'use client';

import { useEffect, useState } from 'react';

import { clientProxyUrl } from '@/lib/api';

type Status = 'loading' | 'empty' | 'error' | 'ready';

function Shell({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div
      role="status"
      aria-label={label}
      className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-muted/30 p-12 text-center"
    >
      <div className="text-4xl mb-4" aria-hidden="true">
        🏆
      </div>
      {children}
    </div>
  );
}

export default function RewardsPanel() {
  const [status, setStatus] = useState<Status>('loading');
  const [count, setCount] = useState(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(clientProxyUrl('api/rewards'), { cache: 'no-store' });
        if (!res.ok) {
          if (!cancelled) setStatus('error');
          return;
        }
        const data: unknown = await res.json();
        const items = Array.isArray(data) ? data : (data as { items?: unknown[] }).items;
        if (!cancelled) {
          if (Array.isArray(items) && items.length > 0) {
            setCount(items.length);
            setStatus('ready');
          } else {
            setStatus('empty');
          }
        }
      } catch {
        if (!cancelled) setStatus('error');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (status === 'loading') {
    return (
      <Shell label="Loading rewards from engagement API">
        <h2 className="text-lg font-semibold mb-2">Loading rewards…</h2>
        <p className="text-sm text-muted-foreground max-w-sm">Contacting the engagement service.</p>
      </Shell>
    );
  }

  if (status === 'error') {
    return (
      <Shell label="Rewards API unreachable">
        <h2 className="text-lg font-semibold mb-2">Rewards API unreachable</h2>
        <p className="text-sm text-muted-foreground max-w-sm">
          The engagement service did not respond. Check that the gateway is up, then see the aggregated route
          table at <code className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded">/openapi.json</code>.
        </p>
      </Shell>
    );
  }

  if (status === 'empty') {
    return (
      <Shell label="No rewards yet">
        <h2 className="text-lg font-semibold mb-2">No rewards yet</h2>
        <p className="text-sm text-muted-foreground max-w-sm">
          The engagement API is reachable but returned no rewards. Endpoint:{' '}
          <code className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded">/api/rewards</code> — contract
          documented in the gateway route table{' '}
          <code className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded">/openapi.json</code>.
        </p>
      </Shell>
    );
  }

  return (
    <div
      role="status"
      aria-label={`${count} rewards available`}
      className="flex flex-col items-center justify-center rounded-xl border border-border bg-card p-12 text-center"
    >
      <div className="text-4xl mb-4" aria-hidden="true">
        🏆
      </div>
      <h2 className="text-lg font-semibold mb-2">{count} rewards available</h2>
      <p className="text-sm text-muted-foreground max-w-sm">
        Served live by the engagement service (
        <code className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded">/api/rewards</code>).
      </p>
    </div>
  );
}
