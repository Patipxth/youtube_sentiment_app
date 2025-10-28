from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import os
from typing import List, Dict

# --- 1. โหลด Tokenizer และ Model จาก Hugging Face Hub ---
MODEL_HUB_ID = "patipathdev/wangchanberta-thai-sentiment"

print(f"INFO: กำลังโหลดโมเดลจาก Hugging Face Hub: {MODEL_HUB_ID}")
print("INFO: (อาจใช้เวลาสักครู่ในการดาวน์โหลดครั้งแรก)")

try:
    # ไลบรารี transformers จะดาวน์โหลดโมเดลจาก Hub ให้โดยอัตโนมัติ
    tokenizer = AutoTokenizer.from_pretrained(MODEL_HUB_ID)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_HUB_ID)
    print("INFO: โหลด Tokenizer และ Model สำเร็จ")
except Exception as e:
    print(f"ERROR: ไม่สามารถโหลดโมเดลจาก Hugging Face Hub '{MODEL_HUB_ID}' ได้: {e}")
    tokenizer = None
    model = None

# --- 2. กำหนด Mapping ของ Label ---
# ส่วนนี้เหมือนเดิม
id2label = {0: "negative", 1: "neutral", 2: "positive"}


# --- 3. ฟังก์ชันทำนายผล ---
# ส่วนนี้เหมือนเดิม
def predict_sentiment(texts: List[str]) -> List[Dict[str, str]]:
    """
    ทำนายความรู้สึกของข้อความหลายบรรทัดโดยใช้ Batch Processing เพื่อความเร็วสูงสุด
    """
    # ตรวจสอบว่าโมเดลโหลดสำเร็จหรือไม่ และมีข้อมูลให้ประมวลผลหรือไม่
    if not model or not tokenizer or not texts:
        return []

    try:
        # 1. ส่ง list ของความคิดเห็นทั้งหมดเข้า Tokenizer ในครั้งเดียว
        inputs = tokenizer(
            texts,
            return_tensors="pt",
            truncation=True,
            padding=True,
            max_length=512  # กำหนด max_length เพื่อความปลอดภัย
        )

        # 2. ส่ง Batch ทั้งหมดเข้าโมเดลในครั้งเดียว
        with torch.no_grad():
            outputs = model(**inputs)
            logits = outputs.logits

            # 3. ทำนายผลลัพธ์ของทุกข้อความพร้อมกัน
            predicted_class_ids = logits.argmax(dim=1)

        # 4. แปลง ID ที่ได้ทั้งหมดกลับเป็น Label
        labels = [id2label.get(pid.item(), 'unknown') for pid in predicted_class_ids]
        
        # 5. สร้างผลลัพธ์สุดท้าย
        results = [{"label": label} for label in labels]

        return results
        
    except Exception as e:
        print(f"ERROR: เกิดข้อผิดพลาดระหว่างการทำนายผล Sentiment: {e}")
        return []