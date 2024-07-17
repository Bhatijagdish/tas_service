import json
import os
import re
from typing import List, Dict
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from schema import (QueryRequest, TokenCounter, TypeAndID, TypeAndID2, TypeAndID3,
                    QueryUrls, MetadataQuery, ChatHistoryRequest)
from ai import AsyncCallbackHandler, ConversationalRAG
from crud import model_to_dict, insert_message, get_recent_messages
from db import Session, db_connection, logger
from ats import num_tokens_from_string, iframe_link_generator, source_link_generator, artist_img_generator
import uuid
from lib import extract_highest_ratio_dict

router = APIRouter()

DB_NAME = os.environ.get("DATABASE", "chatbot.db")
os.environ['USER_AGENT'] = 'MyApp/1.0.0'

ai = ConversationalRAG()
JSON_STORE_PATH = "data/json_files/"


@router.post("/get_response_from_ai")
async def stream_response(request_body: QueryRequest, db: Session = Depends(db_connection)):
    try:
        if not request_body.query or not request_body.session_id:
            error_message = "Both 'query' and 'session_id' must be provided"
            return JSONResponse(content={"error": error_message}, status_code=400)

        history_id = str(uuid.uuid4())
        # Regex pattern to match the sections
        pattern = r'%info%(.*?)%\s*%query%(.*?)%\s*%instructions%(.*?)%'
        # Extracting the parts using regex
        matches = re.search(pattern, request_body.query)

        prompt = question = resLen_string = ""
        if matches:
            prompt = matches.group(1).strip()
            question = matches.group(2).strip()
            resLen_string = matches.group(3).strip()
        # Collecting the message objects from db
        chat_history = get_recent_messages(db, session_id=request_body.session_id)

        logger.info(f"Prefix: {prompt}")
        logger.info(f"Question: {question}")
        logger.info(f"Response Length Chosen: {resLen_string}")

        insert_message(db, request_body.session_id, history_id, 'human', question)

        stream_it = AsyncCallbackHandler(db, request_body.session_id, history_id)

        gen = ai.create_gen(prompt, question, resLen_string, request_body.responseLength, stream_it, chat_history)

        return StreamingResponse(gen, media_type="text/event-stream")
    except HTTPException as http_err:
        return JSONResponse(content={"error": str(http_err)}, status_code=http_err.status_code)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.post("/get_token_count")
async def get_token_count(token_counter: TokenCounter):
    return {"tokens": num_tokens_from_string(token_counter.query)}


@router.post("/get_iframe")
async def get_iframe(type_id: TypeAndID):
    return {'iframe': iframe_link_generator(type_id.query)}


@router.post("/get_source")
async def source(type_id2: TypeAndID2):
    return {'sources': source_link_generator(type_id2.query)}


@router.post("/get_artist_img")
async def artist_img(type_id3: TypeAndID3):
    return {'sources': artist_img_generator(type_id3.query)}


@router.get("/health")
async def health():
    return {"Smiling Face": "☺"}


############################################################################

@router.post("/generate_response")
async def generate_response(request_body: QueryRequest, db: Session = Depends(db_connection)):
    try:
        if not request_body.query or not request_body.session_id:
            error_message = "Both 'query' and 'session_id' must be provided"
            return JSONResponse(content={"error": error_message}, status_code=400)

        # Regex pattern to match the sections
        pattern = r'%info%(.*?)%\s*%query%(.*?)%\s*%instructions%(.*?)%'
        # Extracting the parts using regex
        matches = re.search(pattern, request_body.query)

        prompt = question = resLen_string = ""
        if matches:
            prompt = matches.group(1).strip()
            question = matches.group(2).strip()
            resLen_string = matches.group(3).strip()
        # Collecting the message objects from db
        chat_history = get_recent_messages(db, session_id=request_body.session_id)

        logger.info(f"Prefix: {prompt}")
        logger.info(f"Question: {question}")
        logger.info(f"Response Length Chosen: {resLen_string}")

        return StreamingResponse(ai.response_generator(prompt, question, resLen_string,
                                                       request_body.responseLength, chat_history),
                                 media_type="application/json")
    except HTTPException as http_err:
        return JSONResponse(content={"error": str(http_err)}, status_code=http_err.status_code)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.post('/update_chat_history')
async def update_chat_history(query: ChatHistoryRequest, db: Session = Depends(db_connection)):
    try:
        if query.sender not in {'ai', 'human'}:
            return JSONResponse(content={"Please include sender either 'ai' or 'human'"}, status_code=400)
        insert_message(db, query.session_id, query.history_id, 'human', query.query)
        return JSONResponse(content={"Chat history updated successfully."}, status_code=400)
    except HTTPException as http_err:
        return JSONResponse(content={"error": str(http_err)}, status_code=http_err.status_code)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.post('/get_urls')
async def get_metadata(query: QueryUrls):
    try:
        file = f"{query.data_id}.json"
        file_name = os.path.join(JSON_STORE_PATH, file).replace("\\", "/")
        with open(file_name, 'r') as f:
            extracted_dict = json.load(f)[query.data_id]
        dict_output = extract_highest_ratio_dict(extracted_dict, query.chunk)
        return JSONResponse(content={
            'urls': dict_output.get('url', None)
        }, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.post('/get_iframe_link')
async def get_metadata(query: MetadataQuery):
    try:
        file = f"{query.data_id}.json"
        file_name = os.path.join(JSON_STORE_PATH, file).replace("\\", "/")
        with open(file_name, 'r') as f:
            extracted_dict = json.load(f)[query.data_id]
        return JSONResponse(content={
            'iframe': extracted_dict.get('iframe_link', None)
        }, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)


@router.post('/get_artist_image_link')
async def get_metadata(query: MetadataQuery):
    try:
        file = f"{query.data_id}.json"
        file_name = os.path.join(JSON_STORE_PATH, file).replace("\\", "/")
        with open(file_name, 'r') as f:
            extracted_dict = json.load(f)[query.data_id]
        return JSONResponse(content={
            'artist': extracted_dict.get('artist_image', None)
        }, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.post('/get_source_link')
async def get_metadata(query: MetadataQuery):
    try:
        file = f"{query.data_id}.json"
        file_name = os.path.join(JSON_STORE_PATH, file).replace("\\", "/")
        with open(file_name, 'r') as f:
            extracted_dict = json.load(f)[query.data_id]
        return JSONResponse(content={
            'source': extracted_dict.get('source_link', None)
        }, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
