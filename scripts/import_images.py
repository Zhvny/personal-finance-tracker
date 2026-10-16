import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(".")
sys.path.append(str(PROJECT_ROOT))
sys.path.append(str(PROJECT_ROOT / "finance-tracker-gui"))


import google.generativeai as genai

# Import prompts and helpers from backend
from backend.ai.provider_strategy import _RECEIPT_SYSTEM, _gemini_key
from backend.routers.deps import _bust_behavioral_cache
from PIL import Image

from packages.core.application.expense_service import ExpenseService
from packages.core.application.income_service import IncomeService
from packages.core.application.investment_service import InvestmentService
from packages.core.application.reward_service import RewardService

# Import core components
from packages.core.infrastructure.persistence.postgres_expense_repository import PostgresExpenseRepository
from packages.core.infrastructure.persistence.postgres_income_repository import PostgresIncomeRepository
from packages.core.infrastructure.persistence.postgres_investment_repository import PostgresInvestmentRepository
from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager


def calculate_file_hash(file_path):
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

def ensure_metadata_table():
    sql = "CREATE TABLE IF NOT EXISTS financials.import_metadata (id SERIAL PRIMARY KEY, file_hash TEXT UNIQUE NOT NULL, file_name TEXT NOT NULL, imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, source_type TEXT NOT NULL, target_id INTEGER, target_table TEXT)"
    DatabaseManager.execute(sql)

def is_already_imported(file_hash):
    sql = "SELECT id FROM financials.import_metadata WHERE file_hash = %s"
    rows = DatabaseManager.query(sql, (file_hash,))
    return len(rows) > 0

def record_import(file_hash, file_name, source_type, target_id, target_table):
    sql = "INSERT INTO financials.import_metadata (file_hash, file_name, source_type, target_id, target_table) VALUES (%s, %s, %s, %s, %s)"
    DatabaseManager.execute(sql, (file_hash, file_name, source_type, target_id, target_table))

def run_gemini_ocr(image_path):
    key = _gemini_key()
    if not key:
        print("Error: No Gemini API Key found.")
        return None

    genai.configure(api_key=key)
    model = genai.GenerativeModel("gemini-1.5-flash")

    img = Image.open(image_path)
    prompt = f"{_RECEIPT_SYSTEM}\n\nUSER: Tolong baca struk ini dan ekstrak data dalam format JSON."

    try:
        response = model.generate_content([prompt, img])
        raw_text = response.text.strip()
        if raw_text.startswith("```json"): raw_text = raw_text[7:]
        if raw_text.endswith("```"): raw_text = raw_text[:-3]
        return json.loads(raw_text.strip())
    except Exception as e:
        print(f"Gemini OCR error for {image_path}: {e}")
        return None

def process_images():
    DatabaseManager.initialize()
    ensure_metadata_table()

    exp_repo = PostgresExpenseRepository()
    inc_repo = PostgresIncomeRepository()
    inv_repo = PostgresInvestmentRepository()
    reward_service = RewardService()

    expense_service = ExpenseService(exp_repo, reward_service)
    income_service = IncomeService(inc_repo, reward_service)
    investment_service = InvestmentService(inv_repo)

    images_dir = PROJECT_ROOT / "images"
    files_to_process = ["makan_burger.jpeg", "investment.jpeg"]

    results = []

    for filename in files_to_process:
        file_path = images_dir / filename
        if not file_path.exists():
            print(f"File not found: {file_path}")
            continue

        file_hash = calculate_file_hash(file_path)
        if is_already_imported(file_hash):
            print(f"Skipping {filename}: Already imported.")
            continue

        print(f"Processing {filename}...")
        data = run_gemini_ocr(file_path)
        if not data: continue

        target_id, target_table = None, None

        if "makan_burger" in filename:
            amount = data.get("amount", 0)
            date_str = data.get("date")
            try: date_dt = datetime.fromisoformat(date_str)
            except: date_dt = datetime.now()

            res = expense_service.record_expense(
                amount=amount,
                description=data.get("merchant", "Unknown") + " (Imported from image)",
                category="food",
                payment_method=data.get("payment_method", "cash"),
                date=date_dt
            )
            target_id, target_table = res["id"], "financials.expenses"
            print(f"Imported {filename} to Expenses (ID: {target_id})")

        elif "investment" in filename:
            asset_type = "stock"
            if "crypto" in str(data).lower(): asset_type = "crypto"
            merchant = data.get("merchant", "UNKNOWN")
            ticker = merchant.split()[0].upper()
            if len(ticker) > 5: ticker = ticker[:5]
            amount = data.get("amount", 0)
            date_str = data.get("date")
            try: date_dt = datetime.fromisoformat(date_str)
            except: date_dt = datetime.now()

            target_id = investment_service.add_investment(
                asset_type=asset_type, ticker=ticker, quantity=1.0,
                buy_price=amount, buy_currency=data.get("currency", "IDR"),
                buy_date=date_dt
            )
            target_table = "investment.investments"
            print(f"Imported {filename} to Investments (ID: {target_id})")

        if target_id:
            record_import(file_hash, filename, "image_ocr", target_id, target_table)
            results.append({"file": filename, "table": target_table, "id": target_id})

    if results:
        _bust_behavioral_cache()
        print("\n--- Summary ---")
        for r in results: print(f"Imported {r.get('file')} -> {r.get('table')} (ID: {r.get('id')})")
    else: print("No new data imported.")

if __name__ == "__main__": process_images()
