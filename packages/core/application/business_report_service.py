
import pandas as pd

from packages.core.infrastructure.config import Config
from packages.core.infrastructure.persistence.database import Database


class BusinessReportService:
    """
    Service for generating business-specific reports.
    """
    def __init__(self):
        # Reports saved in the business profile root
        self.output_dir = Config.get_cli_data_root() / "reports"

    def generate_quarterly_report(self, year: int, quarter: int) -> str:
        """
        Generates an Excel report for the specified year and quarter.
        Queries data from the 'business' schema via the Database class.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)

        start_month = (quarter - 1) * 3 + 1
        end_month = start_month + 3

        start_date = f"{year}-{start_month:02d}-01"
        if end_month > 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{end_month:02d}-01"

        # SQL using '?' placeholders for safety (Database class translates to %s for Postgres)
        income_sql = "SELECT date, income_type AS category, amount, description FROM incomes WHERE date >= ? AND date < ?"
        expense_sql = "SELECT date, category, amount, description FROM expenses WHERE date >= ? AND date < ?"

        # Database.query redirects to the active profile schema in Postgres
        # or the profile-specific .db file in SQLite.
        incomes = Database.query(Config.get_db_path("income"), income_sql, (start_date, end_date))
        expenses = Database.query(Config.get_db_path("expense"), expense_sql, (start_date, end_date))

        df_inc = pd.DataFrame(incomes)
        df_exp = pd.DataFrame(expenses)

        file_path = self.output_dir / f"quarterly_{year}_Q{quarter}.xlsx"

        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            if not df_inc.empty:
                df_inc.to_excel(writer, sheet_name='Income', index=False)
            else:
                pd.DataFrame(columns=['date', 'income_type', 'amount', 'description']).to_excel(writer, sheet_name='Income', index=False)

            if not df_exp.empty:
                df_exp.to_excel(writer, sheet_name='Expense', index=False)
            else:
                pd.DataFrame(columns=['date', 'category', 'amount', 'description']).to_excel(writer, sheet_name='Expense', index=False)

            # Summary Sheet
            summary_data = {
                'Metric': ['Total Income', 'Total Expense', 'Net Profit'],
                'Amount': [
                    df_inc['amount'].sum() if not df_inc.empty else 0,
                    df_exp['amount'].sum() if not df_exp.empty else 0,
                    0
                ]
            }
            summary_data['Amount'][2] = summary_data['Amount'][0] - summary_data['Amount'][1]
            pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)

        return str(file_path)
