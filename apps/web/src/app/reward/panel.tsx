'use client';

import { useEffect, useState } from 'react';

import { clientProxyUrl } from '@/lib/api';
import { useI18n } from '@/i18n/context';

type Status = 'loading' | 'empty' | 'error' | 'ready';

interface RewardItem {
  id: number;
  name_en: string;
  name_id: string;
  desc_en: string;
  desc_id: string;
  kategori: string;
  tier: string;
  cost: number;
  halal?: boolean;
}

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
  const { locale, t } = useI18n();
  const [status, setStatus] = useState<Status>('loading');
  const [items, setItems] = useState<RewardItem[]>([]);
  const [halalOnly, setHalalOnly] = useState<boolean>(true);
  const [hintNextRotation, setHintNextRotation] = useState<boolean>(false);
  const [updatingPref, setUpdatingPref] = useState<boolean>(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(clientProxyUrl('api/rewards/catalogue'), { cache: 'no-store' });
        if (!res.ok) {
          if (!cancelled) setStatus('error');
          return;
        }
        const data: unknown = await res.json();
        const rawItems = Array.isArray(data) ? data : (data as { items?: RewardItem[] }).items;
        const pref = (data as { halal_only?: boolean })?.halal_only ?? true;
        if (!cancelled) {
          setHalalOnly(pref);
          if (Array.isArray(rawItems) && rawItems.length > 0) {
            setItems(rawItems as RewardItem[]);
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

  const handleToggleHalal = async (val: boolean) => {
    if (val === halalOnly || updatingPref) return;
    setUpdatingPref(true);
    try {
      await fetch(clientProxyUrl('api/rewards/preferences'), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ halal_only: val, profile_id: 'default' }),
      });
      setHalalOnly(val);
      setHintNextRotation(true);
    } catch {
      // silently keep current on error
    } finally {
      setUpdatingPref(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Halal Toggle */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-xl border border-border bg-card">
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-muted-foreground">{t('reward.halal_filter_label', 'Filter:')}</span>
          <div className="inline-flex rounded-lg border border-border bg-muted/40 p-1">
            <button
              type="button"
              onClick={() => void handleToggleHalal(true)}
              disabled={updatingPref}
              className={`rounded-md px-3 py-1 text-xs font-semibold transition-colors ${
                halalOnly
                  ? 'bg-primary text-primary-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              {t('reward.halal_only', 'Halal Only')}
            </button>
            <button
              type="button"
              onClick={() => void handleToggleHalal(false)}
              disabled={updatingPref}
              className={`rounded-md px-3 py-1 text-xs font-semibold transition-colors ${
                !halalOnly
                  ? 'bg-primary text-primary-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              {t('reward.all_items', 'Semua')}
            </button>
          </div>
        </div>
        {hintNextRotation && (
          <p className="text-xs text-muted-foreground italic">
            * {t('reward.halal_rotation_hint', 'Berlaku mulai rotasi Senin berikutnya.')}
          </p>
        )}
      </div>

      {status === 'loading' && (
        <Shell label={t('reward.loading_title', 'Loading rewards…')}>
          <h2 className="text-lg font-semibold mb-2">{t('reward.loading_title', 'Loading rewards…')}</h2>
          <p className="text-sm text-muted-foreground max-w-sm">{t('reward.loading_desc', 'Contacting the engagement service.')}</p>
        </Shell>
      )}

      {status === 'error' && (
        <Shell label={t('reward.error_title', 'Rewards API unreachable')}>
          <h2 className="text-lg font-semibold mb-2">{t('reward.error_title', 'Rewards API unreachable')}</h2>
          <p className="text-sm text-muted-foreground max-w-sm">
            {t('reward.error_desc', 'The engagement service did not respond. Check that the gateway is up.')}
          </p>
        </Shell>
      )}

      {status === 'empty' && (
        <Shell label={t('reward.empty_title', 'No rewards in rotation yet')}>
          <h2 className="text-lg font-semibold mb-2">{t('reward.empty_title', 'No rewards in rotation yet')}</h2>
          <p className="text-sm text-muted-foreground max-w-sm">
            {t('reward.empty_desc', 'The engagement service returned 0 items. Weekly rotation seeds every Monday at 00:00 WIB.')}
          </p>
        </Shell>
      )}

      {status === 'ready' && (
        <div
          role="status"
          aria-label={`${items.length} rewards available`}
          className="rounded-xl border border-border bg-card p-6"
        >
          <div className="text-center mb-6">
            <div className="text-4xl mb-2" aria-hidden="true">
              🏆
            </div>
            <h2 className="text-lg font-semibold mb-1">
              {t('reward.ready_title', '{count} rewards in active rotation').replace('{count}', String(items.length))}
            </h2>
            <p className="text-sm text-muted-foreground max-w-sm mx-auto">
              {t('reward.ready_desc', 'Weekly pool synchronized with the engagement service.')}
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {items.map((item) => {
              const name = locale === 'id' ? (item.name_id || item.name_en) : (item.name_en || item.name_id);
              const desc = locale === 'id' ? (item.desc_id || item.desc_en) : (item.desc_en || item.desc_id);
              return (
                <div key={item.id} className="flex flex-col justify-between rounded-lg border border-border/60 bg-muted/20 p-4">
                  <div>
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-primary/10 text-primary">
                        {item.tier}
                      </span>
                      <div className="flex items-center gap-2">
                        <span className="text-[11px] text-muted-foreground capitalize">
                          {item.kategori}
                        </span>
                        {item.halal === false && (
                          <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-red-500/15 text-red-400 border border-red-500/30">
                            {t('reward.non_halal_badge', 'Non-Halal')}
                          </span>
                        )}
                      </div>
                    </div>
                    <h3 className="text-sm font-semibold text-foreground mb-1">{name}</h3>
                    <p className="text-xs text-muted-foreground line-clamp-2">{desc}</p>
                  </div>
                  <div className="mt-3 pt-2 border-t border-border/40 flex items-center justify-between">
                    <span className="text-xs font-bold text-amber-400">
                      {item.cost?.toLocaleString()} pts
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
