import json
import logging
import os
import re
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

# Add monorepo root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Initialize Tesseract Path
import pytesseract

TESS_PATH = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
if os.path.isfile(TESS_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESS_PATH

# Initialize DatabaseManager
try:
    from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager
    DatabaseManager.initialize()
except Exception as e:
    logger.warning(f"DatabaseManager initialization failed: {e}")

# Imports for Investment
# Local OCR imports
from apps.cli.receipt_reader.core.ocr_ensemble import OCREnsemble
from apps.cli.receipt_reader.core.parser import ReceiptParser
from packages.core.domain.models.investment import Investment
from packages.core.infrastructure.expense_tracker.models import Expense, ExpenseCategory
from packages.core.infrastructure.expense_tracker.models import PaymentMethod as ExpensePaymentMethod

# Imports for Expense
from packages.core.infrastructure.expense_tracker.repository import SQLiteExpenseRepository
from packages.core.infrastructure.investment_tracker.repository import PostgresRepository

# Folders
IMAGE_DIR = PROJECT_ROOT / "images" / "New"
ARCHIVE_DIR = PROJECT_ROOT / "images" / "Archive"
os.makedirs(ARCHIVE_DIR, exist_ok=True)

# Repositories & Tools
inv_repo = PostgresRepository()
exp_repo = SQLiteExpenseRepository()
ensemble = OCREnsemble(language="id", use_gpu=False)
parser = ReceiptParser()

def parse_investment_text(text: str) -> dict:
    """Extract investment data from OCR text using regex."""
    data = {
        "ticker": "UNKNOWN",
        "asset_type": "stock",
        "quantity": 0.0,
        "buy_price": 0.0,
        "buy_currency": "IDR",
        "buy_date": datetime.now()
    }

    # Ticker: Uppercase 3-5 chars
    ticker_match = re.search(r'\b([A-Z]{3,6})\b', text)
    if ticker_match:
        data["ticker"] = ticker_match.group(1)

    # Asset Type
    lower_text = text.lower()
    if any(k in lower_text for k in ["crypto", "btc", "eth", "usdt"]):
        data["asset_type"] = "crypto"
    elif any(k in lower_text for k in ["gold", "emas", "antam"]):
        data["asset_type"] = "gold"

    # Quantity: decimal number before 'lot' or 'units' or after 'qty'
    qty_match = re.search(r'(?:qty|quantity)[:\s]*([\d.,]+)', lower_text) or \
                re.search(r'([\d.,]+)\s*(?:lot|unit|shares)', lower_text)
    if qty_match:
        try:
            val = qty_match.group(1).replace(',', '')
            data["quantity"] = Decimal(val)
        except: pass

    # Price
    price_match = re.search(r'(?:price|harga|buy price)[:\s]*(?:rp|idr|usd)?\s*([\d.,]+)', lower_text)
    if price_match:
        try:
            val = price_match.group(1).replace(',', '')
            data["buy_price"] = Decimal(val)
        except: pass

    if "usd" in lower_text or "$" in lower_text:
        data["buy_currency"] = "USD"

    # Date
    from apps.cli.receipt_reader.core.parser import _extract_date
    data["buy_date"] = _extract_date(text)

    return data

def process_image(file_path):
    filename = os.path.basename(file_path)
    is_expense = filename.lower().startswith("expense")
    is_investment = filename.lower().startswith("investment") or "recheck_history_portofolio" in filename.lower()

    if not (is_expense or is_investment):
        logger.info(f"   Skipping {filename}: Not recognized as Expense or Investment")
        return True

    logger.info(f"   Processing {filename} with OCREnsemble...")

    try:
        # Run OCR Ensemble
        result = ensemble.run(str(file_path), verbose=False)
        best_text = result.best_text

        if not best_text.strip():
            logger.error(f"      Error: No text extracted from {filename}")
            return False

        if is_expense:
            receipt_results = parser.parse_all(best_text)
            if not receipt_results:
                logger.error(f"      Error: No receipt data parsed from {filename}")
                return False

            for rd in receipt_results:
                exp = Expense(
                    amount=float(rd.total_amount.amount),
                    description=rd.merchant_name,
                    category=ExpenseCategory(rd.category.value if hasattr(rd.category, 'value') else str(rd.category).lower()),
                    payment_method=ExpensePaymentMethod(rd.payment_method.value if hasattr(rd.payment_method, 'value') else str(rd.payment_method).lower()),
                    date=rd.transaction_date
                )
                res = exp_repo.save(exp)
                logger.info(f"      Saved Expense: {exp.description} | {exp.amount} {exp.category.value} (ID: {res})")
        else:
            # Try to see if it's JSON first (sometimes OCR engines produce it if prompts were in image, unlikely but possible)
            data = None
            if best_text.strip().startswith("{"):
                try: data = json.loads(best_text)
                except: pass

            if not data:
                data = parse_investment_text(best_text)

            inv = Investment(
                asset_type=data.get('asset_type', 'stock').lower(),
                ticker=data.get('ticker', 'UNKNOWN').upper(),
                quantity=Decimal(str(data.get('quantity', 0))),
                buy_price=Decimal(str(data.get('buy_price', 0))),
                buy_currency=data.get('buy_currency', 'IDR').upper(),
                buy_date=data.get('buy_date', datetime.now())
            )
            res = inv_repo.save(inv)
            logger.info(f"      Saved Investment: {inv.ticker} | {inv.quantity} units @ {inv.buy_price} {inv.buy_currency} (ID: {res})")

        # Move to archive
        os.rename(file_path, ARCHIVE_DIR / filename)
        return True

    except Exception as e:
        logger.error(f"      Error processing {filename}: {e}", exc_info=True)
        return False

def main():
    if not os.path.exists(IMAGE_DIR):
        logger.error(f"Error: Directory {IMAGE_DIR} not found.")
        return

    images = [os.path.join(IMAGE_DIR, f) for f in os.listdir(IMAGE_DIR)
              if f.lower().endswith(('.jpg', '.jpeg', '.png'))]

    if not images:
        logger.info("No images found in images/New.")
        return

    logger.info(f"Found {len(images)} images to process.")

    success_count = 0
    for img in images:
        if process_image(img):
            success_count += 1

    logger.info(f"\nFinished. Successfully processed {success_count}/{len(images)} images.")

if __name__ == "__main__":
    main()
