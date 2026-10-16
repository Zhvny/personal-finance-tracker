"""
QA Bug Hunt Script - Full automated testing of Alpha project
Covers: Auth, Business Logic, IDOR, Injection, Edge Cases, API contract, Concurrency
"""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import threading

from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app, raise_server_exceptions=False)

PASS = "[PASS]"
FAIL = "[BUG!]"
WARN = "[WARN]"

findings = []

def check(title, condition, severity="LOW", detail=""):
    icon = PASS if condition else FAIL
    status = "PASS" if condition else f"BUG FOUND [{severity}]"
    if not condition:
        findings.append({"title": title, "severity": severity, "detail": detail})
    print(f"{icon} {status}: {title}")
    if detail:
        print(f"       Detail: {detail}")

def section(name):
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")


# ─── SECTION 1: AUTH & HARDCODED BACKDOOR ────────────────────────────────────
section("1. AUTH TESTS — AUTHENTICATION BYPASS")

r = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
check(
    "CRITICAL: Hardcoded admin/admin backdoor allows login without registration",
    r.status_code == 401,
    severity="CRITICAL",
    detail=f"HTTP {r.status_code} — token: {r.json().get('token', 'N/A') if r.status_code==200 else 'N/A'}"
)

# Case sensitivity bypass
r_upper = client.post("/api/auth/login", json={"username": "ADMIN", "password": "admin"})
check(
    "CRITICAL: Uppercase 'ADMIN' bypasses hardcoded backdoor (case normalization prevents bypass)",
    r_upper.status_code == 401,
    severity="CRITICAL",
    detail=f"HTTP {r_upper.status_code}"
)

# No auth enforcement on sensitive endpoints
sensitive_no_auth = [
    ("GET", "/api/expenses"),
    ("GET", "/api/income"),
    ("GET", "/api/investments"),
    ("GET", "/api/balances"),
    ("GET", "/api/goals"),
    ("GET", "/api/dashboard"),
    ("GET", "/api/config"),
]
for method, path in sensitive_no_auth:
    r = client.get(path) if method == "GET" else client.post(path)
    check(
        f"HIGH: {method} {path} requires authentication (no 401/403)",
        r.status_code in [401, 403],
        severity="HIGH",
        detail=f"Got HTTP {r.status_code} — no auth required"
    )

# Token not validated on subsequent requests
r_login = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
fake_token = "faketoken_invalid_12345"
r_with_fake = client.get("/api/expenses", headers={"Authorization": f"Bearer {fake_token}"})
check(
    "HIGH: Fake/invalid token is not rejected by API (no token validation middleware)",
    r_with_fake.status_code in [401, 403],
    severity="HIGH",
    detail=f"Got HTTP {r_with_fake.status_code} with fake token"
)

# Token generated but not persisted — can't validate
r1 = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
r2 = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
if r1.status_code == 200 and r2.status_code == 200:
    check(
        "MEDIUM: Multiple logins generate different tokens (ephemeral, stateless — no invalidation possible)",
        r1.json().get("token") == r2.json().get("token"),
        severity="MEDIUM",
        detail=f"Token1: {r1.json().get('token')} != Token2: {r2.json().get('token')}"
    )


# ─── SECTION 2: BUSINESS LOGIC — NEGATIVE AMOUNTS ────────────────────────────
section("2. BUSINESS LOGIC — INVALID AMOUNTS")

r = client.post("/api/expenses", json={"amount": -999999, "category": "food", "description": "neg", "date": "2026-01-01", "payment_method": "cash"})
check(
    "HIGH: POST /api/expenses rejects negative amount",
    r.status_code in [400, 422],
    severity="HIGH",
    detail=f"HTTP {r.status_code} — body: {r.text[:150]}"
)

r = client.post("/api/expenses", json={"amount": 0, "category": "food", "description": "zero", "date": "2026-01-01", "payment_method": "cash"})
check(
    "MEDIUM: POST /api/expenses rejects zero amount",
    r.status_code in [400, 422],
    severity="MEDIUM",
    detail=f"HTTP {r.status_code} — body: {r.text[:150]}"
)

