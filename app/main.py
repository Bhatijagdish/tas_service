from fastapi import FastAPI
from routers import chat
from fastapi.middleware.cors import CORSMiddleware
from db import Session, initialize_db
import os

app = FastAPI()

app.add_middleware(CORSMiddleware,
                   allow_origins=["*"],
                   allow_credentials=True,
                   allow_headers=["*"],
                   allow_methods=["*"], )

app.include_router(chat.router)

DB_NAME = os.environ.get("DATABASE", "chatbot.db")


@app.on_event("startup")
async def startup() -> None:
    print("Starting up the application")
    await initialize_db()


@app.on_event("shutdown")
async def shutdown() -> None:
    print("Shutting down the application")
    session = Session()
    session.close()
