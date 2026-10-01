import weaviate
import logging

from weaviate.collections import Collection
from weaviate.collections.classes.config import Configure
import weaviate.classes as wvc

from rag.settings import Settings


def create_collection(client: weaviate.WeaviateClient, name: str) -> Collection:
    """
    Create a collection for article chunks. Vectors are computed by the application with the local
    embedding model (see rag.embeddings), so Weaviate does not vectorize anything itself.
    """
    return client.collections.create(
        name=name,
        vectorizer_config=Configure.Vectorizer.none(),
        properties=[
            wvc.config.Property(
                name="page_content",
                data_type=wvc.config.DataType.TEXT,
            ),
            wvc.config.Property(
                name="source",
                data_type=wvc.config.DataType.TEXT,
            ),
            wvc.config.Property(
                name="section_title",
                data_type=wvc.config.DataType.TEXT,
            ),
            wvc.config.Property(
                name="section_number",
                data_type=wvc.config.DataType.INT,
            ),
            wvc.config.Property(
                name="authors",
                data_type=wvc.config.DataType.TEXT,
            )
        ]
    )


class WeaviateDB:
    def __init__(self):
        self.settings = Settings()
        self.client = None

    def __enter__(self) -> weaviate.WeaviateClient:
        self.client = weaviate.connect_to_local(host=self.settings.weaviate_host)
        if not self.client.collections.exists(self.settings.collection):
            self.configure()

        logging.debug(self.client.is_ready())
        return self.client

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.close()

    def configure(self):
        return create_collection(self.client, self.settings.collection)
