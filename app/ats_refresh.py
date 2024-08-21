import shutil
import time
import xml.etree.ElementTree as ET
import re
import os
import textwrap
import json
from typing import List, Dict, Union
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from langchain_core.documents import Document
from typing import Iterator
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from google.cloud import storage
from dotenv import load_dotenv

VECTOR_STORE_PATH = "data/vector_store/"
JSON_STORE_PATH = "data/json_files/"
IMAGE_STORE_PATH = "data/image_vector"
IFRAME_STORE_PATH = "data/iframe_store"


def fetch_and_parse_xml(url: str) -> Union[ET.Element, None]:
    with requests.get(url) as response:
        if response.status_code == 200:
            return ET.fromstring(response.content)
        return None


def get_xml_files() -> Dict:
    url = "https://www.theartstory.org/sitemap.htm"
    paths = set()
    with requests.get(url) as response:
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        filter_paths = ["/artist/", "/critic/", "/definition/", "/influencer/", "/movement/"]

        for link in soup.find_all('a', href=True):
            href = link['href']
            full_url = urljoin(url, href)
            path = urlparse(full_url).path
            if any(filter_path in path for filter_path in filter_paths):
                paths.add(path)

    data_dict = {"artist": [], "critic": [], "definition": [], "influencer": [], "movement": []}
    for path in paths:
        segments = path.split("/")
        extracted_type = segments[1]
        extracted_id = segments[2]

        data_dict.get(extracted_type).append(
            f"https://www.theartstory.org/data/content/{extracted_type}/{re.sub('-', '_', extracted_id)}.xml")

    return data_dict


def extract_artist_data(root: ET.Element) -> Dict:
    artist_data = {}
    artist_id = None

    main_element = root.find('main')
    if main_element is not None:
        artist_id = main_element.findtext('id')
        new_artist_id = re.sub('_', '-', artist_id)
        artist_data['source_link'] = f"https://www.theartstory.org/artist/{new_artist_id}/"
        artist_data[
            'iframe_link'] = f"https://www.theartstory.org/data/content/dynamic_content/ai-card/artist/{new_artist_id}"
        artist_data['artist_image'] = f"https://www.theartstory.org/images20/ttip/{artist_id}.jpg"
        artist_data['name'] = main_element.findtext('name')
        artist_data['years_worked'] = main_element.findtext('years')
        artist_data['description'] = main_element.findtext('description')
        artist_data['art_description'] = main_element.findtext('art_description')
        artist_data['nationality'] = main_element.findtext('nationality')
        artist_data['occupation'] = main_element.findtext('occupation')
        artist_data['birthDate'] = main_element.findtext('birthDate')
        artist_data['birthPlace'] = main_element.findtext('birthPlace')
        artist_data['deathDate'] = main_element.findtext('deathDate')
        artist_data['deathPlace'] = main_element.findtext('deathPlace')
        artist_data['content_publish_date'] = main_element.findtext('pub_time')

    artist_data['quotes'] = [quote.text for quote in root.findall('.//quotes/q')]
    artist_data['synopsis'] = re.sub(r'<.*?>', '', root.findtext(path='.//article/synopsys', default=''))
    artist_data['similar_artists'] = [artist.text for artist in root.findall('.//artist')]
    artist_data['key_ideas'] = [re.sub(r'<.*?>', '', idea.text) for idea in root.findall('.//idea')]

    artist_data['sections'] = extract_sections(root)
    artist_data['artworks'] = extract_artworks(root, artist_id)
    artist_data['recommended_books'] = extract_recommended_books(root, "category", "subcategory[@name='not_to_show']")
    artist_data['extra_links'] = extract_extra_links(root, 'web resources')

    return {artist_id: artist_data, "type": "artist", "id": artist_id}


