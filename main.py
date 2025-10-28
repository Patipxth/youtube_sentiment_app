from fastapi import FastAPI, Request, Form, Query # เพิ่ม Query สำหรับ load_more_channel_videos
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import os
from dotenv import load_dotenv
import httpx
# Import specific exceptions from httpx.exceptions
from httpx import _exceptions as httpx_exceptions # แก้ไขตรงนี้: เปลี่ยน exceptions เป็น _exceptions
import openai # นำเข้าไลบรารี OpenAI
import tiktoken # นำเข้าไลบรารี tiktoken สำหรับการนับโทเค็น

# Load environment variables
load_dotenv()

# Ensure these imports are correct based on your file structure
from fetch_comments import fetch_comments_from_youtube, extract_video_id, fetch_video_details_by_id
from translate_text import translate_to_thai
from clean_text import clean_comments
from predict_sentiment import predict_sentiment
from fetch_channel_data import extract_channel_id, fetch_channel_details, fetch_channel_videos, get_channel_id_from_identifier # เพิ่ม get_channel_id_from_identifier

# --- API Key Configuration Check ---
# For local testing, ensure these are set in your .env file
YOUTUBE_API_KEY_CHECK = os.getenv("YOUTUBE_API_KEY")
OPENAI_API_KEY_CHECK = os.getenv("OPENAI_API_KEY") # Read OpenAI API key from .env

# OpenAI client initialization
openai_client = None
if not OPENAI_API_KEY_CHECK:
    print("WARNING: ไม่พบ OPENAI_API_KEY ในไฟล์ .env โปรดตั้งค่า API Key ของคุณ")
    print("ตัวอย่าง: OPENAI_API_KEY=YOUR_OPENAI_API_KEY_HERE")
else:
    openai_client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY_CHECK)


app = FastAPI()

# Templates and static files
# แก้ไขพาธของ Templates กลับไปที่ "frontend"
BASE_DIR = os.path.dirname(__file__)
static_path = os.path.join(BASE_DIR, "static")
app.mount("/static", StaticFiles(directory=static_path), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "frontend")) 

# --- ฟังก์ชันสำหรับตัดข้อความตามจำนวนโทเค็น ---
def truncate_text_by_tokens(text: str, max_tokens: int, model_name: str = "gpt-3.5-turbo") -> str:
    """
    ตัดข้อความที่กำหนดให้มีจำนวนโทเค็นไม่เกินที่ระบุ โดยใช้ tiktoken
    """
    try:
        encoding = tiktoken.encoding_for_model(model_name)
    except KeyError:
        # Fallback ไปยัง encoding พื้นฐานหากไม่พบ model_name
        encoding = tiktoken.get_encoding("cl100k_base")

    encoded_text = encoding.encode(text)
    
    if len(encoded_text) > max_tokens:
        truncated_encoded_text = encoded_text[:max_tokens]
        truncated_text = encoding.decode(truncated_encoded_text)
        # เพิ่ม ... เพื่อบ่งชี้ว่าข้อความถูกตัด
        return truncated_text + "..."
    return text