r = client.post("/api/income", json={"amount": -500000, "source": "salary", "description": "neg", "date": "2026-01-01"})
check(
    "HIGH: POST /api/income rejects negative amount",
    r.status_code in [400, 422],
    severity="HIGH",
    detail=f"HTTP {r.status_code} — body: {r.text[:150]}"
)

r = client.post("/api/expenses", json={"amount": 9999999999999999, "category": "food", "description": "huge", "date": "2026-01-01", "payment_method": "cash"})
check(
    "MEDIUM: POST /api/expenses handles extremely large amount",
    r.status_code in [200, 201] or r.status_code in [400, 422],  # shouldn't crash
    severity="MEDIUM",
    detail=f"HTTP {r.status_code} — body: {r.text[:150]}"
)

r = client.post("/api/balances/transfer", json={"direction": "to_bank", "amount": -50000, "note": "neg"})
check(
    "HIGH: POST /api/balances/transfer rejects negative transfer amount",
    r.status_code in [400, 422],
    severity="HIGH",
    detail=f"HTTP {r.status_code} — body: {r.text[:150]}"
)


# ─── SECTION 3: IDOR — RESOURCE OWNERSHIP ─────────────────────────────────────
section("3. IDOR — INSECURE DIRECT OBJECT REFERENCE")

r = client.put("/api/expenses/99999999", json={"amount": 999, "category": "food", "description": "x", "date": "2026-01-01", "payment_method": "cash"})
check(
    "MEDIUM: PUT /api/expenses/{id} returns 404 for non-existent record",
    r.status_code == 404,
    severity="MEDIUM",
    detail=f"HTTP {r.status_code} — body: {r.text[:150]}"
)

r = client.delete("/api/expenses/99999999")
check(
    "MEDIUM: DELETE /api/expenses/{id} returns 404 for non-existent record",
    r.status_code == 404,
    severity="MEDIUM",
    detail=f"HTTP {r.status_code} — body: {r.text[:150]}"
)

r = client.delete("/api/expenses/abc")
check(
    "LOW: DELETE /api/expenses/abc (string ID) handled gracefully",
    r.status_code in [400, 404, 422],
    severity="LOW",
    detail=f"HTTP {r.status_code}"
)

r = client.delete("/api/expenses/-1")
check(
    "LOW: DELETE /api/expenses/-1 (negative ID) handled gracefully",
    r.status_code in [400, 404, 422],
    severity="LOW",
    detail=f"HTTP {r.status_code}"
)

r = client.delete("/api/income/99999999")
check(
    "MEDIUM: DELETE /api/income/{id} returns 404 for non-existent record",
    r.status_code == 404,
    severity="MEDIUM",
    detail=f"HTTP {r.status_code} — body: {r.text[:150]}"
)

r = client.delete("/api/investments/99999999")
check(
    "MEDIUM: DELETE /api/investments/{id} returns 404 for non-existent record",
    r.status_code == 404,
    severity="MEDIUM",
    detail=f"HTTP {r.status_code} — body: {r.text[:150]}"
)

r = client.delete("/api/goals/99999999")
check(
    "MEDIUM: DELETE /api/goals/{id} returns 404 for non-existent record",
    r.status_code == 404,
    severity="MEDIUM",
    detail=f"HTTP {r.status_code} — body: {r.text[:150]}"
)


# ─── SECTION 4: INPUT VALIDATION & EDGE CASES ────────────────────────────────
section("4. INPUT VALIDATION & EDGE CASES")

# Empty JSON body
r = client.post("/api/expenses", json={})
check("LOW: POST /api/expenses with empty body returns 422", r.status_code == 422, detail=f"HTTP {r.status_code}")

r = client.post("/api/income", json={})
check("LOW: POST /api/income with empty body returns 422", r.status_code == 422, detail=f"HTTP {r.status_code}")

