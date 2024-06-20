import os
import re
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from schema import (QueryRequest, ChangeHistoryNameRequest, ViewHistoryRequest,
                    ViewChatHistoryRequest, TokenCounter, TypeAndID, TypeAndID2, TypeAndID3)
from ai import AsyncCallbackHandler, ConversationalRAG
from crud import check_and_insert_session, update_history_name, get_history_list, get_chat_history, model_to_dict
from db import Session, db_connection
from ats import num_tokens_from_string, iframe_link_generator, source_link_generator, artist_img_generator

router = APIRouter()

ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
DB_NAME = os.environ.get("DATABASE", "chatbot.db")
os.environ['USER_AGENT'] = 'MyApp/1.0.0'

ai = ConversationalRAG()


@router.post("/stream")
async def stream_response(request_body: QueryRequest, db: Session = Depends(db_connection)):
    try:
        if not request_body.query or not request_body.session_id or not request_body.history_id:
            error_message = "All 'query', 'session_id', and 'history_id' must be provided"
            print(error_message)
            return JSONResponse(content={"error": error_message}, status_code=400)

        check_and_insert_session(db, request_body.session_id, request_body.history_id)

        # Regex pattern to match the sections
        pattern = r'%info%(.*?)%\s*%query%(.*?)%\s*%instructions%(.*?)%'

        # Extracting the parts using regex
        matches = re.search(pattern, request_body.query)
        prompt = question = resLen_string = ""
        if matches:
            prompt = matches.group(1).strip()
            question = matches.group(2).strip()
            resLen_string = matches.group(3).strip()

        stream_it = AsyncCallbackHandler(db, request_body.history_id, request_body.query)

        gen = ai.create_gen(prompt, question, resLen_string, request_body.responseLength, stream_it)
        return StreamingResponse(gen, media_type="text/event-stream")
    except HTTPException as http_err:
        return JSONResponse(content={"error": str(http_err)}, status_code=http_err.status_code)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.post("/change_history_name")
async def change_history_name(request_body: ChangeHistoryNameRequest, db: Session = Depends(db_connection)):
    try:
        update_history_name(db, request_body.session_id, request_body.history_id, request_body.new_name)
        return JSONResponse(content={"message": f"History name updated successfully with history id: "
                                                f"{request_body.history_id}"}, status_code=200)
    except HTTPException as http_err:
        return JSONResponse(content={"error": str(http_err)}, status_code=http_err.status_code)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.post("/view_history_id_list")
async def view_history_id_list(request_body: ViewHistoryRequest, db: Session = Depends(db_connection)):
    try:
        history_list = get_history_list(db, request_body.session_id)
        history_list_dict = [model_to_dict(history) for history in history_list]
        return JSONResponse(content={"history_list": history_list_dict}, status_code=200)
    except HTTPException as http_err:
        return JSONResponse(content={"error": str(http_err)}, status_code=http_err.status_code)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.post("/view_chat_history")
async def view_chat_history(request_body: ViewChatHistoryRequest, db: Session = Depends(db_connection)):
    try:
        chat_history = get_chat_history(db, request_body.history_id)
        chat_list = [model_to_dict(history) for history in chat_history]
        return JSONResponse(content={"chat_history": chat_list}, status_code=200)
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
