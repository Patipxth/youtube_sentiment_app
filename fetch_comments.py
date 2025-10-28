from googleapiclient.discovery import build  # ใช้สำหรับเรียกใช้ YouTube Data API
import random  # ใช้สำหรับสุ่มคอมเมนต์จากลิสต์
import re  # ใช้สำหรับทำ regex หา video ID
import os  # ใช้สำหรับเข้าถึง environment variables
from dotenv import load_dotenv  # ใช้สำหรับโหลดค่าจากไฟล์ .env

# โหลด environment variables จากไฟล์ .env เช่น API key
load_dotenv()

# ดึงค่า YouTube API key จาก environment variable
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

def extract_video_id(url: str) -> str:
    """
    แยก Video ID จากลิงก์ YouTube ที่หลายรูปแบบ เช่น
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    """
    # ใช้ regex หา video ID ซึ่งมักมีความยาว 11 ตัวอักษร
    pattern = r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})"
    match = re.search(pattern, url)
    return match.group(1) if match else None  # คืนค่า video ID ถ้าพบ มิฉะนั้นคืน None

def fetch_video_details_by_id(video_id: str) -> dict:
    """
    รับ video_id แล้วไปดึงข้อมูลของวิดีโอนั้น เช่น ชื่อเรื่อง และ thumbnail
    """
    if not YOUTUBE_API_KEY:
        raise ValueError("YouTube API Key is not set.")  # แจ้ง error หากไม่มี API key

    # สร้าง YouTube API client object
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

    # เรียก API เพื่อดึงข้อมูลวิดีโอ (title และ thumbnails)
    request = youtube.videos().list(
        part='snippet',  # ขอข้อมูลเฉพาะ snippet
        id=video_id
    )
    response = request.execute()

    if response and response['items']:
        snippet = response['items'][0]['snippet']
        return {
            "title": snippet['title'],  # ดึงชื่อวิดีโอ
            "thumbnail": snippet['thumbnails']['medium']['url']  # ดึงรูป thumbnail ขนาดกลาง (หรือใช้ 'high')
        }
    return {}  # ถ้าไม่เจอวิดีโอ คืน dict ว่าง

def fetch_comments_from_youtube(video_url: str, max_comments: int = 200) -> list:
    """
    ดึงคอมเมนต์จากวิดีโอ YouTube ที่ให้มา
    โดยใช้ YouTube API เพื่อดึงคอมเมนต์แบบ plain text
    และสุ่มเลือกไม่เกินจำนวนที่กำหนด
    """
    video_id = extract_video_id(video_url)
    if not video_id:
        raise ValueError("ไม่พบ video ID จาก URL ที่ให้มา")  # ตรวจสอบว่าแยก video ID ได้ไหม

    # สร้าง YouTube API client object
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    comments = []
    next_page_token = None  # ใช้สำหรับดึงหน้าถัดไปของคอมเมนต์

    # วนลูปเพื่อดึงคอมเมนต์จนกว่าจะครบหรือไม่มีหน้าถัดไป
    while len(comments) < max_comments:
        # เรียก API เพื่อดึงคอมเมนต์
        request = youtube.commentThreads().list(
            part='snippet',  # ขอข้อมูลเฉพาะ snippet
            videoId=video_id,  # ID ของวิดีโอ
            maxResults=100,  # YouTube API จำกัดไม่เกิน 100 ต่อ request
            pageToken=next_page_token,  # สำหรับไปยังหน้าถัดไป
            textFormat='plainText'  # ขอคอมเมนต์ในรูปแบบ plain text
        )
        response = request.execute()

        # วนลูปดึงคอมเมนต์จาก response
        for item in response['items']:
            comment = item['snippet']['topLevelComment']['snippet']['textDisplay']
            comments.append(comment)
            if len(comments) >= max_comments:
                break  # ถ้าครบจำนวนที่ต้องการแล้วให้หยุด

        # ดูว่า API ให้ token สำหรับหน้าถัดไปมาหรือไม่
        next_page_token = response.get('nextPageToken')
        if not next_page_token:
            break  # ถ้าไม่มีหน้าถัดไปแล้วก็หยุด

    # สุ่มเลือกคอมเมนต์จากทั้งหมดที่ได้ โดยไม่เกินจำนวนที่กำหนด
    return random.sample(comments, min(len(comments), max_comments))
