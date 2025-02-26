from datetime import datetime

import bcrypt
import weaviate
import logging

from psycopg import Connection
from weaviate.collections.classes.config import Configure
import weaviate.classes as wvc

from rag.settings import Settings, DBSettings


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
        self.settings = DBSettings()
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

    def init_db(self):
        with self.connection.cursor() as cursor:
            cursor.execute('''
                            CREATE TABLE IF NOT EXISTS users (
                                id SERIAL PRIMARY KEY,
                                username VARCHAR(50) UNIQUE NOT NULL,
                                name VARCHAR(100) NOT NULL,
                                email VARCHAR(100) UNIQUE NOT NULL,
                                password VARCHAR(200) NOT NULL,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        ''')

            # Create login_history table for tracking user logins
            cursor.execute('''
                            CREATE TABLE IF NOT EXISTS login_history (
                                id SERIAL PRIMARY KEY,
                                user_id INTEGER REFERENCES users(id),
                                login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                logout_time TIMESTAMP,
                                ip_address VARCHAR(50),
                                user_agent TEXT
                            )
                        ''')

            self.connection.commit()


    def list_titles(self):
        with self.connection.cursor() as cursor:
            # Query to get all tables in the public schema
            cursor.execute("""
                SELECT thread_id, title FROM conversation_titles ORDER BY created_at DESC;
            """)

            return {thread_id: title for thread_id, title in cursor.fetchall()}

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

    def checkpoint_exists(self):
        return self.table_exists("checkpoints")

    def users_exists(self):
        return self.table_exists("users")

    def get_users_from_db(self):
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT username, name, email, password FROM users")
            db_users = cursor.fetchall()

            # Format for streamlit-authenticator
            credentials = {
                "usernames": {}
            }

            for user in db_users:
                username, name, email, password = user
                credentials["usernames"][username] = {
                    "name": name,
                    "email": email,
                    "password": password
                }

            return credentials

    # Function to add a new user to the database
    def add_user(self, username, name, email, password):
        """Add a new user to the database with hashed password"""
        with self.connection.cursor() as cursor:
            # Check if username or email already exists
            cursor.execute("SELECT * FROM users WHERE username = %s OR email = %s", (username, email))
            if cursor.fetchone():
                return False, "Username or email already exists"

            # Hash the password using bcrypt
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

            # Insert the new user
            cursor.execute(
                "INSERT INTO users (username, name, email, password) VALUES (%s, %s, %s, %s)",
                (username, name, email, hashed_password)
            )
            self.connection.commit()
        return True, "Registration complete"

    # Function to log user login activity
    def log_user_login(self, username, ip_address="", user_agent=""):
        """Record user login in the login_history table"""
        with self.connection.cursor() as cursor:
            # Get user ID from username
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            user_result = cursor.fetchone()

            if user_result:
                user_id = user_result[0]

                # Insert login record
                cursor.execute(
                    "INSERT INTO login_history (user_id, ip_address, user_agent) VALUES (%s, %s, %s)",
                    (user_id, ip_address, user_agent)
                )
                self.connection.commit()
                cursor.close()
                return True
        return False

    # Function to update user logout time
    def log_user_logout(self, username):
        """Update the logout time for the most recent login session"""
        with self.connection.cursor() as cursor:
                # Get user ID from username
                cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
                user_result = cursor.fetchone()

                if user_result:
                    user_id = user_result[0]

                    # Update most recent login record with logout time
                    cursor.execute(
                        """
                        UPDATE login_history 
                        SET logout_time = CURRENT_TIMESTAMP 
                        WHERE user_id = %s 
                        AND id = (
                            SELECT id FROM login_history 
                            WHERE user_id = %s 
                            ORDER BY login_time DESC 
                            LIMIT 1
                        )
                        """,
                        (user_id, user_id)
                    )
                    self.connection.commit()
                    return True
        return False

    def close(self):
        self.connection.close()
