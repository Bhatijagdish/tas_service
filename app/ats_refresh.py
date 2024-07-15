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

vector_store_path = "data/vector_store/"
json_store_path = "data/json_files/"


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
        print(path)

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
        yield Document(page_content=page_content, metadata={"source": doc['type'], "id": doc['id'], "doc_index": i})


def create_local_database() -> List[Dict]:
    data_dict = get_xml_files()

    final_data = []
    for key, values in data_dict.items():
        for value in values:
            root = fetch_and_parse_xml(value)
            # file_name = f"{os.path.basename(value)[:-4]}.json"
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
                final_data.append(inner_dict)
    return final_data


def create_local_vector_store() -> None:

    if not os.path.exists(json_store_path):
        os.makedirs(json_store_path, exist_ok=True)

    final_data = create_local_database()

    embeddings = OpenAIEmbeddings()

    if os.path.exists(vector_store_path):
        os.remove(vector_store_path)

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=400,
        length_function=len
    )
    split_docs = text_splitter.split_documents(lazy_load(final_data))
    vector_store = FAISS.from_documents(split_docs, embeddings)
    vector_store.save_local(vector_store_path)


# def generate_streaming_response(query: str, extracted_dict: Dict, docs: List[Document]):
#     PREFIX = "INFO: You are Prof expert on art history. " \
#              "You will answer the questions asked in details " \
#              "and provide correct responses."
#
#     input_query = f"Main question is : {query}\n\n" \
#                   f"This is the context: {'.'.join(doc.page_content for doc in docs)}\n"
#
#     response = client.chat.completions.create(
#         model="gpt-4o",
#         messages=[
#             {"role": "system", "content": PREFIX},
#             {"role": "user", "content": input_query}
#         ],
#         temperature=0,
#         stream=True
#     )
#
#     temp_dicts = []
#     metadata = []
#     counter = 0
#     result = {"chat_id": None, "text_message": "", "data_id": None}
#     for chunk in response:
#         result['chat_id'] = chunk.id
#         chunk_message = chunk.choices[0].delta.content  # Extract the message
#         if chunk_message:
#             result['text_message'] += chunk_message
#             if '\n' in result['text_message']:
#                 message = result['text_message']
#                 chunks = message.split('\n')
#                 final_chunk = chunks[counter]
#                 counter = min(counter + 1, len(chunks) - 1)
#                 if len(final_chunk) > 200:
#                     dict_output = extract_highest_ratio_dict(extracted_dict, final_chunk)
#                     if dict_output and dict_output not in temp_dicts:
#                         temp_dicts.append(dict_output)
#                         metadata.append(dict_output.get('url', None))
#                         result['metadata'] = {'urls': metadata,
#                                               'iframe': extracted_dict.get('iframe_link', None),
#                                               'artist': extracted_dict.get('artist_image', None),
#                                               'source': extracted_dict.get('source_link', None)
#                                               }
#             yield result
#

def delete_merged_vector(bucket_name="tas-website-data"):
    # Instantiates a client
    client = storage.Client()

    # Get the bucket
    bucket = client.bucket(bucket_name)

    # List all blobs in the folder
    blobs = bucket.list_blobs(prefix=vector_store_path)

    # Delete each blob in the folder
    for blob in blobs:
        blob.delete()

    return f"Folder '{vector_store_path}' deleted successfully."


def upload_merged_vector(bucket_name="tas-website-data"):
    # Instantiates a client
    client = storage.Client()

    # Get the bucket
    bucket = client.bucket(bucket_name)

    # Creating a Folder in Bucket
    bucket.blob(vector_store_path)

    # List all files in the local folder
    local_files = os.listdir(vector_store_path)

    # Upload each file to the cloud folder
    for local_file in local_files:
        local_file_path = os.path.join(vector_store_path, local_file)
        cloud_file_path = os.path.join(vector_store_path, local_file)

        cloud_file_path = cloud_file_path.replace("\\", "/")

        blob = bucket.blob(cloud_file_path)
        blob.upload_from_filename(local_file_path)

        print(f"File {local_file} uploaded to {cloud_file_path}.")


if __name__ == '__main__':
    import sys
    vector_update_status = sys.argv[1]
    if vector_update_status == "refresh":
        # Loading environment variables OPENAI_API_KEY is must
        load_dotenv()
        # creating local vector store
        create_local_vector_store()
        # deleting vector store from cloud
        delete_merged_vector()
        # uploading vector store from local to cloud
        upload_merged_vector()
