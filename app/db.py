import os
from lib import setup_logger
from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError
import asyncio

DATABASE_CONNECTION_ATTEMPTS = 10
DATABASE_CONNECTION_TIMEOUT = 2
logger = setup_logger()
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


# class DatabaseManager:
#
#     def __init__(self):
#         self.connection = db_engine
#         self.logger = logger
#
#     # async def initialize_db(self):
#     #     """Initialize the database if it doesn't exist."""
#     #     """Create a database connection and create the database file if it doesn't exist."""
#     #     if not os.path.exists(self.db_name):
#     #         self.create_tables(self.connection)
#     #
#     # def create_tables(self, conn: Session):
#     #     """Create the Messages and SessionHistory tables if they don't exist."""
#     #     with conn:
#     #         conn.execute("""
#     #             CREATE TABLE IF NOT EXISTS Messages (
#     #                 message_id INTEGER PRIMARY KEY AUTOINCREMENT,
#     #                 history_id TEXT,
#     #                 sender TEXT CHECK(sender IN ('AI', 'User')) NOT NULL,
#     #                 message_text TEXT NOT NULL,
#     #                 timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
#     #             );
#     #         """)
#     #         conn.execute("""
#     #             CREATE TABLE IF NOT EXISTS SessionHistory (
#     #                 instance_id INTEGER PRIMARY KEY AUTOINCREMENT,
#     #                 session_id TEXT ,
#     #                 history_id TEXT,
#     #                 history_name TEXT DEFAULT 'New Chat',
#     #                 session_creation_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#     #                 history_creation_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
#     #             );
#     #         """)
#
#     # def get_db_connection(self):
#     #     """Provide a transactional scope around a series of operations."""
#     #     try:
#     #         if not self.connection:
#     #             self.logger.info(f"Making connection to the database: {self.db_name}")
#     #             self.connection = sqlite3.connect(self.db_name)
#     #             return self.connection
#     #         else:
#     #             self.logger.info(f"Skipping as connection is already established")
#     #     except sqlite3.Error as e:
#     #         self.logger.info(f"Closing connection as error occurred: {e}")
#     #         if self.connection:
#     #             self.connection.close()
#
#     def execute_query(self, db: Session, query):
#         cursor = self.connection.cursor()
#         try:
#             self.logger.info(f"Executing query: {query}")
#             if params:
#                 cursor.execute(query, params)
#             else:
#                 cursor.execute(query)
#             self.connection.commit()
#             return cursor
#         except sqlite3.Error as e:
#             self.logger.error(f"SQLite error: {e}")
#             self.connection.rollback()
#             raise
#
#     def insert_message(self, history_id, sender, message_text):
#         self.execute_query(
#             "INSERT INTO Messages (history_id, sender, message_text) VALUES (?, ?, ?)",
#             (history_id, sender, message_text))
#
#     def check_and_insert_session(self, session_id, history_id):
#         cur = self.execute_query("SELECT * FROM SessionHistory WHERE session_id = ? AND history_id = ?",
#                                  (session_id, history_id))
#         row = cur.fetchone()
#         if not row:
#             self.insert_history(session_id, history_id)
#
#     def get_recent_messages(self, history_id=None, limit=6):
#         cur = self.execute_query(
#             "SELECT sender, message_text FROM (SELECT sender, message_text, message_id FROM Messages "
#             "WHERE history_id = ? "
#             "ORDER BY message_id DESC LIMIT ?) sub ORDER BY message_id ASC;",
#             (history_id, limit)
#         )
#         return cur.fetchall()
#
#     def insert_history(self, session_id, history_id):
#         self.execute_query("INSERT INTO SessionHistory (session_id, history_id) VALUES (?, ?)",
#                            (session_id, history_id))
#
#     def update_history_name(self, session_id, history_id, history_name):
#         self.execute_query("UPDATE SessionHistory SET history_name = ? WHERE session_id = ? AND history_id = ?",
#                            (history_name, session_id, history_id))
#
#     def get_history_list(self, session_id):
#         cur = self.execute_query("SELECT history_id, history_name FROM SessionHistory WHERE session_id = ?",
#                                  (session_id,))
#         return cur.fetchall()
#
#     def get_chat_history(self, history_id):
#         cur = self.execute_query(
#             "SELECT sender, message_text FROM Messages WHERE history_id = ? ORDER BY message_id",
#             (history_id,)
#         )
#         return cur.fetchall()
