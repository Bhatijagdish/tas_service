import difflib
import json
import logging
import os
import re
import string
import unicodedata
from logging.handlers import RotatingFileHandler
import csv
import uuid
from pathlib import Path
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


def extract_highest_ratio(nested_dict: Dict, match_str: str) -> float:
    highest_ratio = 0

    def traverse_dict(d):
        nonlocal highest_ratio
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
            elif isinstance(value, str):
                confidence = get_confidence_score(value, match_str)
                if confidence > highest_ratio:
                    highest_ratio = confidence

    traverse_dict(nested_dict)
    return highest_ratio


def normalize_text(text):
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = ''.join(c for c in normalized if not unicodedata.combining(c))
    return ascii_text.lower()


def normalize_sentence(sentence):
    words = []
    for word in sentence.split():
        word = re.sub(r"s'?$", "", word)
        normalized_word = normalize_text(word)
        words.append(normalized_word)
    return " ".join(words)


def get_metadata_type(directory_path, file_name) -> str:
    file_path = Path(directory_path) / f"{file_name}"
    with open(file_path, 'r') as file:
        return json.load(file)["type"]


def get_best_metadata_id(directory_path: str, query: str):
    common_words = {"in", "to", "a", "the", "and", "or", "of", "is", "are", "on", "at", "for",
                    "was", "were", "has", "have", "had", "did", "do", "does", "it", "its", "his",
                    "him", "her", "an", "they", "their", "them"}

    best_match_id = None
    highest_ratio = 0

    find_string = query[:50]
    find_string = find_string.replace("\n", "")
    find_string = normalize_sentence(find_string)
    find_string = find_string.translate(str.maketrans('', '', string.punctuation))
    find_string = re.sub(r'[^a-zA-Z\s]', '', find_string)
    string_output = find_string.split()
    filtered_string_output = [word for word in string_output if word.lower() not in common_words]
    find_string = "_".join(filtered_string_output[::-1])

    for item in os.listdir(directory_path):
        best_item = item[:-5]
        confidence = get_confidence_score(best_item, find_string)
        file_type = get_metadata_type(directory_path, item)
        if confidence > highest_ratio and confidence > 0.5 and file_type == 'artist':
            highest_ratio = confidence
            best_match_id = best_item
    return best_match_id


def get_metadata_id(directory_path: str, query: str):
    common_words = {"in", "to", "a", "the", "and", "or", "of", "is", "are", "on", "at", "for",
                    "was", "were", "has", "have", "had", "did", "do", "does", "it", "its", "his",
                    "him", "her", "an", "they", "their", "them"}

    matching_string = query
    cleaned_input = matching_string.translate(str.maketrans('', '', string.punctuation))
    normalized_input = normalize_text(cleaned_input)

    best_match = None
    best_score = float('inf')

    for item in os.listdir(directory_path):
        final_item = item[:-5]
        normalized_item = normalize_text(final_item)
        item_score = 0
        found_all_words = True

        for word in normalized_item.split('_'):
            if word in common_words:
                continue
            position = normalized_input.find(word)
            if position == -1:
                found_all_words = False
                break
            item_score += position
        file_type = get_metadata_type(directory_path, item)
        if found_all_words and item_score < best_score and file_type == 'artist':
            best_match = final_item
            best_score = item_score

    return best_match, best_score
