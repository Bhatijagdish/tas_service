import os
import openai
import asyncio
from dotenv import load_dotenv
from typing import Any
from langchain.callbacks.streaming_aiter import AsyncIteratorCallbackHandler
from langchain.schema import LLMResult
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.agents import AgentType, initialize_agent
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain.memory import ConversationBufferWindowMemory
from langchain_community.vectorstores import FAISS
from google.cloud import storage
from db import Session
from lib import setup_logger, export_messages_to_csv, export_session_history_to_csv
from crud import get_recent_messages, get_recent_messages, insert_message, get_all_messages, get_all_history

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
logger = setup_logger()


class AsyncCallbackHandler(AsyncIteratorCallbackHandler):
    content: str = ""
    final_answer: bool = False

    def __init__(self, db: Session, history_id: str, user_input: str) -> None:
        super().__init__()
        self.db = db
        self.history_id = history_id
        self.user_input = user_input
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
        insert_message(self.db, self.history_id, 'User', self.user_input)
        insert_message(self.db, self.history_id, 'AI', self.ai_answer)
        msg_rows = get_all_messages(self.db)
        export_messages_to_csv(msg_rows)
        session_rows = get_all_history(self.db)
        export_session_history_to_csv(session_rows)


class ConversationalRAG:

    def __init__(self):
        self.bucket = os.environ.get("BUCKET_NAME")
        self.storage_client = storage.Client()
        # self.llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0)
        self.llm = ChatOpenAI(
            model_name="gpt-4",
            streaming=True,  # ! important
            callbacks=[]  # ! important (but we will add them later)
        )
        logger.info("LLM initialized")

        # Download and replace local vector store files
        os.makedirs("data/merged_vector", exist_ok=True)
        self.download_and_replace_file("data/merged_vector/index.faiss")
        self.download_and_replace_file("data/merged_vector/index.pkl")

        # self.loader = WebBaseLoader(
        #     web_paths=("https://lilianweng.github.io/posts/2023-06-23-agent/",),
        #     bs_kwargs=dict(
        #         parse_only=bs4.SoupStrainer(
        #             class_=("post-content", "post-title", "post-header")
        #         )
        #     ),
        # )
        # self.logger.info("Loading documents")
        # self.docs = self.loader.load()
        # self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        # self.splits = self.text_splitter.split_documents(self.docs)
        self.embeddings = OpenAIEmbeddings()
        # self.vectorstore = FAISS_Store.from_documents(documents=self.splits, embedding=self.embeddings)
        # self.vectorstore.save_local("data/merged_vector/index")
        self.vectorstore = FAISS.load_local("data/merged_vector", self.embeddings, allow_dangerous_deserialization=True)
        # self.retriever = self.vectorstore.as_retriever()
        # logger.info("Documents loaded and indexed")
        #
        # self.contextualize_q_system_prompt = """
        # Given a chat history and the latest user question which might reference context in the chat history,
        # formulate a standalone question which can be understood without the chat history.
        # Do NOT answer the question, just reformulate it if needed and otherwise return it as is.
        # """
        # self.contextualize_q_prompt = ChatPromptTemplate.from_messages(
        #     [
        #         ("system", self.contextualize_q_system_prompt),
        #         MessagesPlaceholder("chat_history"),
        #         ("human", "{input}"),
        #     ]
        # )
        # self.history_aware_retriever = create_history_aware_retriever(self.llm, self.retriever,
        #                                                               self.contextualize_q_prompt)
        # logger.info("History aware retriever created")
        #
        # self.qa_system_prompt = """
        # You are an assistant for question-answering tasks.
        # Use the following pieces of retrieved context to answer the question.
        # If you don't know the answer, just say that you don't know.
        # Use three sentences maximum and keep the answer concise.
        #
        # {context}
        # """
        # self.qa_prompt = ChatPromptTemplate.from_messages(
        #     [
        #         ("system", self.qa_system_prompt),
        #         MessagesPlaceholder("chat_history"),
        #         ("human", "{input}"),
        #     ]
        # )
        # self.question_answer_chain = create_stuff_documents_chain(self.llm, self.qa_prompt)
        # self.rag_chain = create_retrieval_chain(self.history_aware_retriever, self.question_answer_chain)
        # logger.info("RAG chain created")

        self.store = {}

        # self.conversational_rag_chain = RunnableWithMessageHistory(
        #     self.rag_chain,
        #     self.get_session_history,
        #     input_messages_key="input",
        #     history_messages_key="chat_history",
        #     output_messages_key="answer",
        # )
        # logger.info("Conversational RAG chain created")

        # new changes ===========

        self.memory = ConversationBufferWindowMemory(
            memory_key="chat_history",
            k=5,
            return_messages=True,
            output_key="output"
        )
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

    def get_session_history(self, db: Session, session_id: str) -> BaseChatMessageHistory:
        if session_id not in self.store:
            self.store[session_id] = ChatMessageHistory()
            recent_messages = get_recent_messages(db, session_id)
            for sender, message_text in reversed(recent_messages):
                if sender == 'User':
                    self.store[session_id].add_user_message(message_text)
                elif sender == 'AI':
                    self.store[session_id].add_ai_message(message_text)
        return self.store[session_id]

    async def invoke_rag_chain(self, db: Session, input_text, history_id=None):
        try:
            if history_id:
                response = self.conversational_rag_chain.ainvoke(
                    {"input": input_text, "chat_history": get_recent_messages(db, history_id)},
                    config={
                        "configurable": {"session_id": history_id}
                    },
                )
            else:
                response = self.conversational_rag_chain.invoke(
                    {"input": input_text},
                    config={
                        "configurable": {"session_id": history_id}
                    },
                )
            answer = response["answer"]

            # Save user message and AI response to database
            insert_message(db, history_id, 'User', input_text)
            insert_message(db, history_id, 'AI', answer)

            msg_rows = get_all_messages(db)
            export_messages_to_csv(msg_rows)
            session_rows = get_all_history(db)
            export_session_history_to_csv(session_rows)

            return answer
        except Exception as e:
            error_id = "ERR009"
            logger.error(error_id, "invoke_rag_chain", str(e))
            logger.info(f"Error {error_id} occurred during RAG chain invocation: {str(e)}")
            return None

    async def run_call(self, prompt: str, query: str, resLen_String: str,
                       responseLength: str,
                       stream_it: AsyncCallbackHandler):
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
        all_content = '\n'.join(doc.page_content for doc in docs)
        prompt += f"\n\n{resLen_String}\n\n{all_content}\n\n{query}"

        # Assign callback handler
        self.agent.agent.llm_chain.llm.callbacks = [stream_it]
        await self.agent.acall(inputs={"input": prompt})

    async def create_gen(self, prompt: str, query: str, resLen_string: str, responseLength: str,
                         stream_it: AsyncCallbackHandler):
        task = asyncio.create_task(self.run_call(prompt, query, resLen_string, responseLength, stream_it))
        async for token in stream_it.aiter():
            yield token
        await task

    def create_tas_agent(self):
        return initialize_agent(
            agent=AgentType.CHAT_CONVERSATIONAL_REACT_DESCRIPTION,
            tools=[],
            llm=self.llm,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=3,
            early_stopping_method="generate",
            memory=self.memory,
            return_intermediate_steps=False
        )
