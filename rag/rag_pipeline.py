from langchain import hub
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from langchain_weaviate import WeaviateVectorStore
from langgraph.graph import START, StateGraph
from typing_extensions import TypedDict, List

from db import WeaviateDB
from settings import Settings
from utils import get_llm, get_embeddings


class State(TypedDict):
    question: str
    context: List[Document]
    answer: str


class RAG:
    def __init__(self):
        # self.rag_prompt = hub.pull("rlm/rag-prompt")
        self.template = """Use the following pieces of context to answer the question at the end.
        Each piece of context will have at the end source with arxiv index, list all of this sources and the end of your response. 
        If you can't answer based on the context ask if you user wants to answer based on your knowledge.                

        {context}

        Question: {question}

        Helpful Answer:"""
        self.rag_prompt = PromptTemplate.from_template(self.template)
        self.settings = Settings()
        self.llm = get_llm()
        self.embeddings = get_embeddings()

        graph_builder = StateGraph(State).add_sequence([self.retrieve, self.generate])
        graph_builder.add_edge(START, "retrieve")
        self.graph = graph_builder.compile()


    def retrieve(self, state: State):
        with WeaviateDB() as wdb:
            wvs = WeaviateVectorStore(wdb, embedding=self.embeddings, index_name=self.settings.collection, text_key=self.settings.text_key)
            retrieved_docs = wvs.similarity_search(state["question"], k=7)
            return {"context": retrieved_docs}

    def generate(self, state: State):
        docs_content = "\n\n".join(f"{doc.page_content}, source:{doc.metadata.get('source')}" for doc in state["context"])
        print(docs_content)
        messages = self.rag_prompt.invoke({"question": state["question"], "context": docs_content})
        response = self.llm.invoke(messages)
        return {"answer": response.content}

    def ask_question(self, question: str):
        for message, _ in self.graph.stream(
                {"question": question}, stream_mode="messages"
        ):
            yield message.content
