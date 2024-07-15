import difflib
import logging
from logging.handlers import RotatingFileHandler
import csv
import uuid
from typing import Dict


def setup_logger():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

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


def get_confidence_score(str1: str, str2: str) -> float:
    return difflib.SequenceMatcher(None, str1, str2).ratio()


def extract_highest_ratio_dict(nested_dict: Dict, match_str: str) -> Dict:
    highest_ratio = 0
    best_match_dict = {}

    def traverse_dict(d):
        nonlocal highest_ratio, best_match_dict
        for key, value in d.items():
            if isinstance(value, dict):
                traverse_dict(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        traverse_dict(item)
                    elif isinstance(item, str):
                        confidence = get_confidence_score(item, match_str)
                        if confidence > highest_ratio:
                            highest_ratio = confidence
                            best_match_dict = d
            elif isinstance(value, str):
                confidence = get_confidence_score(value, match_str)
                if confidence > highest_ratio:
                    highest_ratio = confidence
                    best_match_dict = d

    traverse_dict(nested_dict)
    return best_match_dict
