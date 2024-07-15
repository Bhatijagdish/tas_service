import re
import tiktoken
import string
import unicodedata
import csv

COMMON_WORDS = {"in", "to", "a", "the", "and", "or", "of", "is", "are", "on", "at", "for"}


def num_tokens_from_string(string: str, encoding_name: str = "cl100k_base") -> int:
    encoding = tiktoken.get_encoding(encoding_name)
    return len(encoding.encode(string))


def iframe_link_generator(sentence: str):
    type_and_id_list = extract_type_and_id_2(sentence)
    links = set()
    for type, id, name, sorting_score, occurrence in type_and_id_list:
        links.add(f"https://www.theartstory.org/data/content/dynamic_content/ai-card/{type}/{re.sub('_', '-', id)}")
    return links

# With Single Word Search (Unique added) + Multi Word Search
def extract_type_and_id(sentence, database_file="database.csv"):
    # Initialize an empty list to store the results
    results = []

    # Remove punctuation and normalize the input sentence
    cleaned_sentence = sentence.translate(str.maketrans('', '', string.punctuation))
    normalized_sentence = normalize_sentence(cleaned_sentence)

    # Open the CSV file with utf-8 encoding
    with open(database_file, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)

        # Read all rows into memory and normalize the 'name' and 'unique_name' fields
        rows = []
        for row in reader:
            normalized_name = normalize_text(row['name'])
            normalized_unique_name = normalize_text(row['unique_name'])
            rows.append({
                'Type': row['Type'],
                'ID': row['ID'],
                'name': normalized_name,
                'unique_name': normalized_unique_name,
                'original_name': row['name']  # Store the original name
            })

    # Iterate through each row in the CSV file
    for row in rows:
        # Extract the normalized name from the current row
        name = row['name']

        # Check if the name is in the normalized sentence and not a common word
        if re.search(r'\b' + re.escape(name) + r'\b', normalized_sentence) and name not in COMMON_WORDS:
            if (row['Type'], row['ID'], row['original_name']) not in results:
                # If not found, add the type and ID to the results list
                results.append((row['Type'], row['ID'], row['original_name']))

    # Remove duplicates and filter out substrings
    unique_results = list(set(results))
    filtered_results = []
    for result in unique_results:
        if all(result[1] not in r[1] or result[1] == r[1] for r in filtered_results):
            filtered_results.append(result)

    # Calculate the score for each result based on its position in the sentence
    scored_results = []
    for result in filtered_results:
        id_words = result[1].split('_')  # Split the ID into individual words
        score = sum(normalized_sentence.find(word) for word in id_words if normalized_sentence.find(word) != -1)
        occurrence = sum(1 for _ in re.finditer(r'\b' + re.escape(result[2]) + r'\b', normalized_sentence))
        scored_results.append((result[0], result[1], result[2], score, occurrence))

    # Sort the results based on the scores
    sorted_results = sorted(scored_results, key=lambda x: x[3])

    # Additional search for each word in the 'unique_name' column
    for word in normalized_sentence.split():
        if word not in COMMON_WORDS:
            for row in rows:
                # Split unique_name into individual words and check each against the word in the sentence
                for unique_word in row['unique_name'].split():
                    if re.search(r'\b' + re.escape(word) + r'\b', unique_word):
                        if (row['Type'], row['ID'], row['original_name']) not in results:
                            score = normalized_sentence.find(word)
                            occurrence = sum(
                                1 for _ in re.finditer(r'\b' + re.escape(word) + r'\b', normalized_sentence))
                            results.append((row['Type'], row['ID'], row['original_name'], score, occurrence))

    # Remove duplicates again after the additional search
    unique_results = list(set(results))
    filtered_results = []
    for result in unique_results:
        if all(result[1] not in r[1] or result[1] == r[1] for r in filtered_results):
            filtered_results.append(result)

    # Recalculate the score and occurrences after the additional search
    scored_results = []
    for result in filtered_results:
        id_words = result[1].split('_')  # Split the ID into individual words
        score = sum(normalized_sentence.find(word) for word in id_words if normalized_sentence.find(word) != -1)
        occurrence = sum(1 for _ in re.finditer(r'\b' + re.escape(result[2]) + r'\b', normalized_sentence))
        scored_results.append((result[0], result[1], result[2], score, occurrence))

    # Sort the final results based on the scores
    sorted_results = sorted(scored_results, key=lambda x: x[3])
    return sorted_results

