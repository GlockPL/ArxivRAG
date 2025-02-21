from typing import Sequence, Generator

from PIL import Image
from langchain_core.documents import Document
from langchain_core.messages import BaseMessage, SystemMessage, AIMessage, HumanMessage
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import tool
from langchain_weaviate import WeaviateVectorStore
from langgraph.graph import END, StateGraph, add_messages, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition
from pydantic import BaseModel
from typing_extensions import TypedDict, List, Annotated

from db import WeaviateDB
from settings import Settings
from utils import get_llm, get_embeddings


class State(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    question: str
    context: List[Document]
    answer: str

class RetrieveInput(BaseModel):  # Define Pydantic model
    query: str

class RAG:
    def __init__(self):
        # self.rag_prompt = hub.pull("rlm/rag-prompt")
        self.template = """Use the following pieces of context to answer the question at the end.
        Each piece of context will have at the end source with arxiv index, list all of this sources and the end of your response. 
        If you can't answer based on the context ask if you user wants to answer based on your knowledge.                

        {context}
        """
        self.rag_prompt = PromptTemplate.from_template(self.template)
        self.settings = Settings()
        self.llm = get_llm()
        self.embeddings = get_embeddings()

        retr_tool = ToolNode([self.retrieve])

        graph_builder = StateGraph(MessagesState)
        graph_builder.add_node("query_or_respond", self.query_or_respond)
        graph_builder.add_node("retriever_tool", retr_tool)
        graph_builder.add_node("generate", self.generate)

        graph_builder.set_entry_point("query_or_respond")
        graph_builder.add_conditional_edges(
            "query_or_respond",
            tools_condition,
            {END: "generate", "tools": "retriever_tool"},
        )
        graph_builder.add_edge("retriever_tool", "generate")
        graph_builder.add_edge("generate", END)

        self.graph = graph_builder.compile()
        self.graph.get_graph().draw_mermaid_png(output_file_path="graph.png")

    @tool(response_format="content_and_artifact", args_schema=RetrieveInput)
    def retrieve(self, query: str):
        """
        Retrive information from query
        :param query: str with user query
        :return:
        """
        with WeaviateDB() as wdb:
            wvs = WeaviateVectorStore(wdb, embedding=self.embeddings, index_name=self.settings.collection,
                                      text_key=self.settings.text_key)
            retrieved_docs = wvs.similarity_search(query, k=8)
            serialized = "\n\n".join(
                f"Content: {doc.page_content}\n Source: {doc.metadata.get('source')}"
                for doc in retrieved_docs
            )
            return serialized, retrieved_docs

    def query_or_respond(self, state: MessagesState):
        """Generate tool call for retrieval or respond."""
        llm_with_tools = self.llm.bind_tools([self.retrieve])
        response = llm_with_tools.invoke(state["messages"])
        return {"messages": state["messages"] + [response]}

    def generate(self, state: MessagesState):
        """Generate answer."""
        # Get generated ToolMessages
        recent_tool_messages = []
        for message in reversed(state["messages"]):
            if message.type == "tool":
                recent_tool_messages.append(message)
            else:
                break
        tool_messages = recent_tool_messages[::-1]

        # Format into prompt
        docs_content = "\n\n".join(doc.content for doc in tool_messages)
        system_message_content = f"""Use the following pieces of context to answer the question at the end.
        Each piece of context will have at the end source with arxiv index, list all of this sources and the end of your response. 
        If you can't answer based on the context ask if you user wants to answer based on your knowledge.                

        {docs_content}
        """
        conversation_messages = [
            message
            for message in state["messages"]
            if message.type in ("human", "system")
               or (message.type == "ai" and not message.tool_calls)
        ]
        prompt = [SystemMessage(system_message_content)] + conversation_messages

        # Run
        response = self.llm.invoke(prompt)
        return {"messages": [response]}

    def ask_question(self, question: str) -> str:
        for step in self.graph.stream(
                {"messages": [{"role": "user", "content": question}]},
                stream_mode="debug",
        ):
            yield step
