// ─── animations.js ────────────────────────────────────────────────────────────
// Central animation abstraction — Single Source of Truth for all motion in app.
//
// Clean Architecture: all animation config defined here; components stay dumb.
// DRY              : easing/duration constants declared once, reused everywhere.
// Abstraction      : consumers call sidebarStyle(), pageStyle — never write
//                    transition/animation strings inline.
// YAGNI            : only animations actually used in the app are defined.
// ─────────────────────────────────────────────────────────────────────────────

// ── Easing curves (matches Material Design motion spec) ───────────────────────
export const EASE = {
  standard:    "cubic-bezier(.4,0,.2,1)",   // enter + exit (balanced)
  decelerate:  "cubic-bezier(0,0,.2,1)",    // enter screen (fast → slow)
  accelerate:  "cubic-bezier(.4,0,1,1)",    // exit screen  (slow → fast)
  spring:      "cubic-bezier(.34,1.56,.64,1)", // slight overshoot for playful feel
};

// ── Duration tokens (ms) ─────────────────────────────────────────────────────
export const DUR = {
  fast:    150,   // micro-interactions (hover, badge)
  normal:  220,   // sidebar, tooltip
  slow:    380,   // page transitions, large panels
};

// ── Sidebar animation ─────────────────────────────────────────────────────────
// Returns an inline style object for the sidebar <aside> element.
// Hidden ↔ visible transition: width + opacity collapse simultaneously.
export function sidebarStyle(hidden) {
  // On mobile (≤768px), sidebar positioning is handled entirely by CSS classes.
  // Returning an empty object avoids inline styles that would override media queries.
  if (typeof window !== "undefined" && window.innerWidth <= 768) return {};
  return {
    width:          hidden ? 0        : 252,
    minWidth:       hidden ? 0        : 252,
    opacity:        hidden ? 0        : 1,
    overflow:       hidden ? "hidden" : undefined,
    pointerEvents:  hidden ? "none"   : undefined,
    padding:        hidden ? 0        : undefined,
    border:         hidden ? "none"   : undefined,
    transition: [
      `width ${DUR.normal}ms ${EASE.standard}`,
      `min-width ${DUR.normal}ms ${EASE.standard}`,
      `opacity ${DUR.fast}ms ${EASE.standard}`,
      `padding ${DUR.normal}ms ${EASE.standard}`,
    ].join(", "),
  };
}

// ── Page transition animation ─────────────────────────────────────────────────
// Returns an inline style for the page content wrapper.
// Uses CSS animation name defined in PAGE_KEYFRAMES below.
export const pageStyle = {
  animation: `page-in ${DUR.slow}ms ${EASE.decelerate} both`,
};

// ── Page-in keyframe CSS string ───────────────────────────────────────────────
// Inject once via <style> tag in the layout wrapper (App.jsx).
export const PAGE_KEYFRAMES = `
@keyframes page-in {
  from { opacity: 0; transform: translateY(10px); }
  to   { opacity: 1; transform: translateY(0);    }
}
`;

// ── PageWrapper component helper ──────────────────────────────────────────────
// Convenience — wraps any page with the fade+drift animation.
// Re-mounts (and re-animates) when pageKey changes.
// NOTE: @keyframes page-in is defined in dark-style.css — no <style> injection needed.
export function PageWrapper({ pageKey, children }) {
  return (
    <div key={pageKey} style={pageStyle}>
      {children}
    </div>
  );
}
