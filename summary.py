import os
import json
import re
import pandas as pd
from google import genai

# 1. API Key ของคุณ
API_KEY = "AQ.Ab8RN6IcXk_D4XUy7kx48c3uI0E_sxwg0r-xvwbA7NDP9rQRSQ"
client = genai.Client(api_key=API_KEY)

def convert_buddhist_to_christ_date(date_str: str) -> str:
    """ฟังก์ชันแปลงวันที่ที่เป็น พ.ศ. ให้เป็น ค.ศ. (YYYY-MM-DD)"""
    if not isinstance(date_str, str) or not date_str.strip():
        return None
    
    date_str = date_str.strip()
    match = re.match(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})$", date_str)
    if match:
        day, month, year = match.groups()
        year = int(year)
        if year < 100:
            year += 2500
        if year > 2400:
            year -= 543
        return f"{year:04d}-{int(month):02d}-{int(day):02d}"
    return date_str

def analyze_finance_with_ai(df: pd.DataFrame) -> str:
    """ส่งข้อมูลสถิติการใช้จ่ายให้ Gemini ช่วยวิเคราะห์และสรุปพฤติกรรมการเงิน"""
    try:
        df_expense = df[df["tx_type"] == "expense"]
        df_income = df[df["tx_type"] == "income"]
        df_transfer = df[df["tx_type"] == "transfer"]

        total_expense = df_expense["amount"].sum()
        total_income = df_income["amount"].sum()
        total_transfer = df_transfer["amount"].sum()
        
        cat_summary = df_expense.groupby("category")["amount"].sum().sort_values(ascending=False).to_dict()
        rec_summary = df_expense.groupby("receiver")["amount"].sum().head(5).to_dict()

        prompt = f"""
        คุณคือที่ปรึกษาทางการเงินส่วนบุคคล โปรดวิเคราะห์ข้อมูลการใช้จ่ายด้านล่างนี้:
        - รายรับรวมทั้งหมด (Income): {total_income:,.2f} บาท (จำนวน {len(df_income)} รายการ)
        - รายจ่ายรวมทั้งหมด (Expense): {total_expense:,.2f} บาท (จำนวน {len(df_expense)} รายการ)
        - ยอดโอนย้ายระหว่างบัญชีตนเอง (Transfer): {total_transfer:,.2f} บาท (จำนวน {len(df_transfer)} รายการ - ไม่นำมารวมคำนวณรับ/จ่าย)
        - รายจ่ายแยกตามหมวดหมู่ (Category): {json.dumps(cat_summary, ensure_ascii=False)}
        - ร้านค้า/ผู้รับเงินที่จ่ายออกมากที่สุด 5 อันดับแรก (Receiver): {json.dumps(rec_summary, ensure_ascii=False)}

        กรุณาวิเคราะห์และตอบเป็นภาษาไทย โดยเน้นหัวข้อหลักดังนี้:
        1. **สรุปภาพรวมรายรับ-รายจ่ายจริง** (ไม่นับรวมยอด Transfer)
        2. **สรุปว่าเสียเงินไปกับอะไรมากที่สุด** (ทั้งในแง่หมวดหมู่ และร้านค้า/ผู้รับเงิน)
        3. **คำแนะนำในการประหยัดเงิน** 2-3 ข้อที่ทำได้จริง

        ตอบให้กระชับ ชัดเจน และเป็นกันเอง
        """

        response = client.models.generate_content(
            model='gemini-3.5-flash-lite',
            contents=prompt,
        )
        return response.text.strip()
    except Exception as e:
        return f"❌ ไม่สามารถให้ AI วิเคราะห์ได้เนื่องจากเกิดข้อผิดพลาด: {e}"