# --- ฟังก์ชันสำหรับสรุปข้อความด้วย OpenAI API ---
async def summarize_with_openai(text_to_summarize: str, openai_client: openai.AsyncOpenAI) -> str:
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "คุณคือผู้ช่วยวิเคราะห์ความคิดเห็นของผู้ชมจาก YouTube "
                        "โดยจะต้องสรุปแนวโน้มความรู้สึกหลัก (เชิงบวก/ลบ/เป็นกลาง) "
                        "และประเด็นสำคัญที่ถูกพูดถึงในคอมเมนต์ โดยเขียนให้อ่านง่ายและเป็นทางการ"
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"ต่อไปนี้คือความคิดเห็นของผู้ชมจากวิดีโอ YouTube :\n\n{text_to_summarize}\n\n"
                        "โปรดสรุปภาพรวมของความคิดเห็นเหล่านี้ว่าโดยรวมมีแนวโน้มไปทางใด "
                        "(เช่น ส่วนใหญ่ชื่นชอบ, เศร้า, มีการวิจารณ์ ฯลฯ) "
                        "และมีประเด็นใดบ้างที่ถูกกล่าวถึงบ่อย โดยเขียนให้กระชับ ภายใน 100 คำ"
                    )
                }
            ],
            max_tokens=512,
            temperature=0.5,  
        )
        result = response.choices[0].message.content.strip()
        return result
    except Exception as e:
        print(f"เกิดข้อผิดพลาดระหว่างสรุปความคิดเห็น: {e}")
        return "ไม่สามารถสรุปความคิดเห็นได้ในขณะนี้"

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """
    Handles the root URL and renders the main index page for sentiment analysis.
    """
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/analyze", response_class=HTMLResponse)
async def analyze(
    request: Request,
    input_url: str = Form(...),
    analysis_mode: str = Form(...),
    channel_id: str = Form(None), # รับ channel_id เพิ่มเติม
    channel_url: str = Form(None) # รับ channel_url เพิ่มเติม
):
    print(f"DEBUG: รับคำขอวิเคราะห์แล้วสำหรับ URL: {input_url}, โหมด: {analysis_mode}")
    # เพิ่มการ Debugging สำหรับ channel_id และ channel_url
    print(f"DEBUG: channel_id ที่ได้รับ: {channel_id}")
    print(f"DEBUG: channel_url ที่ได้รับ: {channel_url}")

    if not YOUTUBE_API_KEY_CHECK:
        print("ERROR: ไม่พบ YouTube API Key.")
        return templates.TemplateResponse("error.html", {
            "request": request,
            "message": "ข้อผิดพลาด: ไม่พบ YouTube API Key โปรดตรวจสอบไฟล์ .env ของคุณ"
        }, status_code=500)

    original_comments = []
    sentiment_results = []
    
    positive_count = 0
    negative_count = 0
    neutral_count = 0
    overall_summary = "" # จะถูกสร้างโดย OpenAI
    video_title = "ไม่พบชื่อวิดีโอ"
    video_thumbnail = ""

    try:
        if analysis_mode == "video":
            # ตรวจสอบว่าฟังก์ชันที่จำเป็นสำหรับการวิเคราะห์ Sentiment พร้อมใช้งานหรือไม่
            if not all([fetch_comments_from_youtube, extract_video_id, fetch_video_details_by_id, translate_to_thai, clean_comments, predict_sentiment]):
                return templates.TemplateResponse("error.html", {
                    "request": request,
                    "message": "ฟังก์ชันสำหรับการวิเคราะห์ Sentiment ยังไม่พร้อมใช้งาน โปรดตรวจสอบการนำเข้า"
                }, status_code=500)

            video_id = extract_video_id(input_url)
            if not video_id:
                print(f"ERROR:ไม่พบ Video ID จาก URL: {input_url}")
                return templates.TemplateResponse("error.html", {
                    "request": request,
                    "message": "ไม่พบ Video ID จาก URL ที่ให้มา กรุณาตรวจสอบลิงก์วิดีโอ YouTube"
                }, status_code=400)
            print(f"DEBUG: Video ID ที่ดึงได้: {video_id}")

            video_details = fetch_video_details_by_id(video_id)
            target_title = video_details.get("title", "ไม่พบชื่อวิดีโอ") if video_details else "ไม่พบชื่อวิดีโอ"
            target_thumbnail = video_details.get("thumbnail", "https://placehold.co/480x360/E0E0E0/6C757D?text=No+Thumbnail") if video_details else "https://placehold.co/480x360/E0E0E0/6C757D?text=No+Thumbnail"
            analysis_source_link = input_url
            print(f"DEBUG:รายละเอียดวิดีโอ: ชื่อ='{target_title}', Thumbnail='{target_thumbnail}'")

            original_comments_raw = fetch_comments_from_youtube(input_url, max_comments=200)
            print(f"DEBUG:จำนวนความคิดเห็นที่ดึงมาจากYouTube (ดิบ): {len(original_comments_raw) if original_comments_raw else 0} รายการ")
            
            comments_for_template = []
            positive_count = 0
            negative_count = 0
            neutral_count = 0
            total_comments_analyzed = 0
            total_comments_skipped_by_length = 0

            if original_comments_raw:
                # แก้ไข: เพิ่ม await และส่ง openai_client
                translated_comments_raw = await translate_to_thai(original_comments_raw, openai_client)
                print(f"DEBUG:จำนวนความคิดเห็นหลังการแปล: {len(translated_comments_raw)} รายการ")
                
                MAX_CHAR_LENGTH_FOR_SENTIMENT = 700 
                
                comments_to_process_translated = []
                original_comments_to_display = []
                
                for i, translated_comment_text in enumerate(translated_comments_raw):
                    current_original_comment = original_comments_raw[i] 
                    
                    if len(translated_comment_text) <= MAX_CHAR_LENGTH_FOR_SENTIMENT:
                        comments_to_process_translated.append(translated_comment_text)
                        original_comments_to_display.append(current_original_comment)
                    else:
                        total_comments_skipped_by_length += 1
                        comments_for_template.append({
                            "text": current_original_comment,
                            "sentiment": "เกินขีดจำกัดความยาว (ข้าม)",
                        })
                
                print(f"DEBUG:จำนวนความคิดเห็นที่ผ่านการกรองความยาวตัวอักษร (ที่จะนำไปวิเคราะห์): {len(comments_to_process_translated)}รายการ")
                print(f"DEBUG:จำนวนความคิดเห็นที่ถูกข้ามเนื่องจากความยาว (ตัวอักษร): {total_comments_skipped_by_length} รายการ")

                if comments_to_process_translated:
                    cleaned_comments = clean_comments(comments_to_process_translated)
                    print(f"DEBUG: จำนวนความคิดเห็นหลังการทำความสะอาด (ที่ผ่านการกรองแล้ว): {len(cleaned_comments)} รายการ")
                    
                    try:
                        sentiment_results = predict_sentiment(cleaned_comments)
                        print(f"DEBUG: จำนวนผลลัพธ์ Sentiment ที่ได้จาก predict_sentiment: {len(sentiment_results)}รายการ")
                    except Exception as sentiment_err:
                        print(f"ERROR: เกิดข้อผิดพลาดใน predict_sentiment: {sentiment_err}")
                        sentiment_results = []
                        print(f"DEBUG: sentiment_results ถูกตั้งเป็นค่าว่างเปล่าเนื่องจากข้อผิดพลาดใน predict_sentiment")

                    for original_comment_text, sentiment_info in zip(original_comments_to_display, sentiment_results):
                        if sentiment_info and 'label' in sentiment_info:
                            sentiment_label = sentiment_info.get('label', 'unknown')
                            comments_for_template.append({
                                "text": original_comment_text,
                                "sentiment": sentiment_label,
                            })
                            if sentiment_label == 'positive':
                                positive_count += 1
                            elif sentiment_label == 'negative':
                                negative_count += 1
                            elif sentiment_label == 'neutral':
                                neutral_count += 1
                            total_comments_analyzed += 1
                        else:
                            comments_for_template.append({
                                "text": original_comment_text,
                                "sentiment": "ไม่สามารถวิเคราะห์ได้",
                            })
                else:
                    overall_summary = f"ไม่มีความคิดเห็นที่สั้นพอสำหรับการวิเคราะห์จากทั้งหมด {len(original_comments_raw)} รายการ"
                    print("DEBUG: ไม่มีความคิดเห็นที่ผ่านการกรองความยาวตัวอักษร")
                
                # Combine comments for summarization
                MAX_COMMENTS_FOR_SUMMARY = 100 
                MAX_CHAR_LENGTH_FOR_SUMMARY_COMMENT = 120 

                comments_for_openai_summary = []
                for comment in original_comments_to_display[:MAX_COMMENTS_FOR_SUMMARY]:
                    if len(comment) > MAX_CHAR_LENGTH_FOR_SUMMARY_COMMENT:
                        comments_for_openai_summary.append(comment[:MAX_CHAR_LENGTH_FOR_SUMMARY_COMMENT] + "...")
                    else:
                        comments_for_openai_summary.append(comment)

                comments_text_for_summary_raw = "\n".join(comments_for_openai_summary)
                
                MAX_INPUT_TOKENS_FOR_SUMMARY = 15000 
                comments_text_for_summary = truncate_text_by_tokens(
                    comments_text_for_summary_raw, MAX_INPUT_TOKENS_FOR_SUMMARY, "gpt-3.5-turbo"
                )
                print(f"DEBUG: ความยาวของข้อความสำหรับสรุปหลังการตัด (อักขระ): {len(comments_text_for_summary)}")

                # เรียกใช้ OpenAI API เพื่อสรุปความคิดเห็น
                if comments_text_for_summary and OPENAI_API_KEY_CHECK:
                    overall_summary = await summarize_with_openai(
                     comments_text_for_summary,
                     openai_client
                )

                elif not OPENAI_API_KEY_CHECK:
                    overall_summary = "ไม่สามารถสร้างสรุปความคิดเห็นได้ (ไม่พบ OpenAI API Key)"
                else:
                    overall_summary = "ไม่พบความคิดเห็นที่เพียงพอสำหรับสรุป"

                print(f"DEBUG:สรุปผลการวิเคราะห์: Positive={positive_count}, Negative={negative_count}, Neutral={neutral_count}, Analyzed={total_comments_analyzed}, Skipped={total_comments_skipped_by_length}")
                print(f"DEBUG:จำนวน comments_for_template ที่เตรียมไว้สำหรับ HTML (รวมที่ข้าม): {len(comments_for_template)}")

            else:
                overall_summary = "ไม่พบความคิดเห็นสำหรับวิดีโอนี้ หรือ API มีข้อจำกัด"
                print("DEBUG:ไม่พบความคิดเห็นจาก YouTube ตั้งแต่แรก")

            return templates.TemplateResponse("result.html", {
                "request": request,
                "analysis_mode": analysis_mode,
                "input_url": input_url,
                "video_title": target_title,
                "video_thumbnail": target_thumbnail,
                "analysis_source_link": analysis_source_link,
                "comments": comments_for_template,
                "positive_count": positive_count,
                "negative_count": negative_count,
                "neutral_count": neutral_count,
                "total_comments": len(original_comments_raw) if original_comments_raw else 0,
                "overall_summary": overall_summary,
                "channel_id": channel_id,
                "channel_url": channel_url 
            })

        elif analysis_mode == "channel":
            print(f"DEBUG:เข้าสู่โหมดวิเคราะห์ Channel สำหรับ URL: {input_url}")
            channel_id = extract_channel_id(input_url)
            if not channel_id:
                print(f"ERROR:ไม่พบ Channel ID จาก URL: {input_url}")
                return templates.TemplateResponse("error.html", {
                    "request": request,
                    "message": "ไม่พบ Channel ID จาก URL ที่ให้มา กรุณาตรวจสอบลิงก์ช่อง YouTube"
                }, status_code=400)
            print(f"DEBUG: Channel ID ที่ดึงได้: {channel_id}")
            
            channel_details = fetch_channel_details(channel_id)
            if not channel_details:
                print(f"ERROR:ไม่พบข้อมูลช่อง YouTube สำหรับ Channel ID: {channel_id}")
                return templates.TemplateResponse("error.html", {
                    "request": request,
                    "message": "ไม่พบข้อมูลช่อง YouTube นี้ กรุณาตรวจสอบ Channel ID หรือ URL"
                }, status_code=404)
            print(f"DEBUG:ดึงข้อมูลช่อง: {channel_details.get('channel_name', 'ไม่ระบุ')}") 

            # ดึงวิดีโอชุดแรก (50 คลิป) - fetch_channel_videos ตอนนี้คืนค่าเป็น list ของวิดีโอทั้งหมด
            all_videos, next_page_token = fetch_channel_videos(channel_id, max_results_per_page=50) # ใช้ 50 เป็นค่าเริ่มต้น
            print(f"DEBUG: ดึงวิดีโอช่องได้: {len(all_videos)} รายการ")
            
            return templates.TemplateResponse("channel_videos.html", {
                "request": request,
                "channel_details": channel_details,
                "all_videos": all_videos, # ส่งลิสต์วิดีโอทั้งหมด
                "next_page_token": next_page_token,
                "channel_id": channel_id,
                "channel_url": input_url
            })

        else:
            print(f"ERROR:โหมดการวิเคราะห์ไม่ถูกต้อง: {analysis_mode}")
            return templates.TemplateResponse("error.html", {
                "request": request,
                "message": "โหมดการวิเคราะห์ไม่ถูกต้อง กรุณาเลือก 'video' หรือ 'channel'"
            }, status_code=400)

    except ValueError as e:
        print(f"ERROR: ข้อผิดพลาด ValueError ขณะประมวลผล: {e}")
        return templates.TemplateResponse("error.html", {
            "request": request,
            "message": f"ข้อผิดพลาดในการดึงข้อมูลหรือประมวลผล: {e}"
        }, status_code=400)
    except Exception as e:
        print(f"CRITICAL ERROR: เกิดข้อผิดพลาดที่ไม่คาดคิดขณะประมวลผลใน /analyze: {e}") 
        return templates.TemplateResponse("error.html", {
            "request": request,
            "message": f"เกิดข้อผิดพลาดขณะประมวลผล: {e}"
        }, status_code=500)

