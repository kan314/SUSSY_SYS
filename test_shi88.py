import os
import json
import shutil
from datetime import datetime
from PIL import Image
from google import genai
from google.genai import types
import pandas as pd

# 1. API Key ของคุณ
API_KEY = "AQ.Ab8RN6IcXk_D4XUy7kx48c3uI0E_sxwg0r-xvwbA7NDP9rQRSQ"

client = genai.Client(api_key=API_KEY)

def extract_slip_info(image_path: str):
    """อ่านรูปสลิปและสกัดข้อมูลสำคัญออกมาเป็น JSON"""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"ไม่พบไฟล์รูปภาพที่: {image_path}")
    
    image = Image.open(image_path)
    image.thumbnail((800, 800))
    
    prompt = """
    วิเคราะห์รูปภาพสลิปโอนเงินนี้ และดึงข้อมูลออกมาเป็น JSON เท่านั้น โดยมีคีย์ดังนี้:
    - "transaction_id": เลขที่รายการ หรือ รหัสอ้างอิง (เช่น 016283195310APM10961)
    - "date": วันที่ทำรายการ (รูปแบบ DD/MM/YYYY)
    - "time": เวลาที่ทำรายการ (HH:MM)
    - "type": ประเภทรายการ ("Income" หรือ "Expense")
    - "amount": จำนวนเงิน (ตัวเลขทศนิยม เช่น 39.00)
    - "sender": ชื่อผู้โอน
    - "receiver": ชื่อผู้รับโอน
    - "bank": ธนาคารที่โอน
    - "note": บันทึกช่วยจำ หรือหมายเหตุ (ถ้ามี)
    """
    
    response = client.models.generate_content(
        model='gemini-3.5-flash-lite',
        contents=[image, prompt],
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        ),
    )
    
    raw_text = response.text.strip()
    if raw_text.startswith("```json"):
        raw_text = raw_text[7:]
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]
        
    return json.loads(raw_text.strip())

def is_duplicate_transaction(data: dict, excel_file: str = "transactions.xlsx") -> bool:
    """ตรวจสอบว่าสลิปนี้เคยบันทึกลง Excel ไปแล้วหรือยัง"""
    if not os.path.exists(excel_file):
        return False
        
    try:
        df_existing = pd.read_excel(excel_file)
        
        # 1. เช็คด้วย transaction_id
        tx_id = data.get("transaction_id")
        if tx_id and "transaction_id" in df_existing.columns:
            if tx_id in df_existing["transaction_id"].astype(str).values:
                return True
                
        # 2. เช็คสำรอง (วันที่ + เวลา + ยอดเงิน + ผู้รับ)
        check_cols = ["date", "time", "amount", "receiver"]
        if all(col in df_existing.columns for col in check_cols):
            match = df_existing[
                (df_existing["date"].astype(str) == str(data.get("date"))) &
                (df_existing["time"].astype(str) == str(data.get("time"))) &
                (df_existing["amount"] == data.get("amount")) &
                (df_existing["receiver"].astype(str) == str(data.get("receiver")))
            ]
            if not match.empty:
                return True
                
    except Exception as e:
        print(f"⚠️ เกิดข้อผิดพลาดขณะเช็คสลิปซ้ำ: {e}")
        
    return False

def organize_and_move_slip(slip_image_path: str, date_str: str) -> str:
    """สร้างโฟลเดอร์แยกตาม ปี-เดือน (เช่น slips/2026-10) และย้ายไฟล์สลิปไปเก็บ"""
    try:
        date_obj = datetime.strptime(date_str, "%d/%m/%Y")
        folder_name = date_obj.strftime("%Y-%m")
    except Exception:
        folder_name = datetime.now().strftime("%Y-%m")
        
    target_dir = os.path.join("slips", folder_name)
    os.makedirs(target_dir, exist_ok=True)
    
    filename = os.path.basename(slip_image_path)
    new_path = os.path.join(target_dir, filename)
    
    counter = 1
    base_name, ext = os.path.splitext(filename)
    while os.path.exists(new_path):
        new_path = os.path.join(target_dir, f"{base_name}_{counter}{ext}")
        counter += 1

    shutil.move(slip_image_path, new_path)
    return new_path

