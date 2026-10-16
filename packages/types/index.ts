export enum ExpenseCategory {
  FOOD = "food",
  TRANSPORT = "transport",
  HOUSING = "housing",
  ENTERTAINMENT = "entertainment",
  HEALTH = "health",
  SHOPPING = "shopping",
  EDUCATION = "education",
  INVESTMENT = "investment",
  OTHER = "other",
}

export enum PaymentMethod {
  CASH = "cash",
  DEBIT_CARD = "debit-card",
  CREDIT_CARD = "credit-card",
  E_WALLET = "e-wallet",
  BANK_TRANSFER = "bank-transfer",
  OVO = "ovo",
  GOPAY = "gopay",
  SHOPEEPAY = "shopeepay",
  QRIS = "qris",
}

export interface Expense {
  id?: number;
  amount: number;
  description: string;
  category: ExpenseCategory;
  payment_method: PaymentMethod;
  date: string; // ISO format
  is_recurring: boolean;
  recurring_period?: string;
}

export enum IncomeType {
  SALARY = "salary",
  FREELANCE = "freelance",
  INVESTMENT = "investment",
  SIDE_HUSTLE = "side-hustle",
  TRANSFER = "transfer",
  OTHER = "other",
}

export interface Income {
  id?: number;
  amount: number;
  source: string;
  income_type: IncomeType;
  date: string;
  description?: string;
  is_taxed: boolean;
}

export enum InvestmentStatus {
  HOLDING = "holding",
  SOLD = "sold",
  PARTIAL = "partial",
}

export interface SellTransaction {
  sell_date: string;
  quantity: number;
  sell_price: number;
  sell_currency: string;
  fees: number;
  realized_pl: number;
  realized_pl_pct: number;
}

export interface Investment {
  id?: number;
  asset_type: string;
  ticker: string;
  quantity: number;
  buy_price: number;
  buy_currency: string;
  buy_price_idr?: number;
  buy_date: string;
  status: InvestmentStatus;
  is_favorite: boolean;
  remaining_quantity: number;
  sells: SellTransaction[];
}
