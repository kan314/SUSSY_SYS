import subprocess
import re
import sys
import time

def start_cloudflare_tunnel():
    print("🌐 กำลังเริ่มต้นรัน Cloudflare Tunnel สำหรับ Port 8000...")
    print("--------------------------------------------------------------------------------------------")

    # คำสั่งรัน cloudflared
    cmd = "cloudflared tunnel --url http://localhost:8000"

    try:
        # เปิด process และอ่าน log แบบ Real-time
        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        tunnel_url_found = False

        # อ่านข้อความจาก Cloudflare บรรทัดต่อบรรทัด
        for line in iter(process.stdout.readline, ''):
            if not line:
                break
            
            # พิมพ์ Log ของ Cloudflare ออกหน้าจอ Terminal ตามปกติ
            print(line, end='')

            # ดักจับ URL ที่เป็น .trycloudflare.com
            if not tunnel_url_found and "trycloudflare.com" in line:
                match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
                if match:
                    base_url = match.group(0)
                    webhook_url = f"{base_url}/callback"
                    
                    print("\n" + "="*80)
                    print("🎉 ดักจับ Webhook URL สำเร็จ!")
                    print(f"👉 คัดลอกลิงก์นี้ไปวางใน LINE Developers Console:")
                    print(f"\n   {webhook_url}\n")
                    print("="*80 + "\n")
                    
                    tunnel_url_found = True

        process.wait()

    except KeyboardInterrupt:
        print("\n🛑 กำลังปิดการทำงานของ Cloudflare Tunnel...")
        print("✅ ปิดระบบเรียบร้อยแล้ว!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ เกิดข้อผิดพลาดในการรัน Cloudflare: {e}")

if __name__ == "__main__":
    start_cloudflare_tunnel()
