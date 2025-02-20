## RAG App for Arxiv Articles from cs_AI category
### Setup
Create .env file with api key to google ai studio.  
Key can be generated for free [here](https://aistudio.google.com/app/apikey).
The amount of data is so big that free tier maybe not enough to index entire dataset.
### Indexing data
Run docker compose:
```
docker compose up -d
```
This will start weaviate database.
Than on python 3.11 run:
```
 poetry install
```
next
```
poetry run ./rag/indexing.py
```
