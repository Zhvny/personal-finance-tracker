import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import * as matchers from "@testing-library/jest-dom/matchers";
import { Empty } from "../src/components.jsx";
import ExpenseTracker from "../src/pages/expense_tracker.jsx";
import IncomeTracker from "../src/pages/income_tracker.jsx";
import InvestmentTracker from "../src/pages/investment_tracker.jsx";

expect.extend(matchers);

// Mock useApi hooks
vi.mock("../src/finance/useApi.js", () => ({
  useExpenses: () => ({ data: [], loading: false, error: null, reload: vi.fn() }),
  useExpenseSummary: () => ({ data: { total: 0, count: 0, by_category: {} }, loading: false }),
  useExpenseBudget: () => ({ data: { budgets: [] }, loading: false }),
  useExpenseTrend: () => ({ data: [], loading: false }),
  
  useIncome: () => ({ data: [], loading: false, error: null, reload: vi.fn() }),
  useIncomeSummary: () => ({ data: { total: 0, count: 0, by_category: {} }, loading: false }),
  useIncomeTax: () => ({ data: { bracket: 0, tax: 0, rate: 0 }, loading: false }),
  useIncomeTrend: () => ({ data: [], loading: false }),
  
  useInvestments: () => ({ data: [], loading: false, error: null, reload: vi.fn() }),
  useRealized: () => ({ data: [], loading: false, error: null }),
  useInvHistory: () => ({ data: [], loading: false, error: null }),
  useFxRate: () => ({ data: 16500, loading: false }),

  usePersistedTab: (key, def) => [def, vi.fn()],
  downloadCSV: vi.fn(),
  useDebounce: (val) => val,
}));

describe("Empty Component - Financial Theme Illustration", () => {
  it("renders a wallet-themed SVG illustration for the generic variant by default", () => {
    const { container } = render(<Empty msg="No data" />);
    expect(container.querySelector(".empty-state")).toBeInTheDocument();
    expect(container.querySelector("svg")).toBeInTheDocument();
    expect(container.querySelector(".es-wallet-body")).toBeInTheDocument();
  });

  it("renders a receipt-themed SVG illustration for the expense variant", () => {
    const { container } = render(<Empty variant="expense" msg="No expenses" />);
    expect(container.querySelector(".empty-state")).toBeInTheDocument();
    // EmptySVGExpense has es-float animation class
    expect(container.querySelector(".es-float")).toBeInTheDocument();
  });

  it("renders a coin-themed SVG illustration for the income variant", () => {
    const { container } = render(<Empty variant="income" msg="No income" />);
    expect(container.querySelector(".empty-state")).toBeInTheDocument();
    // EmptySVGIncome has ei-coin animation class
    expect(container.querySelector(".ei-coin")).toBeInTheDocument();
  });

  it("renders a chart-themed SVG illustration for the investment variant", () => {
    const { container } = render(<Empty variant="investment" msg="No investments" />);
    expect(container.querySelector(".empty-state")).toBeInTheDocument();
    // EmptySVGInvestment has inv-line animation class
    expect(container.querySelector(".inv-line")).toBeInTheDocument();
  });
});

describe("ExpenseTracker - Table Empty State Integration", () => {
  it("renders the premium receipt-themed SVG empty state when there are no expenses (instead of a plain icon)", () => {
    const { container } = render(<ExpenseTracker onToast={vi.fn()} />);
    expect(container.querySelector(".es-float")).toBeInTheDocument();
  });
});

describe("IncomeTracker - Table Empty State Integration", () => {
  it("renders the premium coin-themed SVG empty state when there are no income records (instead of a plain icon)", () => {
    const { container } = render(<IncomeTracker onToast={vi.fn()} />);
    expect(container.querySelector(".ei-coin")).toBeInTheDocument();
  });
});

describe("InvestmentTracker - Table Empty State Integration", () => {
  it("renders the premium chart-themed SVG empty state when there are no investments (instead of a plain icon)", () => {
    const { container } = render(<InvestmentTracker onToast={vi.fn()} />);
    expect(container.querySelector(".inv-line")).toBeInTheDocument();
  });
});
