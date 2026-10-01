"""
RAG chat pipeline: a LangGraph graph that decides whether to search the arXiv index, retrieves article
sections and answers. Conversation history is persisted per thread by the Postgres checkpointer.
"""
import logging
from typing import AsyncIterator

import weaviate
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from rag.settings import db_settings, settings
from rag.utils import get_embeddings, get_llm

ANSWER_PROMPT = """Use the following pieces of context to answer the question at the end.
Each piece of context will have at the end source with arxiv index, list all of this sources and the end of your response.
If you can't answer based on the context ask if you user wants to answer based on your knowledge.

{context}"""

# The question is embedded in the instruction, otherwise models tend to answer it instead of titling it
TITLE_PROMPT = """Write a short title of at most 5 words for a conversation that starts with the question below.
Do not answer the question. Return only the title.

Question: {query}"""

# Graph nodes whose model output is the answer shown to the user.
# The names match the graph used before, so existing conversations keep working.
ANSWER_NODES = ("query_or_respond", "generate")


def handle_tool_error(error: Exception) -> str:
    """
    Turn a failed search into a tool result. A tool call without a result would leave the conversation
    history invalid for the model API and break every later message in the thread.
    """
    logging.error("Tool call failed", exc_info=error)
    return f"The search failed with an error, tell the user that the article search is currently unavailable: {error}"


class RAG:
    """
    Holds the compiled graph and the connections it uses. Create it with `await RAG.create()`
    and release it with `await rag.close()`.
    """

    def __init__(self, pool: AsyncConnectionPool, checkpointer: AsyncPostgresSaver,
                 weaviate_client: weaviate.WeaviateAsyncClient):
        self.settings = settings
        self.pool = pool
        self.checkpointer = checkpointer
        self.weaviate_client = weaviate_client
        self.embeddings = get_embeddings()
        self.llm = get_llm()
        self.retrieve = self.create_retrieve_tool()
        self.graph = self.create_graph()

    @classmethod
    async def create(cls) -> "RAG":
        pool = AsyncConnectionPool(
            db_settings.uri(),
            max_size=10,
            open=False,
            # Connection settings required by the LangGraph Postgres checkpointer
            kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        )
        await pool.open()
        checkpointer = AsyncPostgresSaver(pool)
        await checkpointer.setup()

        weaviate_client = weaviate.use_async_with_local(host=settings.weaviate_host)
        await weaviate_client.connect()
        return cls(pool, checkpointer, weaviate_client)

    async def close(self):
        await self.weaviate_client.close()
        await self.embeddings.aclose()
        await self.pool.close()

    def create_retrieve_tool(self):
        collection = self.weaviate_client.collections.get(self.settings.collection)
        embeddings = self.embeddings
        text_key = self.settings.text_key

        @tool(response_format="content_and_artifact")
        async def retrieve(query: str) -> tuple[str, list[Document]]:
            """
            Query the vector store using embeddings that will retrieve sections from Arxiv cs.AI articles.
            :param query: string with user query
            :return: string with retrieved documents and list of documents with metadata retrieved from vector store
            """
            vector = await embeddings.aembed_query(query)
            result = await collection.query.hybrid(query=query, vector=vector, limit=10)

            retrieved_docs = []
            for obj in result.objects:
                properties = dict(obj.properties)
                retrieved_docs.append(Document(page_content=properties.pop(text_key) or "", metadata=properties))

            serialized = "\n\n".join(
                f"Content: {doc.page_content}\n Source: {doc.metadata.get('source')}"
                for doc in retrieved_docs
            )
            return serialized, retrieved_docs

        return retrieve

    async def query_or_respond(self, state: MessagesState) -> dict:
        """Generate tool call for retrieval or respond."""
        response = await self.llm.bind_tools([self.retrieve]).ainvoke(state["messages"])
        return {"messages": [response]}

    async def generate(self, state: MessagesState) -> dict:
        """Generate answer from the results of the latest retrieval."""
        messages = state["messages"]
        recent_tool_messages = []
        for message in reversed(messages):
            if not isinstance(message, ToolMessage):
                break
            recent_tool_messages.append(message)
        docs_content = "\n\n".join(message.text for message in reversed(recent_tool_messages))

        # Conversation without tool calls and their results, those only matter for the current answer
        conversation_messages = [
            message
            for message in messages
            if isinstance(message, (HumanMessage, SystemMessage))
            or (isinstance(message, AIMessage) and not message.tool_calls)
        ]
        prompt = [SystemMessage(ANSWER_PROMPT.format(context=docs_content))] + conversation_messages
        response = await self.llm.ainvoke(prompt)
        return {"messages": [response]}

    def create_graph(self) -> CompiledStateGraph:
        graph_builder = StateGraph(MessagesState)
        graph_builder.add_node("query_or_respond", self.query_or_respond)
        graph_builder.add_node("tools", ToolNode([self.retrieve], handle_tool_errors=handle_tool_error))
        graph_builder.add_node("generate", self.generate)

        graph_builder.add_edge(START, "query_or_respond")
        graph_builder.add_conditional_edges("query_or_respond", tools_condition, {"tools": "tools", END: END})
        graph_builder.add_edge("tools", "generate")
        graph_builder.add_edge("generate", END)

        return graph_builder.compile(checkpointer=self.checkpointer)

    async def astream(self, query: str, thread_id: str) -> AsyncIterator[str]:
        """Add the user's query to the thread and stream the text of the answer."""
        config = {"configurable": {"thread_id": thread_id}}
        async for chunk, metadata in self.graph.astream(
                {"messages": [HumanMessage(query)]}, config=config, stream_mode="messages"):
            # Only answer text reaches the user, not tool calls or tool results.
            # Text a model writes in the same message as a tool call would still pass, models rarely do that.
            if (isinstance(chunk, AIMessage)
                    and not chunk.tool_calls
                    and not getattr(chunk, "tool_call_chunks", None)
                    and metadata.get("langgraph_node") in ANSWER_NODES
                    and chunk.text):
                yield chunk.text

    async def generate_title(self, query: str) -> str:
        """Generate a conversation title from the user's first query, outside the graph so it is not streamed."""
        response = await self.llm.ainvoke([HumanMessage(TITLE_PROMPT.format(query=query))])
        return response.text.strip().strip('"')[:100]

    async def get_messages(self, thread_id: str) -> list[BaseMessage]:
        state = await self.graph.aget_state({"configurable": {"thread_id": thread_id}})
        return state.values.get("messages", [])

    async def delete_thread(self, thread_id: str):
        await self.checkpointer.adelete_thread(thread_id)
