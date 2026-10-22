"use client";

import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useI18n } from "@/i18n/context";

interface Tab {
  label: string;
  value: string;
  icon?: React.ReactNode;
}

interface LiquidNavProps {
  tabs: Tab[];
  value: string;
  onChange: (value: string) => void;
  className?: string;
}

export function LiquidNav({ tabs, value, onChange, className = "" }: LiquidNavProps) {
  const { t } = useI18n();
  const [indicatorStyle, setIndicatorStyle] = useState({ left: 0, width: 0 });
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  useEffect(() => {
    const activeIdx = tabs.findIndex((tab) => tab.value === value);
    const el = tabRefs.current[activeIdx];
    if (el) {
      setIndicatorStyle({ left: el.offsetLeft, width: el.offsetWidth });
    }
  }, [value, tabs]);

  return (
    <div
      className={`relative flex items-center gap-0.5 p-1 rounded-2xl glass-panel ${className}`}
      role="tablist"
      aria-label={t("ui.nav_tabs_label")}
    >
      {/* Liquid morphing pill indicator */}
      <motion.div
        className="absolute top-1 bottom-1 rounded-xl bg-foreground/90 shadow-sm"
        animate={{ left: indicatorStyle.left, width: indicatorStyle.width }}
        transition={{ type: "spring", stiffness: 500, damping: 38, mass: 0.6 }}
        aria-hidden="true"
      />

      {tabs.map((tab, idx) => {
        const isActive = tab.value === value;
        return (
          <button
            key={tab.value}
            ref={(el) => { tabRefs.current[idx] = el; }}
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(tab.value)}
            className={`relative z-10 flex items-center gap-1.5 px-4 py-2 text-sm font-medium
              rounded-xl transition-colors duration-200 select-none whitespace-nowrap
              focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring
              ${isActive ? "text-background" : "text-muted-foreground hover:text-foreground"}`}
          >
            {tab.icon && (
              <span className={`transition-transform duration-200 ${isActive ? "scale-110" : ""}`}>
                {tab.icon}
              </span>
            )}
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
