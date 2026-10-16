import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import * as matchers from "@testing-library/jest-dom/matchers";
import ButterflyMap from "../src/components/ButterflyMap.jsx";

expect.extend(matchers);

// Set up mutable mock data
let mockCacheFetch = { data: null, loading: false, error: null };
let mockBenchmarkMode = false;
const setBenchmarkModeMock = vi.fn();
const setScaleMock = vi.fn();

vi.mock("../src/finance/useApi.js", () => ({
  useDebounce: (val) => val,
  useCacheFetch: () => mockCacheFetch,
  useWebSocket: () => ({ lastMessage: null })
}));

vi.mock("../src/hooks/useButterflyBenchmark.js", () => ({
  useButterflyBenchmark: () => ({
    benchmarkMode: mockBenchmarkMode,
    setBenchmarkMode: setBenchmarkModeMock,
    metrics: { fps: 58, memory: 45.2 },
    scale: 100,
    setScale: setScaleMock
  })
}));

describe("ButterflyMap component tests", () => {
  beforeEach(() => {
    mockCacheFetch = { data: null, loading: false, error: null };
    mockBenchmarkMode = false;
    vi.clearAllMocks();
  });

  it("renders empty state when no data is loaded", () => {
    mockCacheFetch = { data: null, loading: false, error: null };
    render(<ButterflyMap ticker="AAPL" />);
    
    expect(screen.getByText(/BUTTERFLY EFFECT MAP/i)).toBeInTheDocument();
    expect(screen.getByText(/No significant relationships detected/i)).toBeInTheDocument();
  });

  it("renders loading skeletons when loading is true and no data is cached yet", () => {
    mockCacheFetch = { data: null, loading: true, error: null };
    const { container } = render(<ButterflyMap ticker="AAPL" />);
    
    // Skeletons should be rendered (with shimmer class)
    const skeletons = container.querySelectorAll(".shimmer");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders correlation nodes correctly when data is loaded", () => {
    mockCacheFetch = {
      loading: false,
      error: null,
      data: {
        nodes: [
          { ticker: "MSFT", correlation: 0.75, impact: "High", description: "Tech correlation" },
          { ticker: "SPY", correlation: -0.21, impact: "Low", description: "Index hedge" }
        ],
        edges: []
      }
    };
    
    render(<ButterflyMap ticker="AAPL" />);
    
    // Tickers should be present
    expect(screen.getByText("MSFT")).toBeInTheDocument();
    expect(screen.getByText("SPY")).toBeInTheDocument();

    // Descriptions should be present
    expect(screen.getByText(/Tech correlation/i)).toBeInTheDocument();
    expect(screen.getByText(/Index hedge/i)).toBeInTheDocument();

    // Correlations should be formatted as percentages
    expect(screen.getByText("75.0%")).toBeInTheDocument();
    expect(screen.getByText("-21.0%")).toBeInTheDocument();

    // Impact labels should be shown
    expect(screen.getByText("HIGH IMPACT")).toBeInTheDocument();
    expect(screen.getByText("LOW IMPACT")).toBeInTheDocument();
  });

  it("renders error state when fetchError is present", () => {
    mockCacheFetch = { data: null, loading: false, error: new Error("Network Error") };
    render(<ButterflyMap ticker="AAPL" />);
    
    expect(screen.getByText(/Graph unavailable/i)).toBeInTheDocument();
  });

  it("renders benchmark mode metrics and toggles benchmark scale", () => {
    mockBenchmarkMode = true;
    mockCacheFetch = {
      loading: false,
      error: null,
      data: {
        nodes: [
          { ticker: "MSFT", correlation: 0.75, impact: "High", description: "Tech" }
        ],
        edges: []
      }
    };

    render(<ButterflyMap ticker="AAPL" />);

    // Benchmark mode UI elements
    expect(screen.getByText(/FPS: 58/i)).toBeInTheDocument();
    expect(screen.getByText(/MEM: 45.2MB/i)).toBeInTheDocument();
    expect(screen.getByText(/BENCHMARK ON/i)).toBeInTheDocument();

    // Tapping scale buttons should invoke setScale
    const scale500Button = screen.getByRole("button", { name: "500" });
    expect(scale500Button).toBeInTheDocument();
    fireEvent.click(scale500Button);
    expect(setScaleMock).toHaveBeenCalledWith(500);

    // Clicking benchmark toggle invokes setBenchmarkMode
    const toggleButton = screen.getByRole("button", { name: /BENCHMARK ON/i });
    fireEvent.click(toggleButton);
    expect(setBenchmarkModeMock).toHaveBeenCalledWith(false);
  });
});