def save_to_excel(data: dict, excel_file: str = "transactions.xlsx"):
    """บันทึกข้อมูลลงไฟล์ Excel แบบต่อท้าย หากบันทึกไม่ได้ให้โยน Error เพื่อหยุดโปรแกรม"""
    new_row = pd.DataFrame([data])
    
    try:
        if os.path.exists(excel_file):
            df_existing = pd.read_excel(excel_file)
            df_updated = pd.concat([df_existing, new_row], ignore_index=True)
        else:
            df_updated = new_row
            
        df_updated.to_excel(excel_file, index=False)
        print(f"✅ บันทึกข้อมูลลงไฟล์ '{excel_file}' สำเร็จแล้ว!")
        
    except PermissionError:
        print(f"\n❌ ข้อผิดพลาด: ไฟล์ '{excel_file}' กำลังถูกเปิดค้างอยู่ กรุณาปิดไฟล์ก่อนรันโปรแกรม!")
        raise RuntimeError(f"ไม่สามารถเขียนลงไฟล์ {excel_file} ได้เนื่องจากไฟล์ถูกล็อก (Permission Error)")
    except Exception as e:
        print(f"\n❌ เกิดข้อผิดพลาดในการบันทึก Excel: {e}")
        raise e

def get_input_files(input_dir: str = "slips_input") -> list:
    """ดึงรายชื่อไฟล์รูปภาพทั้งหมดใน slips_input"""
    if not os.path.exists(input_dir):
        os.makedirs(input_dir, exist_ok=True)
        return []
        
    valid_extensions = (".jpg", ".jpeg", ".png")
    files = [
        os.path.join(input_dir, f) for f in os.listdir(input_dir)
        if f.lower().endswith(valid_extensions)
    ]
    return files

if __name__ == "__main__":
    INPUT_DIR = "slips_input"
    files = get_input_files(INPUT_DIR)

    if not files:
        print(f"🎉 ไม่พบไฟล์รูปภาพใหม่ในโฟลเดอร์ '{INPUT_DIR}'")
    else:
        print(f"🔍 พบสลิปทั้งหมด {len(files)} ไฟล์ กำลังเริ่มประมวลผล...")

        for slip_image_path in files:
            print(f"\n--------------------------------------------------")
            print(f"📸 ประมวลผลไฟล์: {slip_image_path}")

            try:
                # 1. อ่านข้อมูลสลิปด้วย Gemini
                print("1. กำลังอ่านข้อมูลด้วย Gemini (gemini-3.5-flash-lite)...")
                result = extract_slip_info(slip_image_path)

                # 2. ย้ายไฟล์รูปไปโฟลเดอร์ slips/YYYY-MM/
                saved_path = organize_and_move_slip(slip_image_path, result.get("date", ""))
                result["path"] = saved_path

                # 3. เช็ครายการซ้ำ
                if is_duplicate_transaction(result):
                    print(f"⚠️ สลิป {saved_path} เคยบันทึกลง Excel ไปแล้ว (ข้ามการบันทึกซ้ำ)")
                    continue

                # 4. เงื่อนไข Category / Type
                sender_name = str(result.get("sender", ""))
                receiver_name = str(result.get("receiver", ""))
                bank_info = str(result.get("bank", ""))

                if "นิธิกานต์" in sender_name or "NITIKAN" in sender_name and "นิธิกานต์" in receiver_name or "NITIKAN" in receiver_name:
                    result["category"] = "transfer"
                    result["type"] = "Transfer"
                elif "นิธิกานต์" in receiver_name and "นิธิกานต์" not in sender_name:
                    result["type"] = "Income"
                    result["category"] = "income"
                elif bank_info in ["เป๋าตัง", "G-Wallet"]:
                    result["category"] = "food"
                    result["type"] = "Expense"
                else:
                    result["type"] = "Expense"
                    img = Image.open(saved_path)
                    img.show()
                    result["category"] = input(f"Input your category with {receiver_name}: ").lower()

                # 5. บันทึกลง Excel
                print("2. กำลังบันทึกลงไฟล์ Excel...")
                save_to_excel(result)

                print("\nผลลัพธ์ข้อมูลสลิปที่สกัดได้:")
                print(json.dumps(result, ensure_ascii=False, indent=2))

            except Exception as err:
                print(f"\n⛔ โปรแกรมหยุดการทำงานเนื่องจากเกิดข้อผิดพลาด: {err}")
                break

        print("\n🎉 ประมวลผลสลิปทั้งหมดเสร็จสิ้นเรียบร้อยแล้ว!")
