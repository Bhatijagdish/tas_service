import logging
from logging.handlers import RotatingFileHandler
import csv


def setup_logger():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler = RotatingFileHandler('tas.log', maxBytes=1024 * 1024 * 10, backupCount=3)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger


def export_messages_to_csv(rows, file_path='messages.csv'):
    with open(file_path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['message_id', 'history_id', 'sender', 'message_text', 'timestamp'])
        writer.writerows(rows)


def export_session_history_to_csv(rows, file_path='session_history.csv'):
    with open(file_path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['instance_id', 'session_id', 'history_id', 'history_name', 'session_creation_timestamp',
                         'history_creation_timestamp'])
        writer.writerows(rows)
