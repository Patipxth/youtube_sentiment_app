from googleapiclient.discovery import build
import random
import re
import os
from dotenv import load_dotenv
from datetime import timedelta # For parsing ISO 8601 duration

# โหลดค่า environment จากไฟล์ .env
load_dotenv()

# ดึง API Key สำหรับ YouTube จาก environment variables
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# --- ฟังก์ชัน extract_video_id ---
def extract_video_id(url: str) -> str:
    """
    ดึง Video ID จากลิงก์ YouTube โดยรองรับหลายรูปแบบ URL
    """
    pattern = r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})"
    match = re.search(pattern, url)
    return match.group(1) if match else None

# --- ฟังก์ชัน fetch_video_details_by_id ---
def fetch_video_details_by_id(video_id: str) -> dict:
    """
    ดึงชื่อและปกคลิปสำหรับ Video ID ที่ระบุ
    """
    if not YOUTUBE_API_KEY:
        raise ValueError("YouTube API Key is not set.")

    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    request = youtube.videos().list(
        part='snippet',
        id=video_id
    )
    response = request.execute()

    if response and response['items']:
        snippet = response['items'][0]['snippet']
        return {
            "title": snippet['title'],
            "thumbnail": snippet['thumbnails'].get('medium', {}).get('url', '') or \
                         snippet['thumbnails'].get('high', {}).get('url', '') or \
                         snippet['thumbnails'].get('default', {}).get('url', 'https://placehold.co/480x360/E0E0E0/6C757D?text=No+Thumbnail')
        }
    return {}

# --- ฟังก์ชัน fetch_comments_from_youtube ---
def fetch_comments_from_youtube(video_url: str, max_comments: int = 200) -> list:
    """
    ดึงคอมเมนต์จากวิดีโอ YouTube โดยใช้ API และสุ่มเลือกตามจำนวนที่กำหนด
    """
    video_id = extract_video_id(video_url)
    if not video_id:
        raise ValueError("ไม่พบ video ID จาก URL ที่ให้มา")

    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    comments = []
    next_page_token = None

    while len(comments) < max_comments:
        request = youtube.commentThreads().list(
            part='snippet',
            videoId=video_id,
            maxResults=100, # API limit per request
            pageToken=next_page_token,
            textFormat='plainText'
        )
        response = request.execute()

        for item in response['items']:
            comment = item['snippet']['topLevelComment']['snippet']['textDisplay']
            comments.append(comment)
            if len(comments) >= max_comments:
                break

        next_page_token = response.get('nextPageToken')
        if not next_page_token:
            break

    return random.sample(comments, min(len(comments), max_comments))

# --- ฟังก์ชัน extract_channel_id ---
def extract_channel_id(url: str) -> str:
    """
    ดึง Channel ID จาก URL โดยรองรับหลายรูปแบบ
    """
    match_channel_id = re.search(r"youtube\.com/(?:channel/|@)([a-zA-Z0-9_-]{24})", url)
    if match_channel_id:
        return match_channel_id.group(1)

    match_user_or_custom = re.search(r"youtube\.com/(?:user/|c/|@)([^/]+)", url)
    if match_user_or_custom:
        identifier = match_user_or_custom.group(1)
        return get_channel_id_from_identifier(identifier)

    return None

# --- ฟังก์ชัน get_channel_id_from_identifier ---
def get_channel_id_from_identifier(identifier: str) -> str:
    """
    ดึง Channel ID จากชื่อผู้ใช้หรือ custom URL ด้วย YouTube API
    """
    if not YOUTUBE_API_KEY:
        raise ValueError("YouTube API Key is not set.")

    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

    request = youtube.channels().list(part='id', forHandle=identifier)
    response = request.execute()
    if response and response['items']:
        return response['items'][0]['id']

    request = youtube.channels().list(part='id', forUsername=identifier)
    response = request.execute()
    if response and response['items']:
        return response['items'][0]['id']

    return None

# --- ฟังก์ชัน fetch_channel_details ---
def fetch_channel_details(channel_id: str) -> dict:
    """
    ดึงข้อมูลโปรไฟล์ของ channel เช่น ชื่อ รูป และจำนวนผู้ติดตาม
    """
    if not YOUTUBE_API_KEY:
        raise ValueError("YouTube API Key is not set.")

    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    request = youtube.channels().list(part='snippet,statistics', id=channel_id)
    response = request.execute()

    if response and response['items']:
        snippet = response['items'][0]['snippet']
        statistics = response['items'][0]['statistics']

        subscriber_count_raw = statistics.get('subscriberCount')
        subscriber_count = int(subscriber_count_raw) if subscriber_count_raw and subscriber_count_raw.isdigit() else 'N/A'

        return {
            "channel_name": snippet['title'],
            "channel_thumbnail": snippet['thumbnails']['default']['url'],
            "subscriber_count": subscriber_count
        }
    return {}