# --- Channel Browse Endpoints (ปรับปรุง next_page_token) ---

@app.post("/get_channel_videos", response_class=HTMLResponse)
async def get_channel_videos(request: Request, channel_url: str = Form(...)):
    """
    API endpoint สำหรับแสดงวิดีโอเริ่มต้นของช่อง YouTube
    """
    print(f"DEBUG: รับคำขอแสดงวิดีโอช่องสำหรับ URL: {channel_url}") 
    
    if not YOUTUBE_API_KEY_CHECK:
        print("ERROR: ไม่พบ YouTube API Key ใน /get_channel_videos.")
        return templates.TemplateResponse("error.html", { 
            "request": request,
            "message": "ข้อผิดพลาด: ไม่พบ YouTube API Key โปรดตรวจสอบไฟล์ .env ของคุณ"
        }, status_code=500)

    try:
        channel_id = extract_channel_id(channel_url)
        if not channel_id:
            return templates.TemplateResponse("error.html", {
                "request": request,
                "message": "ไม่พบ Channel ID จาก URL ที่ให้มา กรุณาตรวจสอบลิงก์ช่อง YouTube"
            }, status_code=400)
        print(f"DEBUG: Channel ID ที่ดึงได้: {channel_id}") 

        channel_details = fetch_channel_details(channel_id)
        if not channel_details:
            print(f"ERROR:ไม่พบข้อมูลช่อง YouTube สำหรับ Channel ID: {channel_id}")
            return templates.TemplateResponse("error.html", {
                "request": request,
                "message": "ไม่พบข้อมูลช่อง YouTube นี้ กรุณาตรวจสอบ Channel ID หรือ URL"
            }, status_code=404)

        all_videos, next_page_token = fetch_channel_videos(channel_id, max_results_per_page=50) 
        print(f"DEBUG: ดึงวิดีโอช่องได้: {len(all_videos)} รายการ, Next Page Token: {next_page_token}") 
        
        return templates.TemplateResponse("channel_videos.html", {
            "request": request,
            "channel_details": channel_details,
            "all_videos": all_videos, 
            "next_page_token": next_page_token,
            "channel_id": channel_id,
            "channel_url": channel_url
        })

    except Exception as e:
        print(f"CRITICAL ERROR: เกิดข้อผิดพลาดที่ไม่คาดคิดขณะแสดงวิดีโอช่องใน /get_channel_videos: {e}") 
        return templates.TemplateResponse("error.html", { 
            "request": request,
            "message": f"เกิดข้อผิดพลาดในการแสดงวิดีโอช่อง: {e}"
        }, status_code=500)

@app.get("/load_more_channel_videos", response_class=JSONResponse)
async def load_more_channel_videos(channel_id: str, page_token: str = Query(None)):
    # normalize page_token จาก client
    if page_token in (None, "", "None", "null", "undefined"):
        page_token = None

    try:
        all_videos, new_next_token = fetch_channel_videos(channel_id, max_results_per_page=50, page_token=page_token)
        return JSONResponse(content={
            "all_videos": all_videos,
            "next_page_token": new_next_token or ""
        })
    except Exception as e:
        return JSONResponse(content={"error": f"เกิดข้อผิดพลาดในการโหลดวิดีโอเพิ่มเติม: {e}"}, status_code=500)


# Main entry point for running the Uvicorn server
if __name__ == "__main__":
    # Add a startup check for API keys
    if not YOUTUBE_API_KEY_CHECK:
        print("*****************************************************************")
        print("WARNING: YouTube API Key is not set in your .env file.")
        print("         Please get one from Google Cloud Console and add it:")
        print("         YOUTUBE_API_KEY=YOUR_API_KEY_HERE")
        print("*****************************************************************")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
