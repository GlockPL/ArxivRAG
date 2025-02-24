from typing import Generator, Iterator

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage, SystemMessage, AIMessage, HumanMessage, AnyMessage, ToolMessage
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langchain_weaviate import WeaviateVectorStore
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, StateGraph, add_messages, MessagesState
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.types import StateSnapshot
from psycopg import Connection
from pydantic import BaseModel
from typing_extensions import TypedDict, List, Annotated

from db import WeaviateDB, PostgresDB
from settings import Settings
from utils import get_llm, get_big_llm, get_embeddings, check_database_tables


class RetrieveInput(BaseModel):
    query: str


class GrapState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    title: str


@tool(response_format="content_and_artifact", args_schema=RetrieveInput)
def retrieve(query: str) -> tuple[str, List[Document]]:
    """
    Query the vector store using embeddings that will retrieve sections from Arxiv cs.AI articles.
    :param query: string with user query
    :return: string with retrieved documents and list of documents with metadata retrieved from vector store
    """
    settings = Settings()
    with WeaviateDB() as wdb:
        wvs = WeaviateVectorStore(
            wdb,
            embedding=get_embeddings(),
            index_name=settings.collection,
            text_key=settings.text_key,
        )
        retrieved_docs = wvs.similarity_search(query, k=10)
        serialized = "\n\n".join(
            f"Content: {doc.page_content}\n Source: {doc.metadata.get('source')}"
            for doc in retrieved_docs
        )
        return serialized, retrieved_docs


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
        self.llm = get_big_llm()
        db_uri = f"postgresql://{self.settings.user}:{self.settings.password}@{self.settings.host}:{self.settings.db_port}/{self.settings.user}?sslmode=disable"
        self.connection = Connection.connect(db_uri, autocommit=True)
        self.graph = self.create_graph()

    def query_or_respond(self, state: GrapState) -> dict[str, list]:
        """Generate tool call for retrieval or respond."""
        llm_with_tools = self.llm.bind_tools([retrieve])
        response = llm_with_tools.invoke(state["messages"])
        # MessagesState appends messages to state instead of overwriting
        return {"messages": [response], "title": state["title"]}

    def generate(self, state: GrapState) -> dict[str, list]:
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
        response = self.llm.invoke(prompt)
        return {"messages": [response], "title": state['title']}

    def name_conversation(self, state: GrapState, config: RunnableConfig) -> dict[str, list]:
        """Generate a title for the conversation based on the user's first query."""
        messages = state["messages"]
        if not state.get("title"):
            user_query = messages[0].content  # Assumes first message is the user query
            prompt = [
                SystemMessage(
                    content="Create a short, concise title for this conversation.  The title should be no more than 5 words.  Here is the user's first question:"),
                HumanMessage(content=user_query)
            ]
            response = self.llm.invoke(prompt)
            title = response.content
            thread_id = config["metadata"]["thread_id"]

            pg = PostgresDB()
            pg.insert_conversation_title(thread_id, title)
            pg.close()

            return {"title": title, "messages": messages}

        return {"title": state["title"], "messages": messages}

    def create_graph(self) -> CompiledStateGraph:
        graph_builder = StateGraph(GrapState)
        graph_builder.add_node("query_or_respond", self.query_or_respond)
        graph_builder.add_node("tools", ToolNode([retrieve]))  # Use ToolNode
        graph_builder.add_node("generate", self.generate)
        graph_builder.add_node("name_conversation", self.name_conversation)

        graph_builder.set_entry_point("name_conversation")
        graph_builder.add_conditional_edges(
            "query_or_respond",
            tools_condition,
            {
                "tools": "tools",
                END: END
            },
        )
        graph_builder.add_edge("name_conversation", "query_or_respond")
        graph_builder.add_edge("tools", "generate")
        graph_builder.add_edge("generate", END)

        pg = PostgresDB()

        if not pg.conversation_titles_exists():
            print("Setting up conversation titles table")
            pg.create_conversation_title_table()

        checkpointer = PostgresSaver(self.connection)

        if not pg.checkpoint_exists():
            print("Setting up checkpointer database")
            checkpointer.setup()

        pg.close()

        graph = graph_builder.compile(checkpointer=checkpointer)
        # graph.get_graph().draw_mermaid_png(output_file_path="graph.png")  # Optional
        return graph

    def stream(self, query: str, thread_id: str) -> Generator[str, None, None]:
        """Streams the final response tokens."""
        config = {"configurable": {"thread_id": thread_id}}
        for chunk, metadata in self.graph.stream({"messages": [{"role": "user", "content": query}]}, config=config,
                                                 stream_mode="messages"):
            if chunk.content:
                if "langgraph_node" in metadata:
                    if metadata['langgraph_node'] == "generate" or metadata['langgraph_node'] == "query_or_respond":
                        yield chunk.content

    def get_state_history(self, config: RunnableConfig) -> Iterator[StateSnapshot]:
        return self.graph.get_state_history(config)

    def __del__(self):
        self.connection.close()
