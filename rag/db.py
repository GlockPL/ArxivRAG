import weaviate
import logging

from weaviate.collections.classes.config import Configure
from weaviate.collections.classes.filters import Filter

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
            generative_config=Configure.Generative.google(project_id="id", model_id=self.settings.model)
        )
        return coll

    def delete_source(self, source):
        coll = self.client.collections.get(self.settings.collection)
        resp = coll.data.delete_many(where=Filter.by_property(name="source").equal(source))
        return resp