def extract_movement_data(root: ET.Element) -> Dict:
    movement_data = {}
    movement_id = None

    main_element = root.find('main')
    if main_element is not None:
        movement_id = main_element.findtext('id')
        new_movement_id = re.sub('_', '-', movement_id)
        movement_data['source_link'] = f"https://www.theartstory.org/movement/{new_movement_id}/"
        movement_data[
            'iframe_link'] = f"https://www.theartstory.org/data/content/dynamic_content/ai-card/movement/{new_movement_id}"
        movement_data['name'] = main_element.findtext('name')
        movement_data['years_developed'] = main_element.findtext('years')
        movement_data['description'] = main_element.findtext('description')
        movement_data['art_title'] = main_element.findtext('art_title')
        movement_data['art_description'] = main_element.findtext('art_description')
        movement_data['biography_highlights'] = re.sub(r'<.*?>', '',
                                                       main_element.findtext(path='bio_highlight', default=''))
        movement_data['content_publish_date'] = main_element.findtext('pub_time')

    movement_data['quotes'] = [quote.text for quote in root.findall('.//quotes/q')]
    movement_data['synopsis'] = re.sub(r'<.*?>', '', root.findtext(path='.//article/synopsys', default=''))
    movement_data['key_ideas'] = [re.sub(r'<.*?>', '', idea.text) for idea in root.findall('.//idea')]

    movement_data['sections'] = extract_sections(root)
    movement_data['artworks'] = extract_artworks(root, movement_id)
    movement_data['recommended_pages'] = extract_recommended_pages(root, "category[@name='art story website features']",
                                                                   "subcategory[@name='not_to_show']")
    movement_data['amazon_links'] = extract_recommended_books(root, "category[@name='featured books']", "subcategory")
    movement_data['extra_links'] = extract_extra_links(root, 'resources')

    return {movement_id: movement_data, "type": "movement", "id": movement_id}


def extract_definition_xml(root: ET.Element) -> Dict:
    definition_data = {}
    definition_id = None

    main_element = root.find('main')
    if main_element is not None:
        definition_id = main_element.findtext('id')
        new_definition_id = re.sub('_', '-', definition_id)
        definition_data['source_link'] = f"https://www.theartstory.org/definition/{new_definition_id}/"
        definition_data[
            'iframe_link'] = f"https://www.theartstory.org/data/content/dynamic_content/ai-card/definition/{new_definition_id}"
        definition_data['name'] = main_element.findtext('name')
        definition_data['start_date'] = main_element.findtext('start')
        definition_data['content_publish_date'] = main_element.findtext('pub_time')

    definition_data['quotes'] = [quote.text for quote in root.findall('.//quotes/q')]
    definition_data['synopsis'] = re.sub(r'<.*?>', '', root.findtext(path='.//article/synopsys', default=''))
    definition_data['key_ideas'] = [re.sub(r'<.*?>', '', idea.text) for idea in root.findall('.//idea')]

    definition_data['sections'] = extract_sections(root)
    definition_data['artworks'] = extract_artworks(root, definition_id)
    definition_data['amazon_links'] = extract_recommended_books(root, "category[@name='featured books']",
                                                                "subcategory")
    definition_data['extra_links'] = extract_extra_links(root, "web resources")

    return {definition_id: definition_data, "type": "definition", "id": definition_id}


def extract_critic_xml(root: ET.Element) -> Dict:
    critic_data = {}
    critic_id = None
    main_element = root.find('main')
    if main_element is not None:
        critic_id = main_element.findtext('id')
        new_critic_id = re.sub('_', '-', critic_id)
        critic_data['source_link'] = f"https://www.theartstory.org/critic/{new_critic_id}/"
        critic_data[
            'iframe_link'] = f"https://www.theartstory.org/data/content/dynamic_content/ai-card/critic/{new_critic_id}"
        critic_data['name'] = main_element.findtext('name')
        critic_data['years_worked'] = main_element.findtext('years')
        critic_data['description'] = main_element.findtext('description')
        critic_data['art_description'] = main_element.findtext('art_description')
        critic_data['nationality'] = main_element.findtext('nationality')
        critic_data['occupation'] = main_element.findtext('occupation')
        critic_data['birth_date'] = main_element.findtext('birthDate')
        critic_data['birth_place'] = main_element.findtext('birthPlace')
        critic_data['death_date'] = main_element.findtext('deathDate')
        critic_data['death_place'] = main_element.findtext('deathPlace')
        critic_data['content_publish_date'] = main_element.findtext('pub_time')

    critic_data['quotes'] = [quote.text for quote in root.findall('.//quotes/q')]
    critic_data['synopsis'] = re.sub(r'<.*?>', '', root.findtext(path='.//article/synopsys', default=''))
    critic_data['key_ideas'] = [re.sub(r'<.*?>', '', idea.text) for idea in root.findall('.//idea')]

    critic_data['sections'] = extract_sections(root)
    critic_data['artworks'] = extract_artworks(root, critic_id)
    critic_data['recommended_pages'] = extract_recommended_pages(root, "category[@name='art story website']",
                                                                 "subcategory")
    critic_data['amazon_links'] = extract_recommended_books(root, "category[@name='featured books']", "subcategory")
    critic_data['extra_links'] = extract_extra_links(root, 'web resources')

    return {critic_id: critic_data, "type": "critic", "id": critic_id}


def extract_influencer_data(root: ET.Element) -> Dict:
    influencer_data = {}
    influencer_id = None

    main_element = root.find('main')
    if main_element is not None:
        influencer_id = main_element.findtext('id')
        new_influencer_id = re.sub('_', '-', influencer_id)
        influencer_data['source_link'] = f"https://www.theartstory.org/influencer/{new_influencer_id}/"
        influencer_data[
            'iframe_link'] = f"https://www.theartstory.org/data/content/dynamic_content/ai-card/influencer/{new_influencer_id}"
        influencer_data['name'] = main_element.findtext('name')
        influencer_data['years_worked'] = main_element.findtext('years')
        influencer_data['description'] = main_element.findtext('description')
        influencer_data['art_description'] = main_element.findtext('art_description')
        influencer_data['nationality'] = main_element.findtext('nationality')
        influencer_data['occupation'] = main_element.findtext('occupation')
        influencer_data['birth_date'] = main_element.findtext('birthDate')
        influencer_data['birth_place'] = main_element.findtext('birthPlace')
        influencer_data['death_date'] = main_element.findtext('deathDate')
        influencer_data['death_place'] = main_element.findtext('deathPlace')
        influencer_data['content_publish_date'] = main_element.findtext('pub_time')

    influencer_data['quotes'] = [quote.text for quote in root.findall('.//quotes/q')]
    influencer_data['synopsis'] = re.sub(r'<.*?>', '', root.findtext(path='.//article/synopsys', default=''))
    influencer_data['key_ideas'] = [re.sub(r'<.*?>', '', idea.text) for idea in root.findall('.//idea')]

    influencer_data['sections'] = extract_sections(root)
    influencer_data['artworks'] = extract_artworks(root, influencer_id)
    influencer_data['recommended_books'] = extract_recommended_books(root, "category[@name='featured books']",
                                                                     "subcategory[@name='written by artist']") + \
                                           extract_recommended_books(root, "category[@name='featured books']",
                                                                     "subcategory[@name='biography']")
    influencer_data['extra_links'] = extract_extra_links(root, 'web resources')

    return {influencer_id: influencer_data, "type": "influencer", "id": influencer_id}


def extract_sections(root: ET.Element) -> List[Dict]:
    sections_list = []
    for section in root.iter('section'):
        section_data = {
            'title': section.get('title'),
            'sub_sections': [
                {
                    'title': subsection.get('title'),
                    'content': ' '.join(
                        re.sub(r'<.*?>', '', ' '.join(p.itertext())).strip() for p in subsection.iter('p') if
                        p.get('type') == 'p'),
                    'url': [{'alt_name': p.get('alt'),
                             'url': re.sub(r'<.*?>', '', f'https://www.theartstory.org{p.text}')} for p
                            in subsection.iter('p') if p.get('type') == 'img']
                }
                for subsection in section.iter('subsection')
            ]
        }
        sections_list.append(section_data)
    return sections_list


def extract_artworks(root: ET.Element, artist_id: str) -> List[Dict]:
    artworks_list = []
    for artworks in root.iter('artworks'):
        for i, artwork in enumerate(artworks.iter('artwork')):
            artwork_data = {
                'title': artwork.find('title').text,
                'year': artwork.find('year').text,
                'materials': artwork.find('materials').text,
                'description': re.sub(r'<.*?>', '', textwrap.dedent(artwork.find('desc').text)),
                'collection': artwork.find('collection').text,
                'url': f'https://www.theartstory.org/images20/works/{artist_id}_{i + 1}.jpg' if
                artwork.find('use_big_image') is not None and bool(artwork.find('use_big_image').text) else
                f'https://www.theartstory.org/images20/pnt/pnt_{artist_id}_{i + 1}.jpg'
            }
            artworks_list.append(artwork_data)
    return artworks_list


def extract_recommended_books(root: ET.Element, category: str, subcategory: str) -> List[Dict]:
    amazon_links_list = []
    for entry in root.findall(f".//{category}/{subcategory}/entry"):
        book_data = {
            'title': entry.findtext('title'),
            'info': entry.findtext('info'),
            'amazon_link': f"https://www.amazon.com/gp/product/{entry.findtext('link')}?tag=tharst-20"
        }
        amazon_links_list.append(book_data)
    return amazon_links_list


def extract_recommended_pages(root: ET.Element, category: str, subcategory: str) -> List[Dict]:
    recommended_pages_list = []
    for entry in root.findall(f".//{category}/{subcategory}/entry"):
        page_data = {
            'title': entry.findtext('title'),
            'info': entry.findtext('info'),
            'tas_link': f"https://www.theartstory.org{entry.findtext('link')}"
        }
        recommended_pages_list.append(page_data)
    return recommended_pages_list


def extract_extra_links(root: ET.Element, category_name: str) -> List[Dict]:
    extra_links_list = []
    for entry in root.findall(f'.//category[@name="{category_name}"]/subcategory/entry'):
        link_data = {
            'title': entry.findtext('title'),
            'info': entry.findtext('info'),
            'link': entry.findtext('link')
        }
        extra_links_list.append(link_data)
    return extra_links_list


######################################################

def lazy_load(dictionaries: List) -> Iterator[Document]:
    for i, doc in enumerate(dictionaries):
        page_content = json.dumps(doc, indent=2)
        yield Document(page_content=page_content, metadata={"source": doc['type'], "id": doc['id'], "doc_index": i,
                                                            "json_file": doc["json_file"], "xml_file": doc["xml_file"]})


def images_loader(dictionaries: List) -> Iterator[Document]:
    for i, doc in enumerate(dictionaries):
        page_content = f"{json.dumps(doc['title'], indent=2)} {json.dumps(doc['alternate_title'], indent=2)} " \
                       f"{json.dumps(doc['description'], indent=2)}"
        yield Document(page_content=page_content, metadata={"source": doc['url'], "doc_id": doc['id']})


def iframe_loader(dictionaries: List) -> Iterator[Document]:
    for doc in dictionaries:
        for val in doc.values():
            iframe_url = val['iframe_url']
            page_content = f"{json.dumps(iframe_url, indent=2)} {json.dumps(val['description'], indent=2)}"
            yield Document(page_content=page_content, metadata={"source": iframe_url})


def get_all_images():
    data = []
    for item in os.listdir(JSON_STORE_PATH):
        doc_id = item[:-5]
        file_path = os.path.join(JSON_STORE_PATH, item).replace("\\", "/")
        with open(os.path.join(file_path), "r") as file:
            js_data = json.load(file)
            json_data = js_data[doc_id]
            json_type = js_data['type']
            if json_type == "artist":
                url = f"https://www.theartstory.org/images20/ttip/{doc_id}.jpg"
                title = doc_id.replace("_", " ")
                alternate_title = " ".join(doc_id.split("_")[::-1])
                description = json_data.get('description')
                data.append({"title": title, "description": description.replace("\"", "'"),
                             "alternate_title": alternate_title, "url": url, "id": doc_id})
            sections = json_data.get('sections')
            if sections:
                for section in sections:
                    sub_sections = section.get('sub_sections')
                    for section_id in sub_sections:
                        section_title = section_id.get('title')
                        urls = section_id.get('url')
                        description = section_id.get("content")
                        if urls:
                            for url in urls:
                                data.append({"title": section_title, "description": description.replace("\"", "'"),
                                             "alternate_title": url.get('alt_name'),
                                             "url": url.get('url'), "id": doc_id})
            artworks = json_data.get('artworks')
            if artworks:
                for artwork in artworks:
                    artwork_title = artwork.get('title')
                    artwork_alt_title = " ".join(artwork_title.split()[::-1]) if artwork_title else artwork_title
                    description = artwork.get('description')
                    artwork_url = artwork.get('url')
                    data.append({"title": artwork_title, "description": description.replace("\"", "'"),
                                 "alternate_title": artwork_alt_title,
                                 "url": artwork_url, "id": doc_id})

    with open("data/images.json", "w+") as file:
        file.write(json.dumps(data))


def get_iframe_images():
    data = []
    for item in os.listdir(JSON_STORE_PATH):
        doc_id = item[:-5]
        file_path = os.path.join(JSON_STORE_PATH, item).replace("\\", "/")
        with open(os.path.join(file_path), "r") as file:
            js_data = json.load(file)
            json_data = js_data[doc_id]
            data.append({doc_id: {"iframe_url": json_data['iframe_link'], "description": json_data['synopsis']}})
    with open("data/iframe.json", "w+") as file:
        file.write(json.dumps(data))


def create_json_file(file_name, content):
    try:
        file_path = os.path.join(JSON_STORE_PATH, file_name).replace("\\", "/")
        with open(file_path, 'w+') as json_file:
            json.dump(content, json_file, indent=4)
        print(f"File '{file_name}' created successfully.")
    except Exception as e:
        print(f"An error occurred: {e}")


def create_partial_local_database(vector_store):
    deleted_ids = []
    added_data = []

    actual_data: List[Dict] = create_local_database()
    expected_data: List[Dict] = []
    for file in os.listdir(JSON_STORE_PATH):
        file_name = os.path.join(JSON_STORE_PATH, file).replace("\\", "/")
        with open(file_name, 'w+') as f:
            expected_data.append(json.load(f))

    # Check for deleted files
    actual_file_names = {item.get("json_file") for item in actual_data}
    expected_file_names = {item.get("json_file") for item in expected_data}

    files_to_delete = expected_file_names - actual_file_names
    for file_name in files_to_delete:
        file_path = os.path.join(JSON_STORE_PATH, file_name).replace("\\", "/")
        if os.path.exists(file_path):
            os.remove(file_path)

        for k_id, values in vector_store.docstore._dict.items():
            if file_name == values.metadata['json_file']:
                deleted_ids.append(k_id)

    # Check for added or changed files
    for item in actual_data:
        json_file = item.get("json_file")
        file_path = os.path.join(JSON_STORE_PATH, json_file).replace("\\", "/")
        if item not in expected_data:
            with open(file_path, 'w+') as f:
                json.dump(item, f, indent=4)
            added_data.append(item)
        else:
            expected_item = next((exp_item for exp_item in expected_data if exp_item['json_file'] == json_file), None)
            if expected_item and expected_item != item:
                if os.path.exists(file_path):
                    os.remove(file_path)
                with open(file_path, 'w+') as f:
                    json.dump(item, f, indent=4)
                added_data.append(item)

                for k_id, values in vector_store.docstore._dict.items():
                    if json_file == values.metadata['json_file']:
                        deleted_ids.append(k_id)

    if deleted_ids:
        vector_store.delete(deleted_ids)

    if added_data:
        new_vector_store = get_vector_store(added_data)
        vector_store.merge_from(new_vector_store)
        vector_store.save_local(VECTOR_STORE_PATH)

    return vector_store


def create_local_database() -> List[Dict]:
    data_dict = get_xml_files()

    final_data = []
    for key, values in data_dict.items():
        for value in values:
            root = fetch_and_parse_xml(value)
            if root is not None:
                inner_dict = {}
                if key == 'artist':
                    inner_dict = extract_artist_data(root)
                elif key == 'critic':
                    inner_dict = extract_critic_xml(root)
                elif key == 'definition':
                    inner_dict = extract_definition_xml(root)
                elif key == 'influencer':
                    inner_dict = extract_influencer_data(root)
                elif key == 'movement':
                    inner_dict = extract_movement_data(root)
                file_name = f"{os.path.basename(value)[:-4]}.json"
                inner_dict['json_file'] = file_name
                inner_dict['xml_file'] = value
                final_data.append(inner_dict)
    return final_data


def get_vector_store(data: List[Dict]):
    embeddings = OpenAIEmbeddings()

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=400,
        length_function=len
    )
    split_docs = text_splitter.split_documents(lazy_load(data))
    return FAISS.from_documents(split_docs, embeddings)


def get_image_vector_store(data: List[Dict]):
    embeddings = OpenAIEmbeddings()

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=400,
        length_function=len
    )
    split_docs = text_splitter.split_documents(images_loader(data))
    return FAISS.from_documents(split_docs, embeddings)


def get_iframe_vector_store(data: List[Dict]):
    embeddings = OpenAIEmbeddings()

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=400,
        length_function=len
    )
    split_docs = text_splitter.split_documents(iframe_loader(data))
    return FAISS.from_documents(split_docs, embeddings)


