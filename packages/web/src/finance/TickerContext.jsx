import React, { createContext, useContext, useState, useCallback, useRef } from 'react';
import { apiFetch } from './useApi.js';

const TickerContext = createContext();

export const TickerProvider = ({ children }) => {
  const [selectedTicker, setSelectedTicker] = useState("");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const abortControllerRef = useRef(null);

  const analyze = useCallback(async (ticker) => {
    const symbol = ticker.trim().toUpperCase();
    if (!symbol) return;

    // Cancel previous request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    setSelectedTicker(symbol);
    setLoading(true);
    setError(null);

    try {
      const res = await apiFetch(`/stocks/analyze/${symbol}`, {
        signal: abortControllerRef.current.signal
      });
      
      if (res && !res.__aborted) {
        setData(res);
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        console.error("Analysis failed:", err);
        setError(`Analysis failed for ${symbol}. The ticker might be invalid or market data provider is currently unavailable.`);
        setData(null);
      }
    } finally {
      if (!abortControllerRef.current?.signal.aborted) {
        setLoading(false);
      }
    }
  }, []);

  const value = {
    selectedTicker,
    data,
    loading,
    error,
    analyze,
    clearError: () => setError(null)
  };

  return (
    <TickerContext.Provider value={value}>
      {children}
    </TickerContext.Provider>
  );
};

export const useTicker = () => {
  const context = useContext(TickerContext);
  if (!context) {
    throw new Error('useTicker must be used within a TickerProvider');
  }
  return context;
};
