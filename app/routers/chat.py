import json
import os
import re
import time

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from schema import (QueryRequest, TokenCounter, TypeAndID, TypeAndID2, TypeAndID3,
                    QueryUrls, MetadataQuery, ChatHistoryRequest, FetchDataId, IframeQuery)
from ai import AsyncCallbackHandler, ConversationalRAG
from crud import model_to_dict, insert_message, get_recent_messages
from db import Session, db_connection, logger
from ats import num_tokens_from_string, iframe_link_generator, source_link_generator, artist_img_generator
import uuid
from lib import extract_highest_ratio_dict, get_metadata_id, get_best_metadata_id, get_all_artists_ids
from ats_refresh import (get_all_images, create_image_vector_store, get_iframe_images,
                         create_iframe_vector_store, create_partial_local_database, create_local_vector_store,
                         delete_merged_vector, upload_merged_vector)

router = APIRouter()

DB_NAME = os.environ.get("DATABASE", "chatbot.db")
os.environ['USER_AGENT'] = 'MyApp/1.0.0'

ai = ConversationalRAG()
JSON_STORE_PATH = "data/json_files/"
artists_ids = get_all_artists_ids(JSON_STORE_PATH)
VECTOR_STORE_PATH = "data/vector_store/"


# Common function for executing the logic and calculating execution time
def execute_vector_update(update_function):
    start_time = time.time()
    try:
        update_function()
        execution_time = time.time() - start_time
        return {"message": f"Execution took {execution_time} seconds"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"An unexpected error occurred: {str(e)}")


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
        return JSONResponse(content={"error": str(e)}, status_code=400)


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

@router.get("/get_heading_image")
async def find_heading_url(heading_text: str):
    url = await ai.get_heading_url(heading_text)
    return JSONResponse(content={"url": url})


@router.get("/generate_image")
def find_heading_url(heading_text: str):
    url = f"https://www.theartstory.org/images20/ttip/{heading_text}.jpg"
    return JSONResponse(content={"url": url})


@router.post("/get_valid_data_id")
def find_best_match_id(query: FetchDataId):
    best_match_id = get_best_metadata_id(artists_ids, query.chunk)
    return JSONResponse(content={"best_match_id": best_match_id})


@router.post("/generate_response")
async def generate_response(request_body: QueryRequest, db: Session = Depends(db_connection)):
    try:
        if not request_body.query or not request_body.session_id:
            error_message = "Both 'query' and 'session_id' must be provided"
            return JSONResponse(content={"error": error_message}, status_code=400)

        # Regex pattern to match the sections
        pattern = r'%info%(.*?)%\s*%query%(.*?)%\s*%instructions%(.*?)%'
        # Extracting the parts using regex̀``
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
        return JSONResponse(content={"error": str(e)}, status_code=400)


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
        return JSONResponse(content={"error": str(e)}, status_code=400)


@router.post('/get_urls')
async def get_metadata(query: QueryUrls):
    try:
        file = f"{query.data_id}.json"
        file_name = os.path.join(JSON_STORE_PATH, file).replace("\\", "/")
        with open(file_name, 'r') as f:
            extracted_dict = json.load(f)[query.data_id]
        dict_output = extract_highest_ratio_dict(extracted_dict, query.chunk)
        logger.info(dict_output)
        return JSONResponse(content={
            'urls': dict_output.get('url', None)
        }, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)


# @router.post('/get_iframe_link')
# async def get_metadata(query: IframeQuery):
#     try:
#         file = f"{query.data_id}.json"
#         file_name = os.path.join(JSON_STORE_PATH, file).replace("\\", "/")
#         with open(file_name, 'r') as f:
#             extracted_dict = json.load(f)[query.data_id]
#         return JSONResponse(content={
#             'iframe': extracted_dict.get('iframe_link', None)
#         }, status_code=200)
#     except Exception as e:
#         return JSONResponse(content={"error": str(e)}, status_code=400)


@router.post('/get_iframe_link')
async def get_metadata(query: FetchDataId):
    try:
        extracted_dict = await ai.get_iframe_link(query.chunk)
        return JSONResponse(content={
            'iframe': extracted_dict.metadata.get('source', None)
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
        return JSONResponse(content={"error": str(e)}, status_code=400)


@router.post('/get_source_link')
async def get_metadata(query: MetadataQuery):
    try:
        result = {}
        for data_id in query.data_ids:
            file = f"{data_id}.json"
            file_name = os.path.join(JSON_STORE_PATH, file).replace("\\", "/")
            with open(file_name, 'r') as f:
                extracted_dict = json.load(f)
            id_type = extracted_dict['type']
            id_name = extracted_dict[data_id]['name']
            id_source = extracted_dict[data_id]['source_link']
            if id_type in result:
                result[id_type].append(f"[{id_name}]({id_source})]")
            else:
                result[id_type] = [f"[{id_name}]({id_source})]"]
        final_response = ""
        for key, value in result.items():
            type_name = key.capitalize() + ('s' if len(value) > 1 else '')
            final_response += f"\n{type_name}: {', '.join(i for i in value)}"
        return JSONResponse(content={
            'source': final_response
        }, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)


# Define individual operations for each vector update status
@router.post("/initial_cloud_refresh/")
def initial_cloud_refresh():
    """
    Endpoint to perform initial cloud refresh:
    - Create local vector store.
    - Upload vector store to cloud.
    - Delete old cloud vector store.
    """
    return execute_vector_update(lambda: (create_local_vector_store(), delete_merged_vector(), upload_merged_vector()))


@router.post("/local_refresh/")
def local_refresh():
    """
    Endpoint to perform local vector store refresh without cloud upload.
    """
    return execute_vector_update(create_local_vector_store)


@router.post("/partial_cloud_refresh/")
def partial_cloud_refresh():
    """
    Endpoint to refresh the vector store partially, syncing changes to cloud.
    """
    embeddings = OpenAIEmbeddings()
    if not os.path.exists(VECTOR_STORE_PATH):
        raise HTTPException(status_code=400, detail="Vector store path does not exist.")

    vectorstore = FAISS.load_local(VECTOR_STORE_PATH, embeddings, allow_dangerous_deserialization=True)
    return execute_vector_update(lambda: create_partial_local_database(vectorstore))


@router.post("/iframe_vector_refresh/")
def iframe_vector_refresh():
    """
    Endpoint to refresh iframe vector store.
    """
    return execute_vector_update(lambda: (get_iframe_images(), create_iframe_vector_store()))


@router.post("/image_vector_refresh/")
def image_vector_refresh():
    """
    Endpoint to refresh image vector store.
    """
    return execute_vector_update(lambda: (get_all_images(), create_image_vector_store()))
