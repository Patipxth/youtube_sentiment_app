import openai
from langdetect import detect, LangDetectException # นำเข้า detect และ Exception
import re # นำเข้า regex สำหรับการตรวจสอบตัวอักษร

async def translate_to_thai(texts: list, openai_client: openai.AsyncOpenAI) -> list:

    translated_texts = []
    if not openai_client:
        print("ERROR: OpenAI client ไม่ได้ถูกตั้งค่าสำหรับฟังก์ชันแปลภาษา")
        return texts # คืนค่าข้อความต้นฉบับหาก client ไม่พร้อมใช้งาน

    MIN_CHARS_FOR_TRANSLATION = 5 # กำหนดจำนวนอักขระขั้นต่ำที่จะพิจารณาแปล
    # Regex สำหรับตรวจสอบว่าข้อความมีตัวอักษรที่เป็นคำ (ตัวอักษรภาษาอังกฤษหรือไทย) หรือไม่
    ALPHANUMERIC_PATTERN = re.compile(r'[a-zA-Z0-9ก-ฮ]')
    # Regex สำหรับตรวจจับตัวอักษรไทย
    THAI_CHAR_PATTERN = re.compile(r'[ก-ฮ]')

    for text in texts:
        # 1. ตรวจสอบข้อความที่สั้นเกินไป หรือไม่มีตัวอักษรที่เป็นคำเลย (เช่น อิโมจิล้วน, ตัวเลขล้วน)
        if len(text.strip()) < MIN_CHARS_FOR_TRANSLATION or not ALPHANUMERIC_PATTERN.search(text):
            translated_texts.append(text) # ไม่แปลข้อความประเภทนี้
            continue # ไปยังข้อความถัดไป

        # 2. ตรวจจับภาษาสำหรับข้อความที่ผ่านการกรองเบื้องต้น
        should_translate = False
        try:
            detected_lang = detect(text)
            if detected_lang != 'th': # ถ้าไม่ใช่ภาษาไทย ให้แปล
                should_translate = True
        except LangDetectException:
            # หากตรวจจับภาษาไม่ได้ (เช่น ข้อความสั้นเกินไป)
            # ตรวจสอบว่ามีตัวอักษรไทยหรือไม่ ถ้ามี ให้ถือว่าเป็นภาษาไทย ไม่ต้องแปล
            if THAI_CHAR_PATTERN.search(text):
                print(f"DEBUG: LangDetectException: ข้อความมีตัวอักษรไทย, ไม่แปล: '{text[:50]}...'")
                should_translate = False
            else:
                # ไม่มีตัวอักษรไทย และตรวจจับภาษาไม่ได้ ให้ทำการแปล (อาจเป็นภาษาอังกฤษสั้นๆ หรือภาษาอื่น)
                print(f"ไม่สามารถตรวจจับภาษาได้สำหรับข้อความ: '{text[:50]}...' จะทำการแปล")
                should_translate = True
        except Exception as e:
            print(f"เกิดข้อผิดพลาดในการตรวจจับภาษา: {e}. จะทำการแปลข้อความ")
            should_translate = True

        if should_translate:
            try:
                # เรียกใช้ OpenAI API เพื่อแปลข้อความ (เฉพาะกรณีที่จำเป็น)
                response = await openai_client.chat.completions.create(
                    model="gpt-3.5-turbo", 
                    messages=[
                        {"role": "system", "content": "คุณคือผู้ช่วยที่เชี่ยวชาญในการแปลข้อความเป็นภาษาไทยอย่างแม่นยำและเป็นธรรมชาติ"},
                        {"role": "user", "content": f"โปรดแปลข้อความต่อไปนี้เป็นภาษาไทย:\n\n{text}"}
                    ],
                    max_tokens=500, #
                    temperature=0.2, 
                )
                if response.choices and response.choices[0].message and response.choices[0].message.content:
                    translated_texts.append(response.choices[0].message.content)
                else:
                    print(f"OpenAI API คืนค่าโครงสร้างที่ไม่คาดคิดสำหรับการแปล: {response}")
                    translated_texts.append(text) # คืนค่าข้อความต้นฉบับหากโครงสร้างคำตอบไม่ถูกต้อง
            except openai.APIError as e:
                print(f"เกิดข้อผิดพลาดจาก OpenAI API ระหว่างการแปล: {e}")
                translated_texts.append(text) # คืนค่าข้อความต้นฉบับหากเกิดข้อผิดพลาดจาก API
            except Exception as e:
                print(f"เกิดข้อผิดพลาดที่ไม่คาดคิดระหว่างการแปลด้วย OpenAI: {e}")
                translated_texts.append(text) # คืนค่าข้อความต้นฉบับหากเกิดข้อผิดพลาดอื่นๆ
        else:
            translated_texts.append(text) # เป็นภาษาไทยอยู่แล้ว หรือไม่จำเป็นต้องแปล
            
    return translated_texts
