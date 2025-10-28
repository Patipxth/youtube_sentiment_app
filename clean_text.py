import re  # ใช้สำหรับ regular expressions เช่น การลบ URL, อักขระพิเศษ
from pythainlp.util import normalize  # ใช้ normalize ตัวอักษรภาษาไทย เช่น การจัดรูปแบบซ้ำซ้อน

def clean_text(text):
    """
    ฟังก์ชันทำความสะอาดข้อความเดี่ยว:
    - Normalize ตัวอักษรไทยให้เป็นรูปแบบมาตรฐาน (เช่น ลบสระซ้อน)
    - ลบ URL เช่น http://..., https://..., www...
    - ลบ emoji และอักขระพิเศษที่ไม่ใช่ตัวอักษรหรือตัวเลข
    - ตัดช่องว่างที่เกินออก (เหลือเพียงช่องว่างเดียวระหว่างคำ)
    """
    text = normalize(text)  # จัดการ normalize ตัวอักษรภาษาไทย เช่น "ก้" → "ก็"
    
    # ลบ URL (http, https, www) ออกจากข้อความ
    text = re.sub(r"http\S+|www\S+|https\S+", "", text, flags=re.MULTILINE)
    
    # ลบอักขระที่ไม่ใช่: ตัวอักษรภาษาไทย, a-z, A-Z, ตัวเลข, หรือเว้นวรรค
    text = re.sub(r"[^\w\sก-๙]", "", text)
    
    # ลบช่องว่างซ้ำๆ เช่น tab/newline แล้วเหลือแค่ 1 ช่องว่าง
    text = re.sub(r"\s+", " ", text).strip()
    
    return text  # คืนค่าข้อความที่ทำความสะอาดแล้ว

def clean_comments(comments):
    """
    ฟังก์ชันทำความสะอาดคอมเมนต์หลายข้อความ:
    - รับ list ของข้อความ
    - วนลูปใช้ clean_text กับทุกข้อความใน list
    - คืนค่าลิสต์ใหม่ของข้อความที่ถูกทำความสะอาดแล้ว
    """
    return [clean_text(comment) for comment in comments]
