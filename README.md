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
### UI
UI is based on streamlit.  
To lauch simply type:
```commandline
poetry run streamlit run ./rag/ui.py
```

## Creating backup for weaviate:
```cmd
curl -X POST -H "Content-Type: application/json" -d '{"id": "arxiv-backup-v_1_0"}' http://localhost:8080/v1/backups/filesystem
```

## Restoring from backup:
```cmd
curl -X POST -H "Content-Type: application/json" -d '{"id": "arxiv-backup-v_1_0"}' http://localhost:8080/v1/backups/filesystem/arxiv-backup-v_1_0/restore
```