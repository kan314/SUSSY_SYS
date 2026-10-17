import os
import time
import subprocess
import sys
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ตั้งค่า Logging สำหรับติดตามการทำงาน
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("SimpleWatchdog")

# โฟลเดอร์ที่ต้องการเฝ้ามอง
WATCH_DIR = "./slips_input"
os.makedirs(WATCH_DIR, exist_ok=True)

class SlipHandler(FileSystemEventHandler):
    def on_created(self, event):
        # ข้ามถ้าเป็นโฟลเดอร์
        if event.is_directory:
            return

        file_path = event.src_path
        file_name = os.path.basename(file_path)

        # ตรวจสอบว่าเป็นไฟล์รูปภาพ (.jpg, .jpeg, .png)
        if file_name.lower().endswith(('.jpg', '.jpeg', '.png')):
            logger.info(f"🔍 ตรวจพบไฟล์รูปภาพใหม่: {file_name}")
            
            # หน่วงเวลาเล็กน้อยเพื่อให้ LINE บันทึกไฟล์ลงดิสก์สมบูรณ์ก่อน
            time.sleep(1)

            # สั่งรัน test_shi88.py ทันที
            self.run_shi88()

    def run_shi88(self):
        try:
            logger.info("🚀 กำลังสั่งรัน test_shi88.py...")
            
            # สั่งรัน test_shi88.py โดยใช้ Python ตัวเดียวกับที่รันสคริปต์นี้
            result = subprocess.run(
                [sys.executable, "test_shi88.py"],
                check=True
            )
            
            logger.info("✅ ประมวลผล test_shi88.py สำเร็จ!")

        except subprocess.CalledProcessError as e:
            logger.error(f"❌ test_shi88.py รันไม่สำเร็จ (Exit code: {e.returncode})")
        except Exception as e:
            logger.error(f"❌ เกิดข้อผิดพลาดในการรัน test_shi88.py: {e}")

def start_watchdog():
    event_handler = SlipHandler()
    observer = Observer()
    observer.schedule(event_handler, path=WATCH_DIR, recursive=False)
    
    logger.info(f"👀 Watchdog เริ่มทำงาน... เฝ้ามองโฟลเดอร์: {os.path.abspath(WATCH_DIR)}")
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("🛑 กำลังหยุดการทำงานของ Watchdog...")
        observer.stop()
    observer.join()

if __name__ == "__main__":
    start_watchdog()
