import React from "react";
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import * as matchers from "@testing-library/jest-dom/matchers";
import TrendChart from "../src/finance/TrendChart.jsx";

expect.extend(matchers);

const mockSeries = [
  {
    key: "networth",
    label: "Net Worth",
    color: "#6366f1",
    data: [
      { label: "2026-07-01", value: 1000 },
      { label: "2026-07-02", value: 1500 },
      { label: "2026-07-03", value: 2000 },
    ],
  },
];

describe("TrendChart Premium Visual Enhancements", () => {
  it("renders premium gradient definitions in the SVG defs block", () => {
    const { container } = render(<TrendChart series={mockSeries} title="Test Chart" />);
    
    const defsEl = container.querySelector("defs");
    expect(defsEl).toBeInTheDocument();
    
    // Verify linear gradient element exists for the series key
    const gradEl = container.querySelector("#grad-networth");
    expect(gradEl).toBeInTheDocument();
  });

  it("applies the linear gradient fill to the area path", () => {
    const { container } = render(<TrendChart series={mockSeries} title="Test Chart" />);
    
    const areaPath = container.querySelector('path[d*="L"][fill*="url(#grad-networth)"]');
    expect(areaPath).toBeInTheDocument();
  });

  it("renders a glow path layer below the main line path for premium styling", () => {
    const { container } = render(<TrendChart series={mockSeries} title="Test Chart" />);
    
    const glowPath = container.querySelector('path[key*="networth-glow"], [stroke-opacity="0.15"], [stroke-opacity="0.2"]');
    expect(glowPath).toBeInTheDocument();
  });
});