# Helper function to parse ISO 8601 duration
def parse_duration(iso_duration: str) -> timedelta:
    """Parses an ISO 8601 duration string into a timedelta object."""
    # Example: PT1H2M3S (1 hour, 2 minutes, 3 seconds)
    # This is a simplified parser and might not handle all edge cases
    # For robust parsing, consider using a dedicated library like 'isodate'
    
    # Regex to extract components
    match = re.match(r'P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', iso_duration)
    if not match:
        return timedelta(0) # Return zero timedelta if format is unexpected

    days = int(match.group(1)) if match.group(1) else 0
    hours = int(match.group(2)) if match.group(2) else 0
    minutes = int(match.group(3)) if match.group(3) else 0
    seconds = int(match.group(4)) if match.group(4) else 0

    return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)


# --- ฟังก์ชัน fetch_channel_videos ---
def fetch_channel_videos(channel_id: str, max_results_per_page: int = 50, page_token: str = None) -> tuple[list, str]:
    """
    ดึงวิดีโอจาก channel และระบุประเภท (ปกติ, ไลฟ์สด, Shorts) อย่างแม่นยำขึ้น
    """
    if not YOUTUBE_API_KEY:
        raise ValueError("YouTube API Key is not set.")

    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    
    # Step 1: Use search().list to get a list of video IDs and basic snippets
    search_request = youtube.search().list(
        part='snippet',
        channelId=channel_id,
        type='video',
        order='date',
        maxResults=max_results_per_page,
        pageToken=page_token
    )
    search_response = search_request.execute()

    video_ids = [item['id']['videoId'] for item in search_response['items'] if item['id']['kind'] == 'youtube#video']
    
    all_videos_with_type = []

    if video_ids:
        # Step 2: Use videos().list to get detailed info (liveStreamingDetails, contentDetails) for accurate typing
        videos_request = youtube.videos().list(
            part='snippet,liveStreamingDetails,contentDetails',
            id=','.join(video_ids) # Join all video IDs for a single request
        )
        videos_response = videos_request.execute()

        video_details_map = {item['id']: item for item in videos_response['items']}

        for item in search_response['items']: # Iterate through search results to maintain order
            if item['id']['kind'] != 'youtube#video':
                continue

            video_id = item['id']['videoId']
            title = item['snippet']['title']
            
            # Get thumbnail, prioritize medium, then high, then default, then placeholder
            thumbnail = item['snippet']['thumbnails'].get('medium', {}).get('url') or \
                        item['snippet']['thumbnails'].get('high', {}).get('url') or \
                        item['snippet']['thumbnails'].get('default', {}).get('url') or \
                        'https://placehold.co/480x360/E0E0E0/6C757D?text=No+Thumbnail'

            video_type = "ปกติ" # Default type

            # Use detailed video info if available
            detailed_video = video_details_map.get(video_id)
            if detailed_video:
                # Check for Live Stream
                live_details = detailed_video.get('liveStreamingDetails')
                if live_details:
                    # If it has liveStreamingDetails, it's a live video (past or current)
                    video_type = "ไลฟ์สด"
                else:
                    # Check for Shorts based on duration (less than 60 seconds)
                    content_details = detailed_video.get('contentDetails')
                    if content_details and 'duration' in content_details:
                        try:
                            # Parse ISO 8601 duration (e.g., PT1M30S)
                            duration_td = parse_duration(content_details['duration'])
                            if duration_td.total_seconds() < 60: # Shorts are typically under 60 seconds
                                video_type = "Shorts"
                        except Exception as e:
                            print(f"Warning: Could not parse duration for video {video_id}: {e}")
                            # Fallback to normal if duration parsing fails

            video_info = {
                "video_id": video_id,
                "title": title,
                "thumbnail": thumbnail,
                "video_url": f"https://www.youtube.com/watch?v={video_id}",
                "video_type": video_type # Add the determined type
            }
            all_videos_with_type.append(video_info)
    
    next_page_token = search_response.get('nextPageToken')
            
    # Return a single list of all videos with their determined type
    return all_videos_with_type, next_page_token
