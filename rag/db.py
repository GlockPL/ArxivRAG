import weaviate
import logging

from psycopg import Connection
from weaviate.collections.classes.config import Configure
import weaviate.classes as wvc

from settings import Settings

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


class PostgresDB:
    def __init__(self):
        self.settings = Settings()
        self.connection = self._connect()

    def _connect(self):
        connection = Connection.connect(
            host=self.settings.host,
            dbname=self.settings.user,
            user=self.settings.user,
            password=self.settings.password,
            port=self.settings.db_port
        )
        return connection


    def list_history(self):
        with self.connection.cursor() as cursor:
            # Query to get all tables in the public schema
            cursor.execute("""
                SELECT thread_id FROM checkpoints GROUP BY thread_id;
            """)

            # Fetch all table names
            history = [thread_id[0] for thread_id in cursor.fetchall()]

            return history
    def close(self):
        self.connection.close()



