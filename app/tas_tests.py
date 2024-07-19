import time
import unittest
from fastapi.testclient import TestClient
from main import app
from db import logger

client = TestClient(app)


class TestAPIs(unittest.TestCase):

    def test_get_valid_data_id(self):
        response = client.post("/get_valid_data_id", json={
            "data_ids": ["british_art", "black_arts_movement", "installation_art", "guerrilla_girls",
                         "abstract_expressionism", "british_pop_art", "french_art", "school_of_london"],
            "chunk": "Leonardo da Vinci was a quintessential Renaissance man, excelling in various fields "
                     "including art, science, engineering, and anatomy. His works are celebrated for their "
                     "intricate detail, innovative techniques, and profound understanding of human "
                     "anatomy and emotion. "
        })
        logger.info(f"Response: {response.json()}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("best_match_file", response.json())

    def test_generate_response(self):
        user_query = "Who is pablo Picasso?"
        response = client.post("/generate_response", json={
            "query": f"%info% You are an expert in Arts. % %query% {user_query} % %instructions% medium %",
            "responseLength": "medium",
            "session_id": f"session_id_{time.time()}"
        })
        self.assertEqual(response.status_code, 200)
        for chunk in response.iter_bytes():
            if chunk:
                logger.info(chunk.decode('utf-8'))

    def test_get_urls(self):
        response = client.post("/get_urls", json={
            "data_id": "french_art",
            "chunk": "Leonardo da Vinci (1452-1519)**\n**Medium:** Drawing, Painting, Sculpture, and more.\n**Key "
                     "Works:** \"Mona Lisa,\" \"The Last Supper,\" \"Vitruvian Man.\"\n**Overview:** Leonardo da "
                     "Vinci was a quintessential Renaissance man, excelling in various fields including art, "
                     "science, engineering, and anatomy. His works are celebrated for their intricate detail, "
                     "innovative techniques, and profound understanding of human anatomy and emotion. \"Mona Lisa\" "
                     "is perhaps the most famous painting in the world, known for its enigmatic smile and masterful "
                     "use of sfumato."
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("urls", response.json())
        logger.info(f"Response: {response.json()}")

    def test_get_iframe_link(self):
        response = client.post("/get_iframe_link", json={
            "data_id": "french_art"
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("iframe", response.json())
        logger.info(f"Response: {response.json()}")

    def test_get_artist_image_link(self):
        response = client.post("/get_artist_image_link", json={
            "data_id": "avedon_richard"
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("artist", response.json())
        logger.info(f"Response: {response.json()}")

    def test_get_source_link(self):
        response = client.post("/get_source_link", json={
            "data_id": "french_art"
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("source", response.json())
        logger.info(f"Response: {response.json()}")


if __name__ == '__main__':
    unittest.main()