def process_weekly_summary_and_ai(excel_file: str = "transactions.xlsx", output_file: str = "weekly_summary.xlsx"):
    if not os.path.exists(excel_file):
        print(f"❌ ไม่พบไฟล์ '{excel_file}' ในโฟลเดอร์ปัจจุบัน")
        return

    try:
        # 1. อ่านไฟล์ Excel
        df = pd.read_excel(excel_file)

        if df.empty or "date" not in df.columns or "amount" not in df.columns:
            print("⚠️ ไฟล์ Excel ไม่มีข้อมูล หรือขาดคอลัมน์ 'date' / 'amount'")
            return

        # 2. ทำความสะอาด amount (กรองเฉพาะรายการที่มีจำนวนเงินมากกว่า 0)
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
        df = df[df["amount"] > 0]

        # 3. แปลงวันที่ พ.ศ. -> ค.ศ.
        df["date_clean"] = df["date"].astype(str).apply(convert_buddhist_to_christ_date)
        df["date_dt"] = pd.to_datetime(df["date_clean"], errors="coerce")
        df = df.dropna(subset=["date_dt"])

        # 4. แยกแยะประเภทรายการ (tx_type): income, transfer, expense
        type_col = df["type"].astype(str).str.strip().str.lower() if "type" in df.columns else pd.Series([""] * len(df))
        cat_col = df["category"].astype(str).str.strip().str.lower() if "category" in df.columns else pd.Series([""] * len(df))

        def classify_transaction(row):
            t = str(row["type_str"])
            c = str(row["cat_str"])
            
            if c == "transfer":
                return "transfer"
            elif t == "income" or c == "income":
                return "income"
            else:
                return "expense"

        df["type_str"] = type_col
        df["cat_str"] = cat_col
        df["tx_type"] = df.apply(classify_transaction, axis=1)

        df["category"] = df.get("category", "Uncategorized").fillna("Uncategorized")
        df["receiver"] = df.get("receiver", "Unknown").fillna("Unknown")

        # 5. จัดกลุ่มรายสัปดาห์ (วันจันทร์ - วันอาทิตย์)
        def get_week_range(dt):
            start = dt - pd.Timedelta(days=dt.weekday())
            end = start + pd.Timedelta(days=6)
            return f"{start.strftime('%d/%m/%Y')} - {end.strftime('%d/%m/%Y')}"

        df["week_range"] = df["date_dt"].apply(get_week_range)
        df["week_start"] = df["date_dt"].apply(lambda dt: dt - pd.Timedelta(days=dt.weekday()))

        # แยกคำนวณยอดเงิน และสร้างคอลัมน์ช่วยนับจำนวนรายการแยกประเภท
        df["income"] = df.apply(lambda row: row["amount"] if row["tx_type"] == "income" else 0.0, axis=1)
        df["expense"] = df.apply(lambda row: row["amount"] if row["tx_type"] == "expense" else 0.0, axis=1)
        df["transfer"] = df.apply(lambda row: row["amount"] if row["tx_type"] == "transfer" else 0.0, axis=1)

        df["is_real_tx"] = df["tx_type"].isin(["income", "expense"])

        # 6. สรุปผลรายสัปดาห์
        summary = df.groupby(["week_start", "week_range"]).agg(
            total_income=("income", "sum"),
            total_expense=("expense", "sum"),
            total_transfer=("transfer", "sum"),
            real_tx_count=("is_real_tx", lambda x: x.sum()),  # นับเฉพาะรายการ Income + Expense จริง
            transfer_count=("tx_type", lambda x: (x == "transfer").sum()),  # นับจำนวนรายการโอนย้าย
            total_tx_count=("amount", "count")  # จำนวนรายการทั้งหมดในไฟล์
        ).reset_index()

        summary["net_balance"] = summary["total_income"] - summary["total_expense"]
        summary = summary.sort_values(by="week_start", ascending=False)

        display_df = pd.DataFrame({
            "สัปดาห์ (จันทร์ - อาทิตย์)": summary["week_range"],
            "รายการรับ-จ่ายจริง": summary["real_tx_count"],
            "รายการโอนย้าย": summary["transfer_count"],
            "รายการรวมทั้งหมด": summary["total_tx_count"],
            "รายรับ (บาท)": summary["total_income"].round(2),
            "รายจ่าย (บาท)": summary["total_expense"].round(2),
            "โอนย้ายบัญชี (บาท)": summary["total_transfer"].round(2),
            "คงเหลือสุทธิ (บาท)": summary["net_balance"].round(2)
        })

        # 7. แสดงผลบน Terminal
        print("\n==========================================================================================")
        print("📊 สรุปรายงานรายรับ - รายจ่าย แยกตามสัปดาห์ (Weekly Summary)")
        print("==========================================================================================")
        print(display_df.to_string(index=False))
        print("==========================================================================================")

        all_income = df["income"].sum()
        all_expense = df["expense"].sum()
        all_transfer = df["transfer"].sum()
        all_net = all_income - all_expense
        real_count = df["is_real_tx"].sum()
        transfer_count = (df["tx_type"] == "transfer").sum()

        print(f"\n💰 สรุปภาพรวมทั้งหมด:")
        print(f"   • รายรับรวม (Income):      {all_income:,.2f} บาท")
        print(f"   • รายจ่ายรวม (Expense):     {all_expense:,.2f} บาท")
        print(f"   • โอนย้ายบัญชี (Transfer):   {all_transfer:,.2f} บาท (ไม่นำมารวมคำนวณ)")
        print(f"   • คงเหลือสุทธิรวม:           {all_net:,.2f} บาท")
        print(f"   • จำนวนรายการรับ-จ่ายจริง:  {real_count} รายการ (โอนย้ายอีก {transfer_count} รายการ)")

        # 8. ให้ AI วิเคราะห์
        print("\n🤖 กำลังให้ AI วิเคราะห์พฤติกรรมการใช้จ่ายของคุณ...")
        ai_analysis = analyze_finance_with_ai(df)
        
        print("\n=======================================================")
        print("💡 ผลการวิเคราะห์การเงินจาก AI")
        print("=======================================================")
        print(ai_analysis)
        print("=======================================================")

        # 9. บันทึกลงไฟล์ Excel
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            display_df.to_excel(writer, sheet_name="Weekly Summary", index=False)
            ai_df = pd.DataFrame([{"บทวิเคราะห์การเงินจาก AI": ai_analysis}])
            ai_df.to_excel(writer, sheet_name="AI Analysis", index=False)

        print(f"\n✅ บันทึกรายงานสรุปและบทวิเคราะห์ลงไฟล์ '{output_file}' เรียบร้อยแล้ว!")

    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในการประมวลผล: {e}")

if __name__ == "__main__":
    process_weekly_summary_and_ai()
