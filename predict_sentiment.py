import os
import requests # เราจะใช้ไลบรารี requests ในการคุยกับ API
from typing import List, Dict
from dotenv import load_dotenv

# --- 1. ตั้งค่าการเชื่อมต่อ API ---
load_dotenv()

# URL ของ "โรงงาน" (โมเดลของคุณบน Hugging Face)
API_URL = "https://api-inference.huggingface.co/models/patipathdev/wangchanberta-thai-sentiment"

# "กุญแจ" สำหรับยืนยันตัวตน ดึงมาจาก Environment Variable
HF_TOKEN = os.getenv("HF_TOKEN")
headers = {"Authorization": f"Bearer {HF_TOKEN}"}

# กำหนด Mapping ของ Label (เหมือนเดิม)
id2label = {0: "negative", 1: "neutral", 2: "positive"}


def query_hf_api(payload: dict) -> list:
    """
    ฟังก์ชันสำหรับ "โทรศัพท์" ไปสั่งงานที่ Hugging Face Inference API
    """
    response = requests.post(API_URL, headers=headers, json=payload)
    if response.status_code != 200:
        print(f"ERROR: Hugging Face API request failed with status {response.status_code}")
        print(f"Response: {response.json()}")
        return []
    return response.json()

# --- 2. ฟังก์ชันทำนายผล (เวอร์ชันใหม่) ---
def predict_sentiment(texts: List[str]) -> List[Dict[str, str]]:
    """
    ฟังก์ชันนี้จะเปลี่ยนจากการคำนวณเอง เป็นการส่งข้อความทั้งหมด
    ไปให้ Hugging Face API ทำนายผล แล้วนำคำตอบกลับมาจัดรูปแบบ
    """
    if not texts:
        return []
        
    if not HF_TOKEN:
        print("ERROR: ไม่พบ Hugging Face Token (HF_TOKEN) ใน Environment Variables")
        return []

    try:
        # ส่งข้อความทั้งหมดไปให้ API ประมวลผลในครั้งเดียว
        api_output = query_hf_api({
            "inputs": texts,
            "options": {"wait_for_model": True} # บอกให้ API รอถ้าโมเดลกำลัง "วอร์มเครื่อง"
        })

        if not api_output:
            return []

        # api_output จะมีหน้าตาแบบนี้: [[{'label': 'LABEL_2', 'score': 0.9}, ...], [{'label': 'LABEL_0', 'score': 0.8}, ...]]
        
        results = []
        for prediction_list in api_output:
            # หา label ที่มีคะแนนสูงสุด
            best_prediction = max(prediction_list, key=lambda x: x['score'])
            # แปลง LABEL_0, LABEL_1, LABEL_2 กลับเป็น negative, neutral, positive
            label_index = int(best_prediction['label'].split('_')[-1])
            final_label = id2label.get(label_index, 'unknown')
            results.append({"label": final_label})
            
        return results
        
    except Exception as e:
        print(f"ERROR: เกิดข้อผิดพลาดระหว่างเรียกใช้ Hugging Face API: {e}")
        return []