def create_local_vector_store() -> None:
    if os.path.exists(VECTOR_STORE_PATH):
        shutil.rmtree(VECTOR_STORE_PATH)

    if not os.path.exists(JSON_STORE_PATH):
        os.makedirs(JSON_STORE_PATH, exist_ok=True)

    final_data = create_local_database()

    for inner_dict in final_data:
        create_json_file(inner_dict['json_file'], inner_dict)

    vector_store = get_vector_store(final_data)
    vector_store.save_local(VECTOR_STORE_PATH)


def create_image_vector_store() -> None:
    if os.path.exists(IMAGE_STORE_PATH):
        shutil.rmtree(IMAGE_STORE_PATH)

    if not os.path.exists(IMAGE_STORE_PATH):
        os.makedirs(IMAGE_STORE_PATH, exist_ok=True)

    with open("data/images.json") as file:
        final_data = json.load(file)

    vector_store = get_image_vector_store(final_data)
    vector_store.save_local(IMAGE_STORE_PATH)


def create_iframe_vector_store() -> None:
    if os.path.exists(IFRAME_STORE_PATH):
        shutil.rmtree(IFRAME_STORE_PATH)

    if not os.path.exists(IFRAME_STORE_PATH):
        os.makedirs(IFRAME_STORE_PATH, exist_ok=True)

    with open("data/iframe.json") as file:
        final_data = json.load(file)

    vector_store = get_iframe_vector_store(final_data)
    vector_store.save_local(IFRAME_STORE_PATH)


def delete_merged_vector(bucket_name="tas-website-data"):
    # Instantiates a client
    client = storage.Client()

    # Get the bucket
    bucket = client.bucket(bucket_name)

    # List all blobs in the folder
    blobs = bucket.list_blobs(prefix=VECTOR_STORE_PATH)

    # Delete each blob in the folder
    for blob in blobs:
        blob.delete()

    return f"Folder '{VECTOR_STORE_PATH}' deleted successfully."


def upload_merged_vector(bucket_name="tas-website-data"):
    # Instantiates a client
    client = storage.Client()
    # Get the bucket
    bucket = client.bucket(bucket_name)

    # Creating a Folder in Bucket
    bucket.blob(VECTOR_STORE_PATH)

    # List all files in the local folder
    local_files = os.listdir(VECTOR_STORE_PATH)

    # Upload each file to the cloud folder
    for local_file in local_files:
        local_file_path = os.path.join(VECTOR_STORE_PATH, local_file)
        cloud_file_path = os.path.join(VECTOR_STORE_PATH, local_file)

        cloud_file_path = cloud_file_path.replace("\\", "/")

        blob = bucket.blob(cloud_file_path)
        blob.upload_from_filename(local_file_path)

        print(f"File {local_file} uploaded to {cloud_file_path}.")


if __name__ == '__main__':
    import sys

    print("Executing vector refresh")
    vector_update_status = sys.argv[1]
    # Loading environment variables OPENAI_API_KEY is must
    load_dotenv()
    start_time = time.time()
    if vector_update_status == "initial_cloud_refresh":
        # creating local vector store
        create_local_vector_store()
        # deleting vector store from cloud
        delete_merged_vector()
        # uploading vector store from local to cloud
        upload_merged_vector()
    elif vector_update_status == "local_refresh":
        # It would take approximate 40 minutes to generate new vector store for whole xml files
        # creating local vector store
        create_local_vector_store()
    elif vector_update_status == "partial_cloud_refresh":
        # check if there is any change happened in xml files
        embeddings = OpenAIEmbeddings()
        vectorstore = None
        if os.path.exists(VECTOR_STORE_PATH):
            vectorstore = FAISS.load_local(VECTOR_STORE_PATH, embeddings, allow_dangerous_deserialization=True)
        else:
            raise ValueError("data/vector_store should exists")
        create_partial_local_database(vectorstore)
        # add or remove json file based on changes
        # if changes happened then please update the vector store
    elif vector_update_status == "iframe_vector_refresh":
        get_iframe_images()
        create_iframe_vector_store()

    elif vector_update_status == "image_vector_refresh":
        get_all_images()
        create_image_vector_store()

    print(f"Execution took {time.time() - start_time} seconds")
