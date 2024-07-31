# TAS Service

This is the backend service of the TAS chatbot integrated with openAI latest model.

## Clone the repo

```commandline
git clone https://github.com/repo_name
```

## Change directory

```commandline
cd tas_service
```

## Install dependencies
```commandline
pip install -r requirements.txt
```

## Set up environment variables

Create a new file `.env` within `app` directory and add variable names
```commandline
OPENAI_API_KEY="sk-xxxxxxx"
DATABASE="your_db_name.db"
GOOGLE_APPLICATION_CREDENTIALS="env/your_json_file_name.json"
BUCKET_NAME="your_bucket_name"
```

## Start the server 

### Run without Docker

```commandline
cd app
```
```commandline
`python -m uvicorn main:app --host 0.0.0.0 --port 8000`

or for python3:

`python3 -m uvicorn main:app --host 0.0.0.0 --port 8000`
```
or

uvicorn main:app 

### Run with Docker Compose

```commandline
docker-compose up -d
```

