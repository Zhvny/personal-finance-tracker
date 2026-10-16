"use client";

import { useRef, useEffect, useState, ReactNode } from "react";

interface StackingCardsProps {
  children: ReactNode[];
  className?: string;
}

export function StackingCards({ children, className = "" }: StackingCardsProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [scrollPct, setScrollPct] = useState(0);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const onScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container;
      setScrollPct(scrollTop / Math.max(scrollHeight - clientHeight, 1));
    };
    container.addEventListener("scroll", onScroll, { passive: true });
    return () => container.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div
      ref={containerRef}
      className={`stacking-container relative overflow-y-auto ${className}`}
    >
      <div className="space-y-4">
        {children.map((child, i) => {
          const totalCards = children.length;
          const cardScrollStart = i / totalCards;
          const localProgress = Math.max(0, Math.min(1, (scrollPct - cardScrollStart) * totalCards));
          const scale     = 1 - localProgress * 0.04 * Math.min(i, 3);
          const blurVal   = localProgress * 2 * Math.min(i, 2);
          const opacity   = 1 - localProgress * 0.2 * Math.min(i, 2);

          return (
            <div
              key={i}
              className="stacking-card rounded-2xl overflow-hidden"
              style={{
                transform: `scale(${scale}) translateY(-${localProgress * i * 6}px)`,
                filter:    `blur(${blurVal}px)`,
                opacity,
                zIndex:    totalCards - i,
              }}
            >
              {child}
            </div>
          );
        })}
      </div>
    </div>
  );
}
