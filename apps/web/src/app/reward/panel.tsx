'use client';

import { useEffect, useState } from 'react';

import { clientProxyUrl } from '@/lib/api';
import { useI18n } from '@/i18n/context';

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
  const { t } = useI18n();
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
      <Shell label={t('reward.loading_title', 'Loading rewards…')}>
        <h2 className="text-lg font-semibold mb-2">{t('reward.loading_title', 'Loading rewards…')}</h2>
        <p className="text-sm text-muted-foreground max-w-sm">{t('reward.loading_desc', 'Contacting the engagement service.')}</p>
      </Shell>
    );
  }

  if (status === 'error') {
    return (
      <Shell label={t('reward.error_title', 'Rewards API unreachable')}>
        <h2 className="text-lg font-semibold mb-2">{t('reward.error_title', 'Rewards API unreachable')}</h2>
        <p className="text-sm text-muted-foreground max-w-sm">
          {t('reward.error_desc', 'The engagement service did not respond. Check that the gateway is up.')}
        </p>
      </Shell>
    );
  }

  if (status === 'empty') {
    return (
      <Shell label={t('reward.empty_title', 'No rewards in rotation yet')}>
        <h2 className="text-lg font-semibold mb-2">{t('reward.empty_title', 'No rewards in rotation yet')}</h2>
        <p className="text-sm text-muted-foreground max-w-sm">
          {t('reward.empty_desc', 'Weekly rotation seeds every Monday at 00:00 WIB.')}
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
      <h2 className="text-lg font-semibold mb-2">
        {t('reward.ready_title', '{count} rewards in active rotation').replace('{count}', String(count))}
      </h2>
      <p className="text-sm text-muted-foreground max-w-sm">
        {t('reward.ready_desc', 'Weekly pool synchronized with the engagement service.')}
      </p>
    </div>
  );
}
