from .database import Database


class InvestmentRepository:
    def __init__(self, db_resolver):
        self.db_path = db_resolver("investment_tracker", "portfolio.db")

    def get_by_id(self, inv_id):
        rows = Database.query(self.db_path, "SELECT * FROM investments WHERE id=?", (inv_id,))
        return rows[0] if rows else None

    def add(self, asset_type, ticker, quantity, buy_price, buy_currency, buy_date):
        return Database.execute(self.db_path,
            "INSERT INTO investments (asset_type,ticker,quantity,buy_price,buy_currency,buy_date,status,remaining_quantity)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (asset_type, ticker.upper(), quantity, buy_price, buy_currency, buy_date, "holding", quantity))

    def update_status(self, inv_id, status, remaining):
        return Database.execute(self.db_path,
            "UPDATE investments SET status=?, remaining_quantity=? WHERE id=?",
            (status, remaining, inv_id))

    def add_sell_transaction(self, inv_id, ticker, date, qty, price, curr, fees, pl_idr, pl_pct):
        return Database.execute(self.db_path,
            "INSERT INTO sell_transactions (investment_id,ticker,sell_date,quantity,sell_price,sell_currency,fees,realized_pl_idr,realized_pl_pct)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (inv_id, ticker, date, qty, price, curr, fees, pl_idr, pl_pct))

    def delete(self, inv_id):
        return Database.execute(self.db_path, "DELETE FROM investments WHERE id=?", (inv_id,))

class IncomeRepository:
    def __init__(self, db_resolver):
        self.db_path = db_resolver("income_tracker", "income.db")

    def add(self, amount, source, income_type, date, description, is_taxed=False):
        return Database.execute(self.db_path,
            "INSERT INTO incomes (amount, source, income_type, date, description, is_taxed)"
            " VALUES (?,?,?,?,?,?)",
            (amount, source, income_type, date, description, is_taxed))
