from datetime import datetime

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

    def create_conversation_title_table(self):
        with self.connection.cursor() as cursor:
            cursor.execute("""
            CREATE TABLE "conversation_titles" (
              "id" serial NOT NULL,
              PRIMARY KEY ("id"),
              "thread_id" text NOT NULL,
              "title" text NOT NULL,
              "created_at" timestamp NOT NULL
            );
            """)
        self.connection.commit()

    def list_titles(self):
        with self.connection.cursor() as cursor:
            # Query to get all tables in the public schema
            cursor.execute("""
                SELECT thread_id, title FROM conversation_titles ORDER BY created_at DESC;
            """)

            return {thread_id:title for thread_id, title in cursor.fetchall()}

    def insert_conversation_title(self, thread_id: str, title: str) -> int:
        with self.connection.cursor() as cur:
            current_timestamp = datetime.now()
            cur.execute(
                """
                INSERT INTO conversation_titles (thread_id, title, created_at)
                VALUES (%s, %s, %s)
                RETURNING id;
                """,
                (thread_id, title, current_timestamp),  # Pass the timestamp
            )
            row_id = cur.fetchone()
            self.connection.commit()
            return row_id[0]  # Extract the ID

    def table_exists(self, table_name: str) -> bool:
        """Checks if a table exists in the database.

        Args:
            table_name: The name of the table to check.

        Returns:
            True if the table exists, False otherwise.
        """
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE  table_schema = 'public'
                    AND    table_name   = %s
                );
                """,
                (table_name,),
            )
            result = cursor.fetchone()
            return result[0] if result else False  # Extract the boolean value

    def conversation_titles_exists(self):
        return self.table_exists("conversation_titles")

    def close(self):
        self.connection.close()