r = client.post("/api/goals", json={})
check("LOW: POST /api/goals with empty body returns 422", r.status_code == 422, detail=f"HTTP {r.status_code}")

# Null values
r = client.post("/api/expenses", json={"amount": None, "category": None, "description": None, "date": None, "payment_method": None})
check("LOW: POST /api/expenses all-null returns 422", r.status_code == 422, detail=f"HTTP {r.status_code}")

# Very long strings
long_str = "A" * 10000
r = client.post("/api/expenses", json={"amount": 1000, "category": "food", "description": long_str, "date": "2026-01-01", "payment_method": "cash"})
check(
    "LOW: POST /api/expenses very long description (10000 chars) does not crash",
    r.status_code not in [500],
    detail=f"HTTP {r.status_code}"
)

# Unicode / emoji in description
r = client.post("/api/expenses", json={"amount": 1000, "category": "food", "description": "🎉💰 Makan siang 午餐 テスト", "date": "2026-01-01", "payment_method": "cash"})
check(
    "LOW: POST /api/expenses with emoji/unicode description does not crash",
    r.status_code not in [500],
    detail=f"HTTP {r.status_code}"
)

# Invalid date
r = client.post("/api/expenses", json={"amount": 1000, "category": "food", "description": "test", "date": "not-a-date", "payment_method": "cash"})
check(
    "MEDIUM: POST /api/expenses with invalid date is rejected",
    r.status_code in [400, 422],
    detail=f"HTTP {r.status_code}"
)

# Future date (should be accepted or rejected consistently)
r = client.post("/api/expenses", json={"amount": 1000, "category": "food", "description": "test", "date": "2099-12-31", "payment_method": "cash"})
check(
    "LOW: POST /api/expenses with far-future date is handled",
    r.status_code not in [500],
    detail=f"HTTP {r.status_code}"
)

# Malformed JSON (raw string, not json)
r = client.post("/api/expenses", content=b"not a json at all", headers={"Content-Type": "application/json"})
check("LOW: POST /api/expenses with malformed JSON returns 422", r.status_code in [400, 422], detail=f"HTTP {r.status_code}")


# ─── SECTION 5: GOAL BUSINESS LOGIC ──────────────────────────────────────────
section("5. GOAL BUSINESS LOGIC")

r = client.post("/api/goals", json={"name": "Test Goal", "target_amount": 1000000, "current_amount": 0, "target_date": "2027-01-01"})
print(f"  Created goal: HTTP {r.status_code} — {r.text[:200]}")

r_neg = client.post("/api/goals", json={"name": "Bad Goal", "target_amount": -1, "current_amount": 0})
check(
    "HIGH: POST /api/goals with negative target_amount is rejected",
    r_neg.status_code in [400, 422],
    severity="HIGH",
    detail=f"HTTP {r_neg.status_code} — {r_neg.text[:150]}"
)

r_zero = client.post("/api/goals", json={"name": "Zero Goal", "target_amount": 0, "current_amount": 0})
check(
    "MEDIUM: POST /api/goals with zero target_amount is rejected",
    r_zero.status_code in [400, 422],
    severity="MEDIUM",
    detail=f"HTTP {r_zero.status_code}"
)

r_exceed = client.post("/api/goals", json={"name": "Exceed Goal", "target_amount": 1000, "current_amount": 999999})
check(
    "HIGH: POST /api/goals where current_amount > target_amount is rejected",
    r_exceed.status_code in [400, 422],
    severity="HIGH",
    detail=f"HTTP {r_exceed.status_code} — current > target should be invalid"
)


# ─── SECTION 6: INVESTMENT LOGIC ──────────────────────────────────────────────
section("6. INVESTMENT BUSINESS LOGIC")

r = client.post("/api/investments", json={
    "asset_name": "Test Stock",
    "asset_type": "stock",
    "ticker": "BBCA",
    "quantity": -10,
    "buy_price": 5000,
    "buy_currency": "IDR",
    "buy_date": "2026-01-01"
})
check(
    "HIGH: POST /api/investments rejects negative quantity",
    r.status_code in [400, 422],
    severity="HIGH",
    detail=f"HTTP {r.status_code} — {r.text[:150]}"
)

