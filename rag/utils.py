from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_openai import ChatOpenAI
from psycopg import Connection, Error

from settings import Settings


def get_llm():
    settings = Settings()
    llm = ChatGoogleGenerativeAI(model=settings.model, temperature=settings.temperature, max_retries=2)
    return llm

def get_big_llm():
    settings = Settings()
    llm = ChatGoogleGenerativeAI(model=settings.model_big, temperature=settings.temperature, max_retries=2)
    return llm

def get_oai_llm():
    settings = Settings()
    llm = ChatOpenAI(model=settings.model_oai, temperature=settings.temperature, max_retries=2)
    return llm


def get_embeddings():
    settings = Settings()
    embeddings = GoogleGenerativeAIEmbeddings(model=f"models/{settings.embedder}")
    return embeddings


def check_database_tables():

    settings = Settings()
    host, database, user, password, port = settings.host, settings.database, settings.user, settings.password, settings.db_port
    try:
        # Establish connection
        connection = Connection.connect(
            host=host,
            dbname=database,
            user=user,
            password=password,
            port=port
        )

        # Create cursor
        with connection.cursor() as cursor:
            # Query to get all tables in the public schema
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE';
            """)

            # Fetch all table names
            tables = [table[0] for table in cursor.fetchall()]

            return bool(tables), tables

    except Error as error:
        print("Error while connecting to PostgreSQL:", error)
        return False, []

    finally:
        if connection:
            connection.close()
