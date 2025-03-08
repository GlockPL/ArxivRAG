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

### Creating backup for weaviate:
```cmd
curl -X POST -H "Content-Type: application/json" -d '{"id": "arxiv-backup-v_1_0"}' http://localhost:8080/v1/backups/filesystem
```

