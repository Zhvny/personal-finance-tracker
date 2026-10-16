"use client";

import { useState } from "react";
import { CalendarDays, Filter } from "lucide-react";

interface FilterState {
  year: number;
  month: number | null;
  period: string;
}

interface PeriodFilterProps {
  onFilterChange: (filter: FilterState) => void;
  defaultYear?: number;
}

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
  "Jul", "Agu", "Sep", "Okt", "Nov", "Des"
];

const PRESETS = [
  { label: "Semua",      value: "all" },
  { label: "Bulan Ini",  value: "this_month" },
  { label: "Bln Lalu",  value: "last_month" },
  { label: "Q1",         value: "q1" },
  { label: "Q2",         value: "q2" },
  { label: "Q3",         value: "q3" },
  { label: "Q4",         value: "q4" },
  { label: "YTD",        value: "ytd" },
];

export function PeriodFilter({ onFilterChange, defaultYear = new Date().getFullYear() }: PeriodFilterProps) {
  const [selectedYear, setSelectedYear]   = useState<number>(defaultYear);
  const [selectedMonth, setSelectedMonth] = useState<number | null>(null);
  const [selectedPreset, setSelectedPreset] = useState<string>("this_month");

  const currentYear = new Date().getFullYear();
  const yearOptions = [currentYear - 2, currentYear - 1, currentYear];

  const emitChange = (year: number, month: number | null, period: string) => {
    onFilterChange({ year, month, period });
  };

  const handleYear = (y: number) => {
    setSelectedYear(y);
    setSelectedPreset("custom");
    emitChange(y, selectedMonth, "custom");
  };

  const handleMonth = (idx: number | null) => {
    setSelectedMonth(idx);
    setSelectedPreset("custom");
    emitChange(selectedYear, idx !== null ? idx + 1 : null, "custom");
  };

  const handlePreset = (preset: string) => {
    setSelectedPreset(preset);
    setSelectedMonth(null);
    emitChange(selectedYear, null, preset);
  };

  return (
    <div className="glass-panel p-4 rounded-2xl space-y-3">
      {/* Header row */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <Filter size={15} className="text-primary" />
          <span>Filter Periode</span>
        </div>

        {/* Year selector */}
        <div className="flex items-center gap-2">
          <CalendarDays size={14} className="text-muted-foreground" />
          <select
            value={selectedYear}
            onChange={(e) => handleYear(Number(e.target.value))}
            className="bg-background border border-border rounded-lg px-3 py-1.5 text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-primary cursor-pointer"
          >
            {yearOptions.map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Preset pills */}
      <div className="flex flex-wrap gap-1.5">
        {PRESETS.map((p) => (
          <button
            key={p.value}
            onClick={() => handlePreset(p.value)}
            className={`px-3 py-1 text-xs rounded-lg font-medium transition-all duration-200 ${
              selectedPreset === p.value
                ? "bg-primary text-primary-foreground shadow-sm"
                : "bg-muted/60 text-muted-foreground hover:bg-muted hover:text-foreground"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Month pills */}
      <div className="border-t border-border/50 pt-2">
        <div className="grid grid-cols-7 sm:grid-cols-13 gap-1">
          <button
            onClick={() => handleMonth(null)}
            className={`col-span-1 py-1 px-1 text-xs rounded font-medium transition-colors ${
              selectedMonth === null && selectedPreset === "custom"
                ? "bg-foreground text-background"
                : "text-muted-foreground hover:bg-muted"
            }`}
          >
            All
          </button>
          {MONTHS.map((mo, idx) => (
            <button
              key={mo}
              onClick={() => handleMonth(idx)}
              className={`py-1 text-xs rounded font-medium transition-colors ${
                selectedMonth === idx
                  ? "bg-primary text-primary-foreground font-bold"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              }`}
            >
              {mo}
            </button>
          ))}
        </div>
      </div>

      {/* Active filter summary */}
      {selectedPreset !== "all" && (
        <p className="text-xs text-muted-foreground">
          Menampilkan data:
          <span className="font-semibold text-foreground ml-1">
            {selectedPreset === "custom"
              ? `${selectedYear}${selectedMonth !== null ? ` / ${MONTHS[selectedMonth]}` : ""}`
              : `${PRESETS.find(p => p.value === selectedPreset)?.label} ${selectedYear}`
            }
          </span>
        </p>
      )}
    </div>
  );
}
