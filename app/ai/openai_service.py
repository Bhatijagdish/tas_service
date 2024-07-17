import json
import os
import re

import openai
import asyncio
from dotenv import load_dotenv
from typing import Any
from langchain.callbacks.streaming_aiter import AsyncIteratorCallbackHandler
from langchain.schema import LLMResult
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.agents import AgentType, initialize_agent
from langchain.memory import ConversationBufferWindowMemory
from langchain_community.vectorstores import FAISS
from google.cloud import storage
from db import Session, logger
from crud import insert_message
from openai import OpenAI

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")


class AsyncCallbackHandler(AsyncIteratorCallbackHandler):
    content: str = ""
    final_answer: bool = False

    def __init__(self, db: Session, session_id: str, history_id: str) -> None:
        super().__init__()
        self.db = db
        self.history_id = history_id
        self.session_id = session_id
        self.ai_answer = ""

    async def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        self.ai_answer += token
        self.content += token
        if self.final_answer:
            if '"action_input": "' in self.content:
                if token not in ['"', "}"]:
                    self.queue.put_nowait(token)
        elif "Final Answer" in self.content:
            self.final_answer = True
            self.content = ""

    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        if self.final_answer:
            self.content = ""
            self.final_answer = False
            self.done.set()
            await self.save_to_db()
        else:
            self.content = ""

    async def save_to_db(self):
        logger.info("Adding AI response to DB")
        insert_message(self.db, self.session_id, self.history_id, 'ai', self.ai_answer)


class ConversationalRAG:

    def __init__(self):
        self.bucket = os.environ.get("BUCKET_NAME")
        self.storage_client = storage.Client()
        self.openai_client = OpenAI()
        self.llm = ChatOpenAI(
            model_name="gpt-4o",
            streaming=True,  # ! important
            callbacks=[]  # ! important (but we will add them later)
        )
        logger.info("LLM initialized")
        self.PREFIX_PROMPT = "INFO: You are Prof expert on art history. " \
                             "You will answer the questions asked in details " \
                             "and provide correct responses."

        self.max_session_iteration = 10

        # Download and replace local vector store files
        # os.makedirs("data/merged_vector", exist_ok=True)
        # self.download_and_replace_file("data/merged_vector/index.faiss")
        # self.download_and_replace_file("data/merged_vector/index.pkl")

        self.embeddings = OpenAIEmbeddings()
        self.vectorstore = FAISS.load_local("data/vector_store", self.embeddings, allow_dangerous_deserialization=True)
        self.agent = self.create_tas_agent()

    def download_cs_file(self, file_name, destination_file_name):
        try:
            bucket = self.storage_client.bucket(self.bucket)
            blob = bucket.blob(file_name)
            blob.download_to_filename(destination_file_name)
            logger.info(f"Downloaded {file_name} to {destination_file_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to download {file_name} from {self.bucket}: {str(e)}")
            return False

    def download_and_replace_file(self, local_path):
        try:
            if os.path.exists(local_path):
                os.remove(local_path)
                logger.info(f"Deleting existing file: {os.path.basename(local_path)}")
            else:
                logger.info(f"Starting download: {os.path.basename(local_path)}")
            self.download_cs_file(local_path, local_path)
        except Exception as e:
            logger.error(f"Error downloading and replacing file {local_path}: {str(e)}")

    async def run_call(self, prompt: str, query: str, resLen_String: str,
                       responseLength: str,
                       stream_it: AsyncCallbackHandler, chat_history: list):

        ai_resp = user_resp = ""
        if chat_history:
            if len(chat_history) < self.max_session_iteration:
                for sender, message_text in chat_history:
                    if sender.upper() == 'AI':
                        pattern = r'\{.*?\}'
                        matches = re.findall(pattern, message_text)
                        ai_response = dict(matches).get('action_input')
                        ai_resp += f"\n{ai_response}\n"
                    if sender.upper() == 'HUMAN':
                        user_resp += f"\n{message_text}\n"

        # user query
        query += user_resp
        embedding_vector = OpenAIEmbeddings().embed_query(query)
        if responseLength == 'short':
            k = 4
        elif responseLength == 'medium':
            k = 8
        elif responseLength == 'long':
            k = 12
        else:
            k = 7

        docs = self.vectorstore.similarity_search_by_vector(embedding_vector, k)
        # ai = response
        all_content = '\n'.join(doc.page_content for doc in docs)
        prompt += f"\n\n{resLen_String}\n\n{ai_resp}\n\n{all_content}\n\n{query}"

        logger.info(f"Final Response sent to AI: {prompt}")

        # Assign callback handler
        self.agent.agent.llm_chain.llm.callbacks = [stream_it]
        await self.agent.acall(inputs={"input": prompt})

    async def create_gen(self, prompt: str, query: str, resLen_string: str, responseLength: str,
                         stream_it: AsyncCallbackHandler, chat_history: list):
        task = asyncio.create_task(self.run_call(prompt, query, resLen_string, responseLength,
                                                 stream_it, chat_history))
        async for token in stream_it.aiter():
            yield token
        await task

    def create_tas_agent(self):
        memory = ConversationBufferWindowMemory(
            memory_key="chat_history",
            k=5,
            return_messages=True,
            output_key="output"
        )
        return initialize_agent(
            agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
            tools=[],
            llm=self.llm,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=3,
            early_stopping_method="generate",
            memory=memory,
            return_intermediate_steps=False
        )

    async def response_generator(self, prompt: str, query: str, resLen_String: str,
                                 responseLength: str, chat_history: list):

        ai_resp = user_resp = ""
        if chat_history:
            if len(chat_history) < self.max_session_iteration:
                for sender, message_text in chat_history:
                    if sender.upper() == 'AI':
                        pattern = r'\{.*?\}'
                        matches = re.findall(pattern, message_text)
                        ai_response = dict(matches).get('action_input')
                        ai_resp += f"\n{ai_response}\n"
                    if sender.upper() == 'HUMAN':
                        user_resp += f"\n{message_text}\n"

        # user query
        query += user_resp
        embedding_vector = OpenAIEmbeddings().embed_query(query)
        if responseLength == 'short':
            k = 4
        elif responseLength == 'medium':
            k = 8
        elif responseLength == 'long':
            k = 12
        else:
            k = 7

        docs = self.vectorstore.similarity_search_by_vector(embedding_vector, k)
        data_id = docs[0].metadata['id']
        doc_idx = docs[0].metadata['doc_index']

        # ai = response
        all_content = '\n'.join(doc.page_content for doc in docs)

        response = self.openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"\n\n{resLen_String}\n\n{ai_resp}\n\n{all_content}\n\n{query}"}
            ],
            temperature=0,
            stream=True
        )
        result = {"chat_id": None, "text_message": "", "data_id": data_id, "doc_index": doc_idx}
        for chunk in response:
            result['chat_id'] = chunk.id
            chunk_message = chunk.choices[0].delta.content  # Extract the message
            if chunk_message:
                result['text_message'] += chunk_message
                yield json.dumps(result) + '\n\n\n\n'
