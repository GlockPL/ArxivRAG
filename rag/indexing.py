import logging

import json
from natsort import natsorted
from tqdm import tqdm

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.documents import Document
from langchain_weaviate.vectorstores import WeaviateVectorStore
from weaviate.collections.classes.filters import Filter

from rag.rag.settings import Settings
from rag.rag.db import WeaviateDB

logging.basicConfig(level=logging.ERROR)

class ContextualIndexing:
    def __init__(self):
        self.settings = Settings()
        self.batch_size = 2
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

        self.llm = ChatGoogleGenerativeAI(model=self.settings.model, temperature=self.settings.temperature,
                                          max_retries=2)

    def delete_source(self, source):
        with WeaviateDB() as wdb:
            coll = wdb.collections.get(self.settings.collection)
            resp = coll.data.delete_many(where=Filter.by_property(name="source").equal(source))
            return resp

    def count_source(self, source) -> int:
        with WeaviateDB() as wdb:
            coll = wdb.collections.get(self.settings.collection)
            response = coll.aggregate.over_all(total_count=True, filters=Filter.by_property("source").equal(source))
            return response.total_count

    def check_if_collection_exists(self) -> bool:
        with WeaviateDB() as wdb:
            return wdb.collections.exists(self.settings.collection)

    def create_documents(self) -> list:
        json_path = self.settings.json_dir

        documents = []
        file_list = natsorted(json_path.glob("*.json"), reverse=True)
        i = 0

        for json_file in tqdm(file_list):
            if i == 0:
                documents = []

            if self.check_if_collection_exists() and self.count_source(json_file.stem):
                continue

            with json_file.open('r') as jf:
                json_article = json.load(jf)

            if 'title' not in json_article:
                continue

            for sec_number, section in enumerate(json_article['sections'], start=1):
                if not isinstance(section, dict):
                    continue

                if 'content' not in section or 'title' not in section:
                    continue

                if section['content'] is None:
                    continue

                prompt = ChatPromptTemplate.from_template(self.summary_prompt)
                chain = prompt | self.llm | StrOutputParser()
                output = chain.invoke({"whole_document": json_article, "chunk_content": section["content"]})

                section_title = section['title'] if section['title'] is not None else f"Section {sec_number}"
                document = Document(
                    page_content=f"{output}{section['content']}",
                    metadata={"source": json_file.stem, "section_title": section_title, "section_number": sec_number,
                              "authors": ",".join(json_article['authors'])}
                )

                documents.append(document)

            document = Document(
                page_content=f"{json_article['abstract']}",
                metadata={"source": json_file.stem, "section_title": "Abstract", "section_number": 0,
                          "authors": ",".join(json_article['authors'])}
            )
            documents.append(document)
            i += 1
            if i == self.batch_size:
                i = 0
                yield documents

        yield documents

    def insert_documents(self, ):
        with WeaviateDB() as wdb:
            wvs = WeaviateVectorStore(wdb, index_name=self.settings.collection, text_key="page_content")
            for docs in self.create_documents():
                wvs.add_documents(documents=docs)

    def list_all_documents_with_vectors(self):
        with WeaviateDB() as wdb:
            collection = wdb.collections.get(self.settings.collection)

            for item in collection.iterator(
                    include_vector=True
            ):
                logging.debug(item.properties)
                logging.debug(item.vector)

    def delete_collection(self):
        with WeaviateDB() as wdb:
            wdb.collections.delete(self.settings.collection)


if __name__ == "__main__":
    ci = ContextualIndexing()
    ci.insert_documents()
    # ci.delete_collection()
    # ci.list_all_documents_with_vectors()
