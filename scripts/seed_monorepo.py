import asyncio
from datetime import datetime

from packages.database.index import connect, db, disconnect


async def seed():
    await connect()

    # Check if data exists
    count = await db.expense.count()
    if count == 0:
        print("Seeding sample expenses...")
        await db.expense.create(data={
            "amount": 50000,
            "description": "Lunch at Warung",
            "category": "food",
            "payment_method": "cash",
            "date": datetime.now()
        })
        await db.expense.create(data={
            "amount": 150000,
            "description": "Internet Monthly",
            "category": "housing",
            "payment_method": "bank-transfer",
            "date": datetime.now()
        })
        print("Seed complete.")
    else:
        print("Database already has data.")

    await disconnect()

if __name__ == "__main__":
    asyncio.run(seed())
