Last Updated: 29-05-2026 (14:30)

---
title: "Sankey Cashflow Visuals"
created: "2026-05-23T23:30:00Z"
status: "approved"
authors: ["Gemini CLI", "User"]
type: "design"
design_depth: "deep"
task_complexity: "medium"
---

# Sankey Cashflow Visuals Design Document

## Problem Statement
While the dashboard provides category lists and line charts, it lacks a "Path of Money" visualization. Users cannot easily see how different income sources flow through the system and split into various expense categories and savings. A Sankey diagram provides this "flow" clarity at a glance.

## Requirements

### Functional Requirements
- **REQ-1 (Granular Sources):** Show individual income types (Salary, Dividend, etc.) as source nodes.
- **REQ-2 (Categorized Outflow):** Show expense categories as destination nodes.
- **REQ-3 (Deficit Balancing):** If expenses exceed income, show a "Savings/Credit" node on the left side to balance the flow.
- **REQ-4 (Surplus Balancing):** If income exceeds expenses, show a "Savings" node on the right side to capture the surplus.
- **REQ-5 (Integration):** Display the Sankey diagram on the main Dashboard.

### Non-Functional Requirements
- **REQ-6 (Visual Consistency):** Use existing `CAT_COLOR` palette for expense links.
- **REQ-7 (Performance):** Ensure the diagram renders efficiently without blocking the UI thread.
- **REQ-8 (Interactivity):** Hover effects to highlight specific paths and show numeric totals.

## Architecture

### Component Structure
- **Frontend Component:** `packages/web/src/finance/SankeyChart.jsx`
- **Logic Hook:** `packages/web/src/finance/useApi.js` -> `useSankeyData`
- **Library:** `d3-sankey` for layout mathematics.

### Data Flow
1. `useSankeyData` fetches transactions/summary for the active month.
2. Data is transformed into a `nodes` and `links` JSON structure.
3. `d3-sankey` calculates the coordinates for each node and the Bezier paths for each link.
4. React renders the `<svg>` using the calculated coordinates.

### Color Mapping
- **Income Nodes:** Green theme (`var(--gr)`).
- **Expense Links:** Map to `CAT_COLOR[category]`.
- **Balancing Nodes:** Neutral/Warning colors (`var(--tx3)` for deficit source, `var(--gr)` for surplus savings).

## Design Decisions
- **D3-Sankey (Approach 3):** Use D3 for the math only. React remains the DOM renderer. This ensures we don't have "two masters" of the DOM and keeps the component "React-native."
- **Fixed Width/Fluid Height:** The chart will match the `TrendChart` width but allow height to scale based on the number of categories to prevent vertical compression.
- **Zero-Dependency Styling:** Links and nodes styled via CSS variables to support light/dark mode out of the box.

## Agent Team
- **Coder:** Implement the Sankey component and data hooks.
- **Tester:** Verify the math for balanced/unbalanced months.

## Risk Assessment
- **Layout Complexity:** Very small income/expense slices might result in unreadable nodes. *Mitigation: Minimum node height in D3-Sankey config.*
- **Circular Dependencies:** Sankey diagrams cannot handle circular flows. *Mitigation: Financial data is naturally a directed acyclic graph (DAG) from source to sink.*

## Success Criteria
1. Diagram correctly balances income and expenses.
2. Hovering over a path displays the exact monetary value.
3. Dark/Light mode support is preserved.