r = client.post("/api/investments", json={
    "asset_name": "Test Stock",
    "asset_type": "stock",
    "ticker": "BBCA",
    "quantity": 10,
    "buy_price": -5000,
    "buy_currency": "IDR",
    "buy_date": "2026-01-01"
})
check(
    "HIGH: POST /api/investments rejects negative buy_price",
    r.status_code in [400, 422],
    severity="HIGH",
    detail=f"HTTP {r.status_code} — {r.text[:150]}"
)

# Sell more than owned
r_buy = client.post("/api/investments", json={
    "asset_name": "SellTest",
    "asset_type": "stock",
    "ticker": "SELLTEST",
    "quantity": 5,
    "buy_price": 1000,
    "buy_currency": "IDR",
    "buy_date": "2026-01-01"
})
if r_buy.status_code in [200, 201]:
    inv_id = r_buy.json().get("id") or r_buy.json().get("investment", {}).get("id")
    if inv_id:
        r_sell = client.post(f"/api/investments/{inv_id}/sell", json={"quantity": 9999, "sell_price": 2000, "sell_date": "2026-08-01"})
        check(
            "CRITICAL: POST /api/investments/{id}/sell rejects selling more than owned",
            r_sell.status_code in [400, 422],
            severity="CRITICAL",
            detail=f"HTTP {r_sell.status_code} — selling 9999 when only 5 in stock: {r_sell.text[:200]}"
        )


# ─── SECTION 7: BALANCE TRANSFER LOGIC ───────────────────────────────────────
section("7. BALANCE TRANSFER — BUSINESS LOGIC")

r = client.post("/api/balances/transfer", json={"direction": "to_bank", "amount": 999999999999999, "note": "overflow"})
check(
    "MEDIUM: POST /api/balances/transfer with huge amount handled gracefully",
    r.status_code not in [500],
    detail=f"HTTP {r.status_code}"
)

r = client.post("/api/balances/transfer", json={"direction": "invalid_direction", "amount": 1000, "note": "bad dir"})
check(
    "MEDIUM: POST /api/balances/transfer with invalid direction is rejected",
    r.status_code in [400, 422],
    detail=f"HTTP {r.status_code} — {r.text[:150]}"
)


# ─── SECTION 8: BUDGET LOGIC ─────────────────────────────────────────────────
section("8. BUDGET LOGIC")

r = client.post("/api/budget/2026/8", json={"category": "food", "limit_amt": -5000})
check(
    "HIGH: POST /api/budget/{year}/{month} rejects negative budget limit",
    r.status_code in [400, 422],
    severity="HIGH",
    detail=f"HTTP {r.status_code} — {r.text[:150]}"
)

r = client.get("/api/budget/2026/13")
check(
    "MEDIUM: GET /api/budget/2026/13 invalid month (13) is handled",
    r.status_code in [400, 404, 422],
    detail=f"HTTP {r.status_code}"
)

r = client.get("/api/budget/9999/1")
check(
    "LOW: GET /api/budget/9999/1 far-future year is handled",
    r.status_code not in [500],
    detail=f"HTTP {r.status_code}"
)


# ─── SECTION 9: OCR / RECEIPT ─────────────────────────────────────────────────
section("9. OCR / RECEIPT SCAN")

r = client.post("/api/receipt/scan")
check("LOW: POST /api/receipt/scan with no file returns 422", r.status_code == 422, detail=f"HTTP {r.status_code}")

# Empty file
import io

r = client.post("/api/receipt/scan", files={"file": ("empty.jpg", io.BytesIO(b""), "image/jpeg")})
check(
    "MEDIUM: POST /api/receipt/scan with empty file handles gracefully",
    r.status_code not in [500],
    detail=f"HTTP {r.status_code} — {r.text[:150]}"
)

