import psycopg2
import os

conn = psycopg2.connect(os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/finance_tracker"))
conn.autocommit = True
cur = conn.cursor()

merchants = [
    ("STARBUCKS", "Starbucks", "Food & Dining", 0.95),
    ("STARBUCKS #", "Starbucks", "Food & Dining", 0.90),
    ("AMZN MKTP", "Amazon", "Shopping", 0.95),
    ("AMAZON.COM", "Amazon", "Shopping", 0.95),
    ("AMZN", "Amazon", "Shopping", 0.85),
    ("WALMART", "Walmart", "Shopping", 0.95),
    ("WAL-MART", "Walmart", "Shopping", 0.90),
    ("TARGET", "Target", "Shopping", 0.95),
    ("CVS PHARMACY", "CVS", "Health", 0.90),
    ("CVS", "CVS", "Health", 0.85),
    ("SHELL OIL", "Shell", "Transportation", 0.95),
    ("SHELL", "Shell", "Transportation", 0.85),
    ("CHEVRON", "Chevron", "Transportation", 0.95),
    ("EXXONMOBIL", "ExxonMobil", "Transportation", 0.95),
    ("MCDONALDS", "McDonalds", "Food & Dining", 0.95),
    ("MCDONALD'S", "McDonalds", "Food & Dining", 0.90),
    ("UBER *TRIP", "Uber", "Transportation", 0.95),
    ("UBER EATS", "Uber Eats", "Food & Dining", 0.95),
    ("GRAB", "Grab", "Transportation", 0.95),
    ("GOJEK", "Gojek", "Transportation", 0.95),
    ("TOSS", "Toss", "Financial", 0.90),
    ("OVO", "OVO", "Financial", 0.95),
    ("GOPAY", "GoPay", "Financial", 0.95),
    ("SHOPEEPAY", "ShopeePay", "Financial", 0.95),
    ("DANA", "Dana", "Financial", 0.95),
    ("NETFLIX", "Netflix", "Entertainment", 0.95),
    ("SPOTIFY", "Spotify", "Entertainment", 0.95),
    ("DISNEY+", "Disney+", "Entertainment", 0.95),
    ("HBO MAX", "HBO Max", "Entertainment", 0.95),
    ("MICROSOFT", "Microsoft", "Subscriptions", 0.95),
    ("APPLE.COM", "Apple", "Subscriptions", 0.95),
    ("GOOGLE", "Google", "Subscriptions", 0.90),
]

for m in merchants:
    cur.execute(
        """INSERT INTO merchant_mapping (raw_merchant, normalized_merchant, category, confidence_score)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT DO NOTHING""",
        m,
    )
print(f"Inserted {len(merchants)} merchant mappings")