# With Multi Word Search Only - iFrame Special Only
def extract_type_and_id_2(sentence, database_file="database.csv"):
    # Initialize an empty list to store the results
    results = []

    # Remove punctuation and normalize the input sentence
    cleaned_sentence = sentence.translate(str.maketrans('', '', string.punctuation))
    normalized_sentence = normalize_sentence(cleaned_sentence)

    # Open the CSV file with utf-8 encoding
    with open(database_file, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)

        # Read all rows into memory and normalize the 'name' and 'unique_name' fields
        rows = []
        for row in reader:
            normalized_name = normalize_text(row['name'])
            normalized_unique_name = normalize_text(row['unique_name'])
            rows.append({
                'Type': row['Type'],
                'ID': row['ID'],
                'name': normalized_name,
                'unique_name': normalized_unique_name,
                'original_name': row['name']  # Store the original name
            })

    # Iterate through each row in the CSV file
    for row in rows:
        # Extract the normalized name from the current row
        name = row['name']

        # Check if the name is in the normalized sentence and not a common word
        if re.search(r'\b' + re.escape(name) + r'\b', normalized_sentence) and name not in COMMON_WORDS:
            if (row['Type'], row['ID'], row['original_name']) not in results:
                # If not found, add the type and ID to the results list
                results.append((row['Type'], row['ID'], row['original_name']))

    # Remove duplicates and filter out substrings
    unique_results = list(set(results))
    filtered_results = []
    for result in unique_results:
        if all(result[1] not in r[1] or result[1] == r[1] for r in filtered_results):
            filtered_results.append(result)

    # Calculate the score for each result based on its position in the sentence
    scored_results = []
    for result in filtered_results:
        id_words = result[1].split('_')  # Split the ID into individual words
        score = sum(normalized_sentence.find(word) for word in id_words if normalized_sentence.find(word) != -1)
        occurrence = sum(1 for _ in re.finditer(r'\b' + re.escape(result[2]) + r'\b', normalized_sentence))
        scored_results.append((result[0], result[1], result[2], score, occurrence))

    # Sort the results based on the scores
    sorted_results = sorted(scored_results, key=lambda x: x[3])

    # Final removal of duplicates and re-sorting
    unique_results = list(set(results))
    filtered_results = []
    for result in unique_results:
        if all(result[1] not in r[1] or result[1] == r[1] for r in filtered_results):
            filtered_results.append(result)

    # Recalculate the score and occurrences after the additional search
    scored_results = []
    for result in filtered_results:
        id_words = result[1].split('_')  # Split the ID into individual words
        score = sum(normalized_sentence.find(word) for word in id_words if normalized_sentence.find(word) != -1)
        occurrence = sum(1 for _ in re.finditer(r'\b' + re.escape(result[2]) + r'\b', normalized_sentence))
        scored_results.append((result[0], result[1], result[2], score, occurrence))

    # Sort the final results based on the scores
    sorted_results = sorted(scored_results, key=lambda x: x[3])
    return sorted_results

def normalize_sentence(sentence):
    # Normalize sentence by removing possessive forms and converting to lowercase
    words = []
    for word in sentence.split():
        # Remove possessive 's
        word = re.sub(r"s'?$", "", word)
        # Normalize the word
        normalized_word = normalize_text(word)
        words.append(normalized_word)
    return " ".join(word.lower() for word in words)


def normalize_text(text):
    # Normalize text to remove accents and convert to lowercase
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = ''.join(c for c in normalized if not unicodedata.combining(c))
    return ascii_text.lower()


def source_link_generator(sentence: str):
    type_and_id_list = extract_type_and_id(sentence)
    links_by_type = {}

    # Group results by type
    for type, id, name, _, _ in type_and_id_list:
        if type not in links_by_type:
            links_by_type[type] = []
        link = f"https://www.theartstory.org/{type}/{re.sub('_', '-', id)}/"
        formatted_name = ' '.join(word.capitalize() for word in name.split())
        links_by_type[type].append(f"[{formatted_name}]({link})")

    # Create the final formatted string
    formatted_result = []
    for type, links in links_by_type.items():
        type_name = type.capitalize() + ('s' if len(links) > 1 else '')
        formatted_result.append(f"{type_name}: {', '.join(links)}")

    return '\n'.join(formatted_result)


def artist_img_generator(sentence: str):
    type_and_id_list = extract_type_and_id(sentence)
    links_set = set()
    for type, id, _, _, _ in type_and_id_list:
        if type == 'artist':
            links_set.add(f"https://www.theartstory.org/images20/ttip/{id}.jpg")
    return list(links_set)
