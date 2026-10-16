"use client";

import { useRef, useEffect, useState, ReactNode } from "react";

interface FocusScrollProps {
  children: ReactNode;
  className?: string;
  focusClassName?: string;
  dimClassName?: string;
}

export function FocusScrollSection({ children, className = "", focusClassName = "", dimClassName = "" }: FocusScrollProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [isFocused, setIsFocused] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => setIsFocused(entry.intersectionRatio >= 0.5),
      { threshold: [0, 0.5, 1.0] }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      className={`transition-all duration-500 ${
        isFocused
          ? `scale-[1.01] opacity-100 ${focusClassName}`
          : `opacity-70 scale-[0.99] ${dimClassName}`
      } ${className}`}
    >
      {children}
    </div>
  );
}
