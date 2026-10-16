// ─── SankeyChart.jsx ──────────────────────────────────────────────────────────
// Cashflow Sankey diagram using d3-sankey for layout and React SVG for rendering.
// Visualizes the flow of income sources into a central pivot, then into expenses and savings.

import React, { useMemo, useState } from 'react';
import { sankey, sankeyLinkHorizontal } from 'd3-sankey';
import { CAT_COLOR, fmt } from '../constants.js';
import { createPortal } from 'react-dom';

export default function SankeyChart({ data, width = 600, height = 400 }) {
  const [hoveredLink, setHoveredLink] = useState(null);
  const [tipPos, setTipPos] = useState(null);

  const { nodes, links } = useMemo(() => {
    if (!data || !data.nodes.length) return { nodes: [], links: [] };

    const sankeyInstance = sankey()
      .nodeWidth(12)
      .nodePadding(12)
      .extent([[1, 1], [width - 1, height - 10]]);

    // d3-sankey expects numeric indices for source/target in links
    const graph = {
      nodes: data.nodes.map(d => ({ ...d })),
      links: data.links.map(d => ({
        source: data.nodes.findIndex(n => n.name === d.source),
        target: data.nodes.findIndex(n => n.name === d.target),
        value: d.value
      }))
    };

    try {
        return sankeyInstance(graph);
    } catch (e) {
        console.error("Sankey layout error:", e);
        return { nodes: [], links: [] };
    }
  }, [data, width, height]);

  if (!nodes.length) return null;

  return (
    <div className="sankey-wrap" style={{ position: 'relative', padding: '10px 0' }}>
      <svg width={width} height={height} style={{ overflow: 'visible', display: 'block', margin: '0 auto' }}>
        {/* Links */}
        <g>
          {links.map((link, i) => {
            const isHovered = hoveredLink === i;
            const targetName = link.target.name;
            const strokeColor = link.source.type === 'income' ? 'var(--gr)' : 
                                link.target.type === 'expense' ? (CAT_COLOR[targetName] || 'var(--rd)') : 
                                link.target.name === 'Savings' ? 'var(--gr)' : 'var(--tx3)';

            return (
              <path
                key={i}
                d={sankeyLinkHorizontal()(link)}
                fill="none"
                stroke={strokeColor}
                strokeOpacity={isHovered ? 0.6 : 0.25}
                strokeWidth={Math.max(1, link.width)}
                onMouseEnter={(e) => {
                  setHoveredLink(i);
                  setTipPos({ x: e.clientX + 12, y: e.clientY - 40 });
                }}
                onMouseMove={(e) => {
                  setTipPos({ x: e.clientX + 12, y: e.clientY - 40 });
                }}
                onMouseLeave={() => {
                  setHoveredLink(null);
                  setTipPos(null);
                }}
                style={{ transition: 'stroke-opacity 0.2s', cursor: 'pointer' }}
              />
            );
          })}
        </g>

        {/* Nodes */}
        <g>
          {nodes.map((node, i) => {
            const isLeft = node.x0 < width / 2;
            const color = node.type === 'income' || node.name === 'Savings' ? 'var(--gr)' : 
                          node.type === 'expense' ? (CAT_COLOR[node.name] || 'var(--rd)') : 
                          node.type === 'pivot' ? 'var(--cy)' : 'var(--tx3)';

            return (
              <g key={i} transform={`translate(${node.x0},${node.y0})`}>
                <rect
                  height={Math.max(2, node.y1 - node.y0)}
                  width={node.x1 - node.x0}
                  fill={color}
                  rx={2}
                  style={{ fillOpacity: 0.9 }}
                />
                <text
                  x={isLeft ? -8 : (node.x1 - node.x0) + 8}
                  y={(node.y1 - node.y0) / 2}
                  dy="0.35em"
                  textAnchor={isLeft ? 'end' : 'start'}
                  style={{ 
                    fontSize: 10, 
                    fill: 'var(--tx1)', 
                    fontWeight: 700,
                    pointerEvents: 'none',
                    textShadow: '0 1px 2px var(--bg1)'
                  }}
                >
                  {node.name}
                </text>
                <text
                   x={isLeft ? -8 : (node.x1 - node.x0) + 8}
                   y={(node.y1 - node.y0) / 2 + 12}
                   textAnchor={isLeft ? 'end' : 'start'}
                   style={{ fontSize: 9, fill: 'var(--tx3)', pointerEvents: 'none' }}
                >
                  {fmt(node.value)}
                </text>
              </g>
            );
          })}
        </g>
      </svg>

      {/* Tooltip */}
      {hoveredLink !== null && tipPos && createPortal(
        <div style={{
          position: 'fixed',
          top: tipPos.y,
          left: tipPos.x,
          zIndex: 10000,
          background: 'var(--bg2)',
          border: '1px solid var(--bdr2)',
          borderRadius: 8,
          padding: '8px 12px',
          boxShadow: '0 4px 20px rgba(0,0,0,0.4)',
          pointerEvents: 'none',
          fontSize: 11,
          fontFamily: 'var(--mono)'
        }}>
          <div style={{ color: 'var(--tx3)', marginBottom: 4 }}>
            {links[hoveredLink].source.name} → {links[hoveredLink].target.name}
          </div>
          <div style={{ fontSize: 13, fontWeight: 900, color: 'var(--tx1)' }}>
            {fmt(links[hoveredLink].value)}
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
