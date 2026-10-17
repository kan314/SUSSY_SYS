import os
import sys
import logging
from fastapi import FastAPI, Request, HTTPException
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    MessagingApiBlob,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import MessageEvent, ImageMessageContent

# ==========================================
# 📊 1. ระบบ TELEMETRY & LOGGING SETUP
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),          # แสดงผลบน Terminal
        logging.FileHandler("line_runner.log", encoding="utf-8") # บันทึกลงไฟล์ Log
    ]
)
logger = logging.getLogger("LineRunner")

# ==========================================
# ⚙️ 2. CONFIGURATION
# ==========================================
LINE_CHANNEL_ACCESS_TOKEN = "2F4V4nJ8N6rDPwsI4UU3+C3oGTSj2LBoYnfzTs+T/BeW5kTmY4CzCu5wk0Kb9yAMIXP2ePrWLSFqsqaqhw3FseNzPtwPXYj8WElOhNTGsRSumbD9Cph7BLqsroO1lJCkb1AoEHwUgXILByqHwHXxUQdB04t89/1O/w1cDnyilFU="
LINE_CHANNEL_SECRET = "0a9c7f5e123bb5e5e711f35e36d1970e"

UPLOAD_DIR = "./slips_input"
os.makedirs(UPLOAD_DIR, exist_ok=True)
logger.info(f"📁 ตั้งค่าโฟลเดอร์สำหรับเซฟสลิป: {os.path.abspath(UPLOAD_DIR)}")

app = FastAPI()

if LINE_CHANNEL_ACCESS_TOKEN == "YOUR_LINE_CHANNEL_ACCESS_TOKEN":
    logger.warning("⚠️ อย่าลืมใส่ LINE_CHANNEL_ACCESS_TOKEN จริงในโค้ดก่อนใช้งาน!")

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ==========================================
# 🚀 3. WEBHOOK ENDPOINT
# ==========================================
@app.post("/callback")
async def callback(request: Request):
    signature = request.headers.get("X-Line-Signature")
    if not signature:
        logger.error("❌ คำขอถูกปฏิเสธ: ไม่พบ X-Line-Signature header")
        raise HTTPException(status_code=400, detail="Missing X-Line-Signature header")

    body = await request.body()
    body_str = body.decode("utf-8")
    
    logger.info(f"📩 [Telemetry] ได้รับ Webhook Event (ขนาด payload: {len(body_str)} bytes)")

    try:
        handler.handle(body_str, signature)
    except InvalidSignatureError:
        logger.error("❌ คำขอถูกปฏิเสธ: Signature ไม่ถูกต้อง (Verify Token/Secret ไม่ตรง)")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.critical(f"💥 เกิดข้อผิดพลาดร้ายแรงขณะประมวลผล Webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")

    return "OK"

# ==========================================
# 📸 4. IMAGE HANDLER WITH TELEMETRY
# ==========================================
@handler.add(MessageEvent)
def handle_message(event):
    if isinstance(event.message, ImageMessageContent):
        message_id = event.message.id
        reply_token = event.reply_token
        user_id = getattr(event.source, "user_id", "Unknown_User")

        logger.info(f"📸 [Telemetry] ตรวจพบการส่งรูปภาพ! MessageID: {message_id} จาก User: {user_id}")

        file_path = os.path.join(UPLOAD_DIR, f"{message_id}.jpg")
        
        try:
            # Step 1: ดาวน์โหลดรูปภาพจาก LINE API
            logger.info(f"⏳ [Telemetry] กำลังเชื่อมต่อ LINE API เพื่อดาวน์โหลดรูปภาพ {message_id}...")
            
            with ApiClient(configuration) as api_client:
                line_bot_blob_api = MessagingApiBlob(api_client)
                image_bytes = line_bot_blob_api.get_message_content(message_id=message_id)

            logger.info(f"✅ [Telemetry] ดาวน์โหลดรูปภาพสำเร็จ! (ขนาดไฟล์: {len(image_bytes)} bytes)")

            # Step 2: บันทึกไฟล์ลงดิสก์
            logger.info(f"💾 [Telemetry] กำลังเขียนไฟล์ลงดิสก์ที่: {file_path}")
            with open(file_path, "wb") as f:
                f.write(image_bytes)

            # Verification Check
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                logger.info(f"🎉 [Telemetry] บันทึกไฟล์สมบูรณ์! Path: {os.path.abspath(file_path)}")
                reply_text = f"✅ อัปโหลดและบันทึกรูปสลิปเรียบร้อยแล้ว!\n(ชื่อไฟล์: {message_id}.jpg)"
            else:
                raise IOError("ไฟล์ถูกสร้างแต่มีขนาด 0 bytes")

        except Exception as err:
            logger.error(f"❌ [Telemetry Error] ดาวน์โหลด/บันทึกรูปภาพไม่สำเร็จ: {err}", exc_info=True)
            reply_text = f"❌ เกิดข้อผิดพลาดในการบันทึกรูปสลิป: {str(err)}"

        # Step 3: ส่งข้อความตอบกลับ
        try:
            logger.info(f"📤 [Telemetry] กำลังส่งข้อความตอบกลับไปยัง LINE (ReplyToken: {reply_token})...")
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=reply_token,
                        messages=[TextMessage(text=reply_text)]
                    )
                )
            logger.info(f"✨ [Telemetry] ส่งข้อความตอบกลับสำเร็จ!")
        except Exception as reply_err:
            logger.error(f"❌ [Telemetry Error] ไม่สามารถส่งข้อความตอบกลับหาผู้ใช้ได้: {reply_reply_err}", exc_info=True)

    else:
        logger.info(f"ℹ️ [Telemetry] ได้รับข้อความประเภทอื่น ({event.message.type}) - ข้ามการทำงาน")


if __name__ == "__main__":
    logger.info("🟢 กำลังเริ่มต้นรันระบบ LINE Runner Server...")
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
