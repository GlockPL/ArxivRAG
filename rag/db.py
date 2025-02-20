import weaviate
import logging

from weaviate.collections.classes.config import Configure
import weaviate.classes as wvc

from rag.rag.settings import Settings

class WeaviateDB:
    def __init__(self):
        self.settings = Settings()
        self.client = None

    def __enter__(self) -> weaviate.WeaviateClient:
        self.client = weaviate.connect_to_local()
        if not self.client.collections.exists(self.settings.collection):
            self.configure()

        logging.debug(self.client.is_ready())
        return self.client

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.client.close()

    def configure(self):
        coll = self.client.collections.create(
            name=self.settings.collection,
            vectorizer_config=Configure.Vectorizer.text2vec_google_aistudio(self.settings.embedder),
            generative_config=Configure.Generative.google(project_id="id", model_id=self.settings.model),
            properties=[
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
        return coll

