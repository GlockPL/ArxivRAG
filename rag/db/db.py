import weaviate

from weaviate.collections import Collection
from weaviate.collections.classes.config import Configure
import weaviate.classes as wvc

from rag.settings import settings


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


def connect() -> weaviate.WeaviateClient:
    """
    Connect to Weaviate; the client is a context manager that closes the connection on exit:

        with connect() as client:
            ...
    """
    return weaviate.connect_to_local(host=settings.weaviate_host)
