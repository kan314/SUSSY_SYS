import os
import json
from datetime import datetime
from PIL import Image
from google import genai
from google.genai import types
import pandas as pd

# 1. ใส่ API Key ของคุณตรงนี้
API_KEY = "AQ.Ab8RN6IcXk_D4XUy7kx48c3uI0E_sxwg0r-xvwbA7NDP9rQRSQ"

# ตั้งค่า Client
client = genai.Client(api_key=API_KEY)

def extract_slip_info(image_path: str):
    """อ่านรูปสลิปและสกัดข้อมูลสำคัญออกมาเป็น JSON"""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"ไม่พบไฟล์รูปภาพที่: {image_path}")
    
    # เปิดและย่อขนาดภาพเล็กน้อยเพื่อความรวดเร็วและประหยัด Token
    image = Image.open(image_path)
    image.thumbnail((800, 800))
    
    prompt = """
    วิเคราะห์รูปภาพสลิปโอนเงินนี้ และดึงข้อมูลออกมาเป็น JSON เท่านั้น โดยมีคีย์ดังนี้:
    - "date": วันที่ทำรายการ (รูปแบบ DD/MM/YYYY)
    - "time": เวลาที่ทำรายการ (HH:MM)
    - "type": ประเภทรายการ ("Income" หรือ "Expense")
    - "amount": จำนวนเงิน (ตัวเลขทศนิยม เช่น 39.00)
    - "sender": ชื่อผู้โอน
    - "receiver": ชื่อผู้รับโอน
    - "bank": ธนาคารที่โอน
    - "note": บันทึกช่วยจำ หรือหมายเหตุ (ถ้ามี)
    """
    
    # บังคับให้โมเดลตอบกลับมาเป็น JSON แน่นอน
    response = client.models.generate_content(
        model='gemini-3.5-flash-lite',
        contents=[image, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        ),
    )
    
    # ทำความสะอาดข้อความเผื่อมี markdown ครอบมา
    raw_text = response.text.strip()
    if raw_text.startswith("```json"):
        raw_text = raw_text[7:]
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]
        
    return json.loads(raw_text.strip())

def save_to_excel(data: dict, excel_file: str = "transactions.xlsx"):
    """บันทึกข้อมูลลงไฟล์ Excel แบบต่อท้าย (เช็คไฟล์ถูกเปิดค้างไว้ด้วย)"""
    new_row = pd.DataFrame([data])
    
    try:
        if os.path.exists(excel_file):
            # ถ้ามีไฟล์เดิมอยู่แล้ว ให้อ่านมาต่อท้าย
            df_existing = pd.read_excel(excel_file)
            df_updated = pd.concat([df_existing, new_row], ignore_index=True)
        else:
            # ถ้ายังไม่มี ให้สร้างใหม่
            df_updated = new_row
            
        df_updated.to_excel(excel_file, index=False)
        print(f"✅ บันทึกข้อมูลลงไฟล์ '{excel_file}' สำเร็จแล้ว!")
        
    except PermissionError:
        # หากไฟล์ถูกเปิดค้างไว้ใน Excel ให้บันทึกเป็นชื่อสำรองแทนอัตโนมัติ
        fallback_file = f"transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        new_row.to_excel(fallback_file, index=False)
        print(f"⚠️ คำเตือน: ไฟล์หลักถูกเปิดค้างไว้ ระบบได้บันทึกสำรองไว้ที่ไฟล์: '{fallback_file}' แทน")

def texas():
    name_of_change = ""
    b = 0
    for i in os.listdir():
        a=i.split(".")
        try:
            if a[1] in "jpg png":
                if int(a[0]) > b:
                    b = int(a[0])
                
        except:
            name_of_change = a[0]
    c=str(b+1)

    os.rename(name_of_change + ".jpg",c+".jpg")

    return c

if __name__ == "__main__":
    while True:
        # ใส่ชื่อไฟล์รูปสลิปของคุณ
        try:
            slip_image_path = texas() + ".jpg"
        except:
            print("Everything finished!!")
            break
            
        try:
            print("1. กำลังอ่านข้อมูลจากสลิปด้วย Gemini...")
            result = extract_slip_info(slip_image_path)

            if result["bank"] == "เป๋าตัง" or "G-Wallet":result["category"]="food"
            else:
                img = Image.open(slip_image_path)
                img.show()
                result["category"]=input(f"Input your category with {result["receiver"]}:").lower()
                


            

            if "นิธิกานต์" in result["receiver"]:
                result["category"]="transfer"
            result["path"]=slip_image_path

            
            print("\nผลลัพธ์ข้อมูลสลิปที่สกัดได้:")
            print(json.dumps(result, ensure_ascii=False, indent=2))
            
            print("\n2. กำลังบันทึกลงไฟล์ Excel...")
            save_to_excel(result)
            
        except Exception as err:
            print(f"❌ เกิดข้อผิดพลาด: {err}")
