import weaviate
import json
from pathlib import Path
from natsort import natsorted
from tqdm import tqdm

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.documents import Document
from langchain_weaviate.vectorstores import WeaviateVectorStore

from rag.rag.settings import Settings
from rag.rag.db import WeaviateDB


class ContextualIndexing:
    def __init__(self):
        self.settings = Settings()
        self.batch_size = 100
        print(f"API key: {self.settings.google_api_key}")
        self.summary_prompt = """
        <document> 
        {whole_document} 
        </document> 
        Here is the chunk we want to situate within the whole document 
        <chunk> 
        {chunk_content} 
        </chunk> 
        Please give a short succinct context to situate this chunk within the overall document for the purposes of improving search retrieval of the chunk. Answer only with the succinct context and nothing else. 
        """

        self.llm = ChatGoogleGenerativeAI(model=self.settings.model, temperature=self.settings.temperature, max_retries=2)

    def create_documents(self) -> list:
        json_path = self.settings.json_dir

        documents = []
        file_list = natsorted(json_path.glob("*.json"), reverse=True)
        for json_file in tqdm(file_list):
            with json_file.open('r') as jf:
                json_article = json.load(jf)

            for sec_number, section in enumerate(json_article['sections'], start=1):
                if section['content'] is None:
                    continue

                prompt = ChatPromptTemplate.from_template(self.summary_prompt)
                chain = prompt | self.llm | StrOutputParser()
                output = chain.invoke({"whole_document": json_article, "chunk_content": section["content"]})

                section_title = section['title'] if section['title'] is not None else f"Section {sec_number}"
                document = Document(
                    page_content=f"{output}{section['content']}",
                    metadata={"source": json_file.stem, "section_title": section_title, "section_number": sec_number, "authors": ",".join(json_article['authors'])}
                )

                documents.append(document)

        return documents

    def insert_documents(self, documents: list):
        with WeaviateDB() as wdb:
            wvs = WeaviateVectorStore(wdb, index_name=self.settings.collection, text_key="page_content")
            for i in range(0, len(documents), self.batch_size):
                batch = documents[i:i + self.batch_size]
                wvs.add_documents(documents=batch)

    def list_all_documents_with_vectors(self):
        with WeaviateDB() as wdb:
            collection = wdb.collections.get(self.settings.collection)

            for item in collection.iterator(
                    include_vector=True
            ):
                print(item.properties)
                print(item.vector)

    def delete_collection(self):
        with WeaviateDB() as wdb:
            wdb.collections.delete(self.settings.collection)


if __name__ == "__main__":
    ci = ContextualIndexing()
    docs = ci.create_documents()
    ci.insert_documents(docs)
    # print(docs)
    # ci.delete_collection()
    # ci.list_all_documents_with_vectors()