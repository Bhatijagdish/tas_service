import os
from lib import logger
from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError
import asyncio

DATABASE_CONNECTION_ATTEMPTS = 10
DATABASE_CONNECTION_TIMEOUT = 2
DB_NAME = os.environ.get("DATABASE", "chatbot.db")
db_engine = create_engine(f"sqlite:///{DB_NAME}", echo=True)

Session = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=db_engine
)

Base = declarative_base()


async def initialize_db() -> None:
    """Connect with the database for the first time. This is with the startup of the server."""
    database_alive = False
    attempt = 1

    while not database_alive:
        try:
            try:
                logger.info("Initializing tables creation")
                Base.metadata.create_all(bind=db_engine)
                logger.info("Tables created successfully")
            except (IntegrityError, ProgrammingError):
                pass
            database_alive = True
            logger.info(f"Database connection attempt {attempt} successful")
        except OperationalError:
            logger.info(f"Database connection attempt {attempt} failed (timeout 3 sec)")
            if attempt == DATABASE_CONNECTION_ATTEMPTS:
                raise ConnectionError("Cannot connect to database")
            attempt += 1
            await asyncio.sleep(DATABASE_CONNECTION_TIMEOUT)


def db_connection() -> Session:
    """This function creates a connection with the database."""
    db = Session()
    try:
        yield db
    finally:
        db.close()
