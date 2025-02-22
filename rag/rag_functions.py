from typing import List, Generator

from langchain_core.documents import Document
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_weaviate import WeaviateVectorStore
from langgraph.graph import MessagesState, StateGraph
from langgraph.graph import END
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from pydantic import BaseModel
from db import WeaviateDB
from utils import get_llm, get_embeddings  # Make sure these are correct
from settings import Settings


class RetrieveInput(BaseModel):  # Correct Pydantic Model
    query: str


llm = get_llm() # Make sure this returns a strong model

# llm = ChatOpenAI(model="gpt-4o")

@tool(response_format="content_and_artifact", args_schema=RetrieveInput)
def retrieve(query: str) -> tuple[str, List[Document]]:
    """
    Query the vector store for documents
    """
    embeddings = get_embeddings()
    settings = Settings()
    with WeaviateDB() as wdb:
        wvs = WeaviateVectorStore(
            wdb,
            embedding=embeddings,
            index_name=settings.collection,
            text_key=settings.text_key,
        )
        retrieved_docs = wvs.similarity_search(query, k=8)
        serialized = "\n\n".join(
            f"Content: {doc.page_content}\n Source: {doc.metadata.get('source')}"
            for doc in retrieved_docs
        )
        return serialized, retrieved_docs


def query_or_respond(state: MessagesState):
    """Generate tool call for retrieval or respond."""
    llm_with_tools = llm.bind_tools([retrieve])
    response = llm_with_tools.invoke(state["messages"])
    # MessagesState appends messages to state instead of overwriting
    return {"messages": [response]}

def generate(state: MessagesState):
    """Generate answer."""
    messages = state["messages"]
    recent_tool_messages = []
    for message in reversed(messages):
        if message.type == "tool":
            recent_tool_messages.append(message)
        else:
            break
    tool_messages = recent_tool_messages[::-1]

    docs_content = ""
    # Extract content correctly from ToolMessage
    for tool_message in tool_messages:
        if isinstance(tool_message.content, str):
            docs_content += tool_message.content + "\n\n"

    system_message_content = f"""
        Use the following pieces of context to answer the question at the end.
        Each piece of context will have at the end source with arxiv index, list all of this sources and the end of your response. 
        If you can't answer based on the context ask if you user wants to answer based on your knowledge.
        {docs_content}"""

    # Exclude ToolMessages from the conversation history.
    conversation_messages = [
        message
        for message in messages
        if not isinstance(message, ToolMessage) and (message.type in ("human", "system") or (
                    message.type == 'ai' and not getattr(message, 'tool_calls', None)))
    ]

    prompt = [SystemMessage(content=system_message_content)] + conversation_messages
    response = llm.invoke(prompt)
    return {"messages": [response]}


def create_graph():
    graph_builder = StateGraph(MessagesState)
    graph_builder.add_node("query_or_respond", query_or_respond)
    graph_builder.add_node("tools", ToolNode([retrieve]))  # Use ToolNode
    graph_builder.add_node("generate", generate)

    graph_builder.set_entry_point("query_or_respond")
    graph_builder.add_conditional_edges(
        "query_or_respond",
        tools_condition,
        {
            "tools": "tools",
            END: END
        },
    )
    graph_builder.add_edge("tools", "generate")
    graph_builder.add_edge("generate", END)

    graph = graph_builder.compile()
    graph.get_graph().draw_mermaid_png(output_file_path="graph.png") # Optional
    return graph


def stream(graph: CompiledStateGraph, query: str) -> Generator[str, None, None]:
    """Streams the final response tokens."""
    input_message = HumanMessage(content=query)
    for chunk, metadata in graph.stream({"messages": [input_message]}, stream_mode="messages"):
        if chunk.content:
            if "langgraph_node" in metadata:
                # print(f"New metadata: {metadata['langgraph_node']}")
                if metadata['langgraph_node'] == "generate" or metadata['langgraph_node'] == "query_or_respond":
                    yield chunk.content

