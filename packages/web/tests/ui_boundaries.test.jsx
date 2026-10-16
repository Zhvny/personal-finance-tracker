import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import * as matchers from '@testing-library/jest-dom/matchers';
import ButterflyMap from '../src/components/ButterflyMap.jsx';
import ButterflyErrorBoundary from '../src/components/ButterflyErrorBoundary.jsx';
import AppErrorBoundary from '../src/components/common/ErrorBoundary.jsx';

expect.extend(matchers);

// Set up mutable mock data
let mockCacheFetch = { data: null, loading: false, error: null };

vi.mock("../src/finance/useApi.js", () => ({
  useCacheFetch: () => mockCacheFetch,
  useDebounce: (val) => val,
  useWebSocket: () => ({ lastMessage: null }),
}));

const CrashingComponent = () => {
  throw new Error('Simulation of component crash');
};

describe('AppErrorBoundary', () => {
  it('renders application fallback UI when children crash', () => {
    // Suppress console.error for expected boundary catch
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <AppErrorBoundary>
        <CrashingComponent />
      </AppErrorBoundary>
    );

    expect(screen.getByText(/Something went wrong/i)).toBeInTheDocument();
    expect(screen.getByText(/Reload Application/i)).toBeInTheDocument();
    spy.mockRestore();
  });
});

describe('ButterflyErrorBoundary', () => {
  it('renders error message when children crash', () => {
    // Suppress console.error for expected boundary catch
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <ButterflyErrorBoundary>
        <CrashingComponent />
      </ButterflyErrorBoundary>
    );

    expect(screen.getByText(/Graphics Engine Stalled/i)).toBeInTheDocument();
    spy.mockRestore();
  });
});

describe('ButterflyMap Boundary Behavior', () => {
  beforeEach(() => {
    mockCacheFetch = { data: null, loading: false, error: null };
  });

  it('displays empty state when no nodes are found', () => {
    mockCacheFetch = { data: { nodes: [], edges: [] }, loading: false, error: null };

    render(<ButterflyMap ticker="AAPL" />);
    
    expect(screen.getByText(/No significant relationships detected/i)).toBeInTheDocument();
  });

  it('displays error state when API fails', () => {
    mockCacheFetch = { data: null, loading: false, error: new Error('API Timeout') };

    render(<ButterflyMap ticker="AAPL" />);
    
    expect(screen.getByText(/Graph unavailable/i)).toBeInTheDocument();
  });

  it('triggers error boundary when crash prop is set', () => {
    // Suppress console.error for expected boundary catch
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});

    render(<ButterflyMap ticker="AAPL" crash={true} />);
    
    expect(screen.getByText(/Graphics Engine Stalled/i)).toBeInTheDocument();
    spy.mockRestore();
  });
});
