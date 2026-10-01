import logging

import json
from typing import Any, Generator

from natsort import natsorted
from tqdm import tqdm

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
import weaviate
from langchain_weaviate.vectorstores import WeaviateVectorStore
from weaviate.collections import Collection
from weaviate.collections.classes.aggregate import GroupByAggregate
from weaviate.collections.classes.filters import Filter

from rag.settings import settings
from rag.db.db import connect, create_collection
from rag.utils import get_llm, get_embeddings

logging.basicConfig(level=logging.ERROR)

class ContextualIndexing:
    def __init__(self, client: weaviate.WeaviateClient):
        """
        :param client: connected Weaviate client, used for the whole indexing run
        """
        self.client = client
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

        self.llm = get_llm()

    @property
    def collection(self) -> Collection:
        return self.client.collections.get(settings.collection)

    def delete_source(self, source):
        return self.collection.data.delete_many(where=Filter.by_property(name="source").equal(source))

    def count_source(self, source) -> int:
        response = self.collection.aggregate.over_all(total_count=True,
                                                      filters=Filter.by_property("source").equal(source))
        return response.total_count

    def check_sources_not_in_db(self, file_list):
        """
        Check which files in the provided list are not yet indexed in Weaviate.

        Args:
            file_list: List of file paths, their stems are the sources

        Returns:
            A list of sources that have no chunks in the database
        """
        # Extract source identifiers from file paths (assuming stem is used as source)
        sources = [file_path.stem for file_path in file_list]

        responses = []
        collection = self.collection
        batch = 100

        for i in range(0, len(file_list), batch):
            # Use the 'or' operator to check for any of the sources in a single query
            batched_list = sources[i: i + batch].copy()
            source_filter = Filter.by_property("source").contains_any(batched_list)

            # Use groupby to get counts for each source in one query
            response = collection.aggregate.over_all(
                group_by=GroupByAggregate(prop="source"),
                total_count=True,
                filters=source_filter,
            )
            if hasattr(response, 'groups'):
                responses.extend(response.groups)

        # Sources that already have chunks in the database
        indexed_sources = {group.grouped_by.value for group in responses}

        return list(set(sources).difference(indexed_sources))

    def check_if_collection_exists(self) -> bool:
        return self.client.collections.exists(settings.collection)

    def create_documents(self) -> Generator[list[Document], Any, None]:
        json_path = settings.json_dir

        documents = []
        file_list = natsorted(json_path.glob("*.json"), reverse=True)

        srcs = self.check_sources_not_in_db(file_list)
        i = 0

        for file_stem in (pbr:=tqdm(srcs)):
            if i == 0:
                documents = []

            pbr.set_postfix_str(f"File: {file_stem}")

            json_file = json_path / f"{file_stem}.json"

            with json_file.open('r') as jf:
                json_article = json.load(jf)


            if 'title' not in json_article:
                json_file.unlink(missing_ok=True)
                continue

            if 'sections' not in json_article:
                json_file.unlink(missing_ok=True)
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

        # Yield the last partial batch; a full batch was already yielded inside the loop
        if i > 0:
            yield documents

    def insert_documents(self):
        # Creating the collection is explicit and only happens here, on the write path
        if not self.check_if_collection_exists():
            create_collection(self.client, settings.collection)

        wvs = WeaviateVectorStore(self.client, index_name=settings.collection, text_key=settings.text_key,
                                  embedding=get_embeddings())
        for docs in self.create_documents():
            wvs.add_documents(documents=docs)

    def list_all_documents_with_vectors(self):
        for item in self.collection.iterator(include_vector=True):
            logging.debug(item.properties)
            logging.debug(item.vector)

    def delete_collection(self):
        self.client.collections.delete(settings.collection)


if __name__ == "__main__":
    with connect() as weaviate_client:
        ci = ContextualIndexing(weaviate_client)
        ci.insert_documents()
        # ci.delete_collection()
        # ci.list_all_documents_with_vectors()
