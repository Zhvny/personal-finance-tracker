import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import * as matchers from "@testing-library/jest-dom/matchers";

expect.extend(matchers);

// Mocks
const mockApiFetch = vi.fn();
let mockCacheFetchReturn = { data: null, loading: false, error: null, isStale: false };
let mockTickerReturn = { data: null, loading: false, error: null, analyze: vi.fn(), clearError: vi.fn() };

vi.mock("../src/finance/useApi.js", () => ({
  apiFetch: (...args) => mockApiFetch(...args),
  useCacheFetch: () => mockCacheFetchReturn,
  useDebounce: (v) => v,
  useWebSocket: () => ({ lastMessage: null }),
  usePersistedTab: (key, def) => [def, vi.fn()],
  useUniverseAudit: () => ({ data: null, loading: false, reload: vi.fn() }),
  downloadCSV: vi.fn(),
  API_BASE: "http://localhost:8444/api",
  useAIStatus: () => ({ status: { active_provider: "rules" }, loading: false, setProvider: vi.fn() }),
  apiScanReceipt: vi.fn(),
  apiScanReceiptAI: vi.fn(),
  apiExportReceipt: vi.fn(),
}));

vi.mock("../src/finance/TickerContext.jsx", () => ({
  useTicker: () => mockTickerReturn,
  TickerProvider: ({ children }) => <div>{children}</div>,
}));

import GeneticPortfolioLab from "../src/pages/GeneticPortfolioLab.jsx";
import StockML from "../src/pages/stock_ml.jsx";
import StockAnalyzer from "../src/pages/stock_analyzer.jsx";
import ReceiptReader from "../src/pages/receipt_reader.jsx";

describe("Page Error Awareness", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCacheFetchReturn = { data: null, loading: false, error: null, isStale: false };
    mockTickerReturn = { data: null, loading: false, error: null, analyze: vi.fn(), clearError: vi.fn() };
  });

  describe("GeneticPortfolioLab Error Awareness", () => {
    it("renders an error UI banner when loading genetic portfolio data fails with Error object", async () => {
      mockApiFetch.mockRejectedValue(new Error("Internal Server Error (500)"));

      render(<GeneticPortfolioLab onToast={vi.fn()} />);

      await waitFor(() => {
        expect(screen.getByText(/Gagal Mengambil Data AI Portfolio Lab/i)).toBeInTheDocument();
      });

      expect(screen.getByText(/Internal Server Error \(500\)/i)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Coba Lagi/i })).toBeInTheDocument();
    });
  });

  describe("StockML Error Awareness", () => {
    it("renders error state when ML predictions API fails with Error object", async () => {
      mockApiFetch.mockRejectedValue(new Error("Failed to connect to ML model backend"));

      render(<StockML />);

      await waitFor(() => {
        expect(screen.getByText(/ML PREDICTION ENGINE ERROR/i)).toBeInTheDocument();
      });

      expect(screen.getByText(/Failed to connect to ML model backend/i)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Coba Lagi/i })).toBeInTheDocument();
    });
  });

  describe("StockAnalyzer Error Awareness", () => {
    it("renders error state safely when stock analyzer receives Error object without breaking React tree", async () => {
      mockTickerReturn = { 
        data: null, 
        loading: false, 
        error: new Error("Server error 500: Database lock timeout"), 
        analyze: vi.fn(), 
        clearError: vi.fn() 
      };

      render(<StockAnalyzer />);

      expect(screen.getByText(/Gagal Menganalisis Ticker/i)).toBeInTheDocument();
      expect(screen.getByText(/Server error 500: Database lock timeout/i)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /Coba Lagi/i })).toBeInTheDocument();
    });
  });

  describe("ReceiptReader Error Awareness", () => {
    it("renders dropzone and scanner interface safely", async () => {
      const { container } = render(<ReceiptReader onToast={vi.fn()} />);

      expect(container.querySelector(".drop-zone")).toBeInTheDocument();
    });
  });
});