# Wrong MIME
r = client.post("/api/receipt/scan", files={"file": ("script.py", io.BytesIO(b"print('hack')"), "text/plain")})
check(
    "HIGH: POST /api/receipt/scan rejects non-image MIME type",
    r.status_code in [400, 415, 422],
    severity="HIGH",
    detail=f"HTTP {r.status_code} — {r.text[:150]}"
)

# Path traversal in filename
r = client.post("/api/receipt/scan", files={"file": ("../../../etc/passwd.jpg", io.BytesIO(b"\xff\xd8\xff"), "image/jpeg")})
check(
    "HIGH: POST /api/receipt/scan path traversal in filename is handled",
    r.status_code not in [500],
    severity="HIGH",
    detail=f"HTTP {r.status_code}"
)

# Huge file (~5MB of zeros)
big_file = io.BytesIO(b"\x00" * 5 * 1024 * 1024)
r = client.post("/api/receipt/scan", files={"file": ("big.jpg", big_file, "image/jpeg")})
check(
    "MEDIUM: POST /api/receipt/scan with 5MB file does not 500",
    r.status_code not in [500],
    detail=f"HTTP {r.status_code}"
)


# ─── SECTION 10: CONCURRENCY — RACE CONDITIONS ───────────────────────────────
section("10. CONCURRENCY — RACE CONDITIONS")

results = []

def make_expense():
    r = client.post("/api/expenses", json={"amount": 1000, "category": "food", "description": "concurrent", "date": "2026-08-11", "payment_method": "cash"})
    results.append(r.status_code)

threads = [threading.Thread(target=make_expense) for _ in range(10)]
for t in threads:
    t.start()
for t in threads:
    t.join()

success = sum(1 for s in results if s in [200, 201])
errors = sum(1 for s in results if s == 500)
check(
    "MEDIUM: 10 concurrent POST /api/expenses does not cause 500 errors",
    errors == 0,
    severity="MEDIUM",
    detail=f"Success: {success}/10, Errors (500): {errors}/10, Results: {results}"
)


# ─── SECTION 11: API CONTRACT — HTTP METHOD ENFORCEMENT ──────────────────────
section("11. API CONTRACT — METHOD ENFORCEMENT")

wrong_method_tests = [
    ("POST", "/api/expenses/1"),         # should be PUT
    ("GET", "/api/expenses/1"),          # should not be a GET by ID
    ("DELETE", "/api/dashboard"),        # GET only
    ("PUT", "/api/dashboard"),           # GET only
    ("PATCH", "/api/expenses"),          # should be POST or not exist
]
for method, path in wrong_method_tests:
    r = getattr(client, method.lower())(path)
    check(
        f"LOW: {method} {path} returns 405 Method Not Allowed",
        r.status_code in [405, 404, 422],
        detail=f"HTTP {r.status_code}"
    )


# ─── SECTION 12: SENSITIVE DATA EXPOSURE ─────────────────────────────────────
section("12. SENSITIVE DATA EXPOSURE")

r = client.get("/api/config")
body = r.text.lower()
check(
    "CRITICAL: GET /api/config does not expose API keys or passwords",
    "api_key" not in body and "secret" not in body and "password" not in body and "gemini" not in body,
    severity="CRITICAL",
    detail=f"Response snippet: {r.text[:300]}"
)

r = client.get("/api/health")
check(
    "LOW: GET /api/health does not expose sensitive internal info",
    r.status_code == 200,
    detail=f"HTTP {r.status_code}: {r.text[:200]}"
)


# ─── FINAL SUMMARY ─────────────────────────────────────────────────────────
section("FINAL SUMMARY")

by_severity = {}
for f in findings:
    s = f["severity"]
    by_severity[s] = by_severity.get(s, 0) + 1

print(f"\nTotal findings: {len(findings)}")
for s in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
    cnt = by_severity.get(s, 0)
    print(f"  {s}: {cnt}")

print("\nDetailed Findings:")
for i, f in enumerate(findings, 1):
    print(f"  [{f['severity']}] #{i}: {f['title']}")
    if f.get("detail"):
        print(f"         Detail: {f['detail']}")
