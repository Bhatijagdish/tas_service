import os
import re
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from schema import (QueryRequest, ChangeHistoryNameRequest, ViewHistoryRequest,
                    ViewChatHistoryRequest, TokenCounter, TypeAndID, TypeAndID2, TypeAndID3)
from ai import AsyncCallbackHandler, ConversationalRAG
from crud import model_to_dict, insert_message, get_recent_messages, get_last_ai_response
from db import Session, db_connection, logger
from ats import num_tokens_from_string, iframe_link_generator, source_link_generator, artist_img_generator
import uuid

router = APIRouter()

ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
DB_NAME = os.environ.get("DATABASE", "chatbot.db")
os.environ['USER_AGENT'] = 'MyApp/1.0.0'

ai = ConversationalRAG()


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

        if chat_history:
            if len(chat_history) < ai.max_session_iteration:
                for sender, message_text in chat_history:
                    if sender.upper() == 'AI':
                        pattern = r'\{.*?\}'
                        matches = re.findall(pattern, message_text)
                        ai_response = dict(matches).get('action_input')
                        prompt += f"\n{ai_response}\n"

        logger.info(f"Prefix: {prompt}")
        logger.info(f"Question: {question}")
        logger.info(f"Response Length Chosen: {resLen_string}")

        insert_message(db, request_body.session_id, history_id, 'human', question)

        stream_it = AsyncCallbackHandler(db, request_body.session_id, history_id)

        gen = ai.create_gen(prompt, question, resLen_string, request_body.responseLength, stream_it)

        return StreamingResponse(gen, media_type="text/event-stream")
    except HTTPException as http_err:
        return JSONResponse(content={"error": str(http_err)}, status_code=http_err.status_code)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


# @router.post("/change_history_name")
# async def change_history_name(request_body: ChangeHistoryNameRequest, db: Session = Depends(db_connection)):
#     try:
#         update_history_name(db, request_body.session_id, request_body.history_id, request_body.new_name)
#         return JSONResponse(content={"message": f"History name updated successfully with history id: "
#                                                 f"{request_body.history_id}"}, status_code=200)
#     except HTTPException as http_err:
#         return JSONResponse(content={"error": str(http_err)}, status_code=http_err.status_code)
#     except Exception as e:
#         return JSONResponse(content={"error": str(e)}, status_code=500)
#
#
# @router.post("/view_history_id_list")
# async def view_history_id_list(request_body: ViewHistoryRequest, db: Session = Depends(db_connection)):
#     try:
#         history_list = get_history_list(db, request_body.session_id)
#         history_list_dict = [model_to_dict(history) for history in history_list]
#         return JSONResponse(content={"history_list": history_list_dict}, status_code=200)
#     except HTTPException as http_err:
#         return JSONResponse(content={"error": str(http_err)}, status_code=http_err.status_code)
#     except Exception as e:
#         return JSONResponse(content={"error": str(e)}, status_code=500)
#
#
# @router.post("/view_chat_history")
# async def view_chat_history(request_body: ViewChatHistoryRequest, db: Session = Depends(db_connection)):
#     try:
#         chat_history = get_chat_history(db, request_body.history_id)
#         chat_list = [model_to_dict(history) for history in chat_history]
#         return JSONResponse(content={"chat_history": chat_list}, status_code=200)
#     except Exception as e:
#         return JSONResponse(content={"error": str(e)}, status_code=500)


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
