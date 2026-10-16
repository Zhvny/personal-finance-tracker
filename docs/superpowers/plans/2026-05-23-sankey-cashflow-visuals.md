Last Updated: 29-05-2026 (14:30)

# Sankey Cashflow Visuals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement an interactive Sankey diagram on the main dashboard to visualize the flow of income sources into expense categories and savings.

**Architecture:** Use `d3-sankey` for layout calculations and React SVG for rendering. A new hook `useSankeyData` will provide the balanced node/link data structure.

**Tech Stack:** React, D3-Sankey, CSS Variables.

---

### Task 1: Environment Setup & Dependencies

**Files:**
- Modify: `packages/web/package.json`

- [ ] **Step 1: Install d3-sankey**

Run: `npm install d3-sankey --prefix packages/web`

- [ ] **Step 2: Verify installation**

Check `packages/web/package.json` for `"d3-sankey"`.

- [ ] **Step 3: Commit**

```bash
git add packages/web/package.json packages/web/package-lock.json
git commit -m "chore: add d3-sankey dependency"
```

---

### Task 2: Implement useSankeyData Hook

**Files:**
- Modify: `packages/web/src/finance/useApi.js`

- [ ] **Step 1: Add useSankeyData hook**

Add the following to `packages/web/src/finance/useApi.js`:

```javascript
export function useSankeyData(year, month) {
  const { data, loading, error, reload } = useDashboard(year, month);

  const processedData = useMemo(() => {
    if (!data) return null;

    const nodes = [];
    const links = [];
    const income = data.income?.by_type || {}; // Assume API returns this or map from raw if needed
    const expenses = data.expense?.by_category || {};
    
    // Nodes
    const totalNode = { name: "Total Cash" };
    nodes.push(totalNode);

    let totalIn = 0;
    Object.entries(income).forEach(([type, amt]) => {
      nodes.push({ name: type, type: 'income' });
      links.push({ source: type, target: "Total Cash", value: amt });
      totalIn += amt;
    });

    let totalOut = 0;
    Object.entries(expenses).forEach(([cat, amt]) => {
      nodes.push({ name: cat, type: 'expense' });
      links.push({ source: "Total Cash", target: cat, value: amt });
      totalOut += amt;
    });

    // Balancing
    if (totalOut > totalIn) {
      nodes.push({ name: "Savings/Credit", type: 'source' });
      links.push({ source: "Savings/Credit", target: "Total Cash", value: totalOut - totalIn });
    } else if (totalIn > totalOut) {
      nodes.push({ name: "Savings", type: 'sink' });
      links.push({ source: "Total Cash", target: "Savings", value: totalIn - totalOut });
    }

    return { nodes, links };
  }, [data]);

  return { data: processedData, loading, error, reload };
}
```

- [ ] **Step 2: Commit**

```bash
git add packages/web/src/finance/useApi.js
git commit -m "feat: add useSankeyData hook"
```

---

### Task 3: Create SankeyChart Component

**Files:**
- Create: `packages/web/src/finance/SankeyChart.jsx`

- [ ] **Step 1: Implement SankeyChart using d3-sankey**

```javascript
import React, { useMemo } from 'react';
import { sankey, sankeyLinkHorizontal } from 'd3-sankey';
import { CAT_COLOR, fmt } from '../constants.js';

export default function SankeyChart({ data, width = 600, height = 400 }) {
  const { nodes, links } = useMemo(() => {
    const sankeyInstance = sankey()
      .nodeWidth(15)
      .nodePadding(10)
      .extent([[1, 1], [width - 1, height - 5]]);

    // Deep copy to prevent d3 from mutating original data refs
    const graph = {
      nodes: data.nodes.map(d => ({ ...d })),
      links: data.links.map(d => ({
        source: data.nodes.findIndex(n => n.name === d.source),
        target: data.nodes.findIndex(n => n.name === d.target),
        value: d.value
      }))
    };

    return sankeyInstance(graph);
  }, [data, width, height]);

  return (
    <svg width={width} height={height} style={{ overflow: 'visible' }}>
      <g>
        {links.map((link, i) => (
          <path
            key={i}
            d={sankeyLinkHorizontal()(link)}
            fill="none"
            stroke={CAT_COLOR[link.target.name] || 'var(--gr)'}
            strokeOpacity={0.3}
            strokeWidth={Math.max(1, link.width)}
          >
            <title>{`${link.source.name} → ${link.target.name}: ${fmt(link.value)}`}</title>
          </path>
        ))}
      </g>
      <g>
        {nodes.map((node, i) => (
          <g key={i} transform={`translate(${node.x0},${node.y0})`}>
            <rect
              height={node.y1 - node.y0}
              width={node.x1 - node.x0}
              fill={node.type === 'income' ? 'var(--gr)' : node.type === 'expense' ? (CAT_COLOR[node.name] || 'var(--rd)') : 'var(--tx3)'}
              stroke="var(--bg1)"
            />
            <text
              x={node.x0 < width / 2 ? 20 : -5}
              y={(node.y1 - node.y0) / 2}
              dy="0.35em"
              textAnchor={node.x0 < width / 2 ? 'start' : 'end'}
              style={{ fontSize: 10, fill: 'var(--tx1)', fontWeight: 700 }}
            >
              {node.name}
            </text>
          </g>
        ))}
      </g>
    </svg>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add packages/web/src/finance/SankeyChart.jsx
git commit -m "feat: implement SankeyChart component"
```

---

### Task 4: Integrate into Dashboard

**Files:**
- Modify: `packages/web/src/pages/dashboard.jsx`

- [ ] **Step 1: Import and add SankeyChart to Dashboard**

- [ ] **Step 2: Commit**

```bash
git add packages/web/src/pages/dashboard.jsx
git commit -m "feat: integrate SankeyChart into dashboard"
```
