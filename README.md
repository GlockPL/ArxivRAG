## RAG App for Arxiv Articles from cs_AI category
### Setup
Create .env file with api key to google ai studio.  
Simple template is in file env_template  
Key can be generated for free [here](https://aistudio.google.com/app/apikey).  
The amount of data is so big that free tier maybe not enough to index entire dataset.  
### Run docker compose file:
Clone the repository.   
Create folder `backups` inside the main folder of the repository and run:
```cmd
docker-compose -f docker-compose-prod.yml up --build -d
```
This will build the docker image with the repo and launch all the databases necessary to run the project. 

### Restoring weaviate db from backup:
**You can download the prepared database from [here](https://drive.google.com/file/d/1s6dnBTHBjb7_J7L2qznFwjrp67ohcpLN/view?usp=drive_link)**   
After download unpack the data into the backups directory and run this command from terminal:
```cmd
curl -X POST -H "Content-Type: application/json" -d '{"id": "arxiv-backup-v_1_0"}' http://localhost:8080/v1/backups/filesystem/arxiv-backup-v_1_0/restore
```
This will load the content of the backup into the database.     
Connet through browser with `http://localhost` and register new user.

### Embeddings
Article sections are embedded locally with a Qwen3 embedding model served by
[text-embeddings-inference](https://github.com/huggingface/text-embeddings-inference) (the `embeddings`
service in the compose files, it needs an NVIDIA GPU). The model is set with `EMBEDDING_MODEL`
(default `Qwen/Qwen3-Embedding-0.6B`).

To re-embed the existing chunks of a Weaviate collection with the local model (resumable, the vectors and texts
are also saved to `./embeddings`):
```
uv run python -m rag.reembed bench --limit 2000   # optional: measure throughput
uv run python -m rag.reembed embed                # read chunks from the Arxiv collection and embed them
uv run python -m rag.reembed load                 # load them into the ArxivQwen3 collection
```

### Indexing data
Run docker compose:
```
docker compose up -d
```
This will start weaviate, the embeddings server and the other databases.
Then with [uv](https://docs.astral.sh/uv/) installed run:
```
uv sync
uv run python -m rag.indexing
```

### Creating backup for weaviate:
```cmd
curl -X POST -H "Content-Type: application/json" -d '{"id": "arxiv-backup-v_1_0"}' http://localhost:8080/v1/backups/filesystem
```

