from googleapiclient.discovery import build
from dotenv import load_dotenv
import os
load_dotenv()
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
def get_youtube_client():
    return build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
