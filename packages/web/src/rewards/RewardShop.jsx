// ─── RewardShop.jsx ─────────────────────────────────────────────────────────────
// Weekly Rotating Reward Shop + 5 UI States + Finance System Design
// ─────────────────────────────────────────────────────────────────────────────

import { useState, useEffect, useCallback, useMemo } from "react";
import {
  loadCatalogue,
  claimWeeklyReward,
  redeemWeeklyReward,
  TIER_META,
  CATEGORY_META,
} from "./rewardCatalogue.js";
import {
  IconCoin, IconAward, IconStar, IconTrophy, IconSparkles, IconImage,
  IconVideo, IconUnlock, IconClose, IconWarning, IconCheck, IconSeason,
  IconStore, IconGift, IconCalStat, IconRefresh, IconTarget,
} from "../icons.jsx";

// ── Countdown Hook ────────────────────────────────────────────────────────────
function useCountdown(expiresAt) {
  const [timeLeft, setTimeLeft] = useState("");
  const [isExpired, setIsExpired] = useState(false);

  useEffect(() => {
    if (!expiresAt) {
      setTimeLeft("");
      setIsExpired(false);
      return;
    }

    const calculate = () => {
      const diff = new Date(expiresAt).getTime() - Date.now();
      if (diff <= 0) {
        setTimeLeft("Expired / Kedaluwarsa");
        setIsExpired(true);
        return;
      }
      setIsExpired(false);
      const days = Math.floor(diff / (1000 * 60 * 60 * 24));
      const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
      const mins = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
      setTimeLeft(`${days}h ${hours}j ${mins}m`);
    };

    calculate();
    const timer = setInterval(calculate, 30000);
    return () => clearInterval(timer);
  }, [expiresAt]);

  return { timeLeft, isExpired };
}

// ── State: Loading Skeleton ───────────────────────────────────────────────────
function ShopSkeleton() {
  return (
    <div className="gp-shop-grid">
      {[1, 2, 3, 4, 5, 6].map(i => (
        <div key={i} className="gp-card skeleton-card" style={{ height: 260 }}>
          <div style={{ height: 110, background: "var(--bg3)", borderRadius: "8px 8px 0 0" }} />
          <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ width: "40%", height: 14, background: "var(--bg3)", borderRadius: 4 }} />
            <div style={{ width: "80%", height: 18, background: "var(--bg3)", borderRadius: 4 }} />
            <div style={{ width: "100%", height: 12, background: "var(--bg3)", borderRadius: 4 }} />
            <div style={{ width: "50%", height: 24, marginTop: 8, background: "var(--bg3)", borderRadius: 4 }} />
          </div>
        </div>
      ))}
    </div>
  );
}

// ── State: Error ──────────────────────────────────────────────────────────────
function ShopError({ error, onRetry }) {
  return (
    <div className="gp-empty error-state" style={{ padding: "48px 20px", textAlign: "center" }}>
      <IconWarning size={36} color="var(--rd, #e8714d)" />
      <div style={{ fontSize: 16, fontWeight: 700, marginTop: 12, color: "var(--tx)" }}>
        Gagal Memuat Katalog Reward
      </div>
      <div style={{ fontSize: 13, color: "var(--tx2)", marginTop: 4, maxWidth: 400, margin: "6px auto 16px" }}>
        {error || "Terjadi kesalahan saat mengambil katalog mingguan."}
      </div>
      <button className="gp-filter-btn active" onClick={onRetry} style={{ margin: "0 auto", display: "inline-flex", alignItems: "center", gap: 6 }}>
        <IconRefresh size={14} /> Coba Lagi
      </button>
    </div>
  );
}

// ── State: Empty ──────────────────────────────────────────────────────────────
function ShopEmpty({ onRefresh }) {
  return (
    <div className="gp-empty" style={{ padding: "48px 20px", textAlign: "center" }}>
      <IconStore size={40} color="var(--tx3)" />
      <div style={{ fontSize: 16, fontWeight: 700, marginTop: 12, color: "var(--tx)" }}>
        Belum Ada Reward Minggu Ini
      </div>
      <div style={{ fontSize: 13, color: "var(--tx2)", marginTop: 4, marginBottom: 16 }}>
        Reward dirotasi setiap Senin pukul 00:00 WIB.
      </div>
      <button className="gp-filter-btn" onClick={onRefresh}>
        <IconRefresh size={14} /> Segarkan
      </button>
    </div>
  );
}

// ── Weekly Reward Card ─────────────────────────────────────────────────────────
function WeeklyRewardCard({
  item,
  userReward,
  onClaim,
  onRedeem,
  submitting,
}) {
  const tier = TIER_META[item.tier] || TIER_META.basic;
  const category = CATEGORY_META[item.kategori]?.label || item.kategori;
  const canAfford = userReward >= item.cost;
  const { timeLeft, isExpired } = useCountdown(item.expires_at);

  let statusClass = "unclaimed";
  if (item.redeemed) statusClass = "redeemed";
  else if (item.claimed) statusClass = isExpired ? "expired" : "claimed";

  return (
    <div className={`gp-card weekly-card ${statusClass} tier-${item.tier}`} style={{ borderColor: `rgba(255,255,255,0.08)` }}>
      <div className="gp-card-body" style={{ display: "flex", flexDirection: "column", height: "100%", padding: 18 }}>
        
        {/* Top Badges */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
          <span
            className="gp-tier-pill"
            style={{
              fontSize: 11,
              fontWeight: 700,
              padding: "2px 8px",
              borderRadius: 6,
              background: `rgba(${tier.color === '#fcd535' ? '252,213,53' : '56,189,248'}, 0.12)`,
              color: tier.color,
              border: `1px solid ${tier.color}40`,
              textTransform: "uppercase",
              letterSpacing: "0.5px",
            }}
          >
            {tier.label}
          </span>
          <span style={{ fontSize: 11, color: "var(--tx3)", background: "var(--bg3)", padding: "2px 8px", borderRadius: 4 }}>
            {category}
          </span>
        </div>

        {/* Title & Description */}
        <div style={{ fontSize: 15, fontWeight: 700, color: "var(--tx)", lineHeight: 1.3, marginBottom: 6 }}>
          {item.name_id || item.name_en}
        </div>
        {item.name_en && item.name_en !== item.name_id && (
          <div style={{ fontSize: 11, color: "var(--tx3)", marginBottom: 8, fontStyle: "italic" }}>
            {item.name_en}
          </div>
        )}
        <div style={{ fontSize: 12, color: "var(--tx2)", lineHeight: 1.5, flex: 1, marginBottom: 14 }}>
          {item.desc_id || item.desc_en}
        </div>

        {/* Status Indicators */}
        {item.claimed && !item.redeemed && !isExpired && (
          <div style={{ fontSize: 11, color: "var(--cy)", background: "rgba(55,138,221,0.12)", padding: "4px 8px", borderRadius: 6, marginBottom: 10, display: "flex", alignItems: "center", gap: 6 }}>
            <IconClock size={12} />
            <span>Klaim aktif · Kedaluwarsa dlm {timeLeft}</span>
          </div>
        )}

        {isExpired && !item.redeemed && (
          <div style={{ fontSize: 11, color: "var(--rd)", background: "rgba(232,113,77,0.12)", padding: "4px 8px", borderRadius: 6, marginBottom: 10, display: "flex", alignItems: "center", gap: 6 }}>
            <IconWarning size={12} />
            <span>Kedaluwarsa (14 hari terlampaui)</span>
          </div>
        )}

        {/* Footer / Action */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingTop: 10, borderTop: "1px solid rgba(255,255,255,0.06)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 5, color: "var(--ind, #fcd535)", fontWeight: 700, fontSize: 14 }}>
            <IconCoin size={14} />
            <span>{item.cost?.toLocaleString("id-ID")}</span>
            <span style={{ fontSize: 10, color: "var(--tx3)", fontWeight: 400 }}>poin</span>
          </div>

          {item.redeemed ? (
            <span style={{ display: "inline-flex", alignItems: "center", gap: 4, color: "var(--gr, #7aba2a)", fontSize: 12, fontWeight: 700 }}>
              <IconCheck size={14} /> Digunakan
            </span>
          ) : item.claimed && !isExpired ? (
            <button
              className="gp-unlock-btn"
              style={{ background: "var(--gr, #7aba2a)", color: "#000", fontWeight: 700, padding: "6px 12px", fontSize: 12 }}
              onClick={() => onRedeem(item)}
              disabled={submitting}
            >
              Gunakan Sekarang
            </button>
          ) : isExpired ? (
            <span style={{ color: "var(--tx3)", fontSize: 12, fontWeight: 600 }}>
              Hangus
            </span>
          ) : (
            <button
              className={`gp-unlock-btn ${canAfford ? "buy" : "no"}`}
              style={{ padding: "6px 12px", fontSize: 12 }}
              onClick={() => onClaim(item)}
              disabled={!canAfford || submitting}
              title={canAfford ? "Klaim reward untuk minggu ini" : `Kurang ${(item.cost - userReward).toLocaleString("id-ID")} poin`}
            >
              {canAfford ? (
                <>Klaim</>
              ) : (
                <>Poin Kurang</>
              )}
            </button>
          )}
        </div>

      </div>
    </div>
  );
}

// ── Small Icon Clock Helper ───────────────────────────────────────────────────
function IconClock({ size = 12, color = "currentColor" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}

// ── Main Component: RewardShop ────────────────────────────────────────────────
export default function RewardShop({ reward = 0, unlockedRewards = [], onRedeem }) {
  const [catalogueData, setCatalogueData] = useState({ week_start: null, expires_at: null, items: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [tierFilter, setTierFilter] = useState("all");
  const [submittingId, setSubmittingId] = useState(null);
  const [bannerMsg, setBannerMsg] = useState(null);

  const fetchCatalogue = useCallback(async (force = false) => {
    setLoading(true);
    setError(null);
    try {
      const data = await loadCatalogue(force);
      if (data.error) {
        setError(data.error);
      } else {
        setCatalogueData(data);
      }
    } catch (err) {
      setError(err.message || "Failed to load catalogue");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCatalogue(false);
  }, [fetchCatalogue]);

  // Expiry countdown for the current week pool
  const { timeLeft: poolTimeLeft, isExpired: poolExpired } = useCountdown(catalogueData.expires_at);

  const handleClaim = async (item) => {
    setSubmittingId(item.id);
    setBannerMsg(null);
    try {
      const res = await claimWeeklyReward(item.id, catalogueData.week_start);
      if (res?.ok) {
        setBannerMsg({ type: "success", text: `Berhasil klaim "${item.name_id || item.name_en}"! Berlaku 14 hari.` });
        await fetchCatalogue(true);
      } else {
        setBannerMsg({ type: "error", text: res?.detail || "Gagal mengklaim reward." });
      }
    } catch (err) {
      setBannerMsg({ type: "error", text: err.message || "Terjadi kesalahan saat klaim." });
    } finally {
      setSubmittingId(null);
    }
  };

  const handleRedeem = async (item) => {
    if (!item.claim_id) return;
    setSubmittingId(item.id);
    setBannerMsg(null);
    try {
      const res = await redeemWeeklyReward(item.claim_id);
      if (res?.ok) {
        setBannerMsg({ type: "success", text: `Selamat! "${item.name_id || item.name_en}" berhasil digunakan.` });
        if (onRedeem) {
          onRedeem({ id: item.id, title: item.name_id || item.name_en, cost: item.cost });
        }
        await fetchCatalogue(true);
      } else {
        setBannerMsg({ type: "error", text: res?.detail || "Gagal menggunakan reward." });
      }
    } catch (err) {
      setBannerMsg({ type: "error", text: err.message || "Terjadi kesalahan saat redeem." });
    } finally {
      setSubmittingId(null);
    }
  };

  const items = catalogueData.items || [];

  const visibleItems = useMemo(() => {
    return items.filter(it => {
      const matchCat = categoryFilter === "all" || it.kategori === categoryFilter;
      const matchTier = tierFilter === "all" || it.tier === tierFilter;
      return matchCat && matchTier;
    });
  }, [items, categoryFilter, tierFilter]);

  const CATEGORIES = [
    { id: "all", label: "Semua Kategori" },
    { id: "minuman", label: "Minuman" },
    { id: "makanan", label: "Makanan" },
    { id: "snack", label: "Snack" },
    { id: "barang", label: "Barang" },
    { id: "pengalaman", label: "Pengalaman" },
  ];

  const TIERS = [
    { id: "all", label: "Semua Tier" },
    { id: "basic", label: "Basic" },
    { id: "mid", label: "Mid" },
    { id: "premium", label: "Premium" },
    { id: "ultra", label: "Ultra" },
  ];

  return (
    <div className="reward-shop-container" style={{ padding: "0 0 24px" }}>

      {/* Banner / Notice Message */}
      {bannerMsg && (
        <div style={{
          marginBottom: 16,
          padding: "10px 16px",
          borderRadius: 8,
          fontSize: 13,
          fontWeight: 600,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          background: bannerMsg.type === "success" ? "rgba(122,186,42,0.12)" : "rgba(232,113,77,0.12)",
          border: `1px solid ${bannerMsg.type === "success" ? "rgba(122,186,42,0.3)" : "rgba(232,113,77,0.3)"}`,
          color: bannerMsg.type === "success" ? "var(--gr, #7aba2a)" : "var(--rd, #e8714d)",
        }}>
          <span>{bannerMsg.text}</span>
          <button onClick={() => setBannerMsg(null)} style={{ background: "none", border: "none", color: "inherit", cursor: "pointer", padding: 2 }}>
            <IconClose size={12} />
          </button>
        </div>
      )}

      {/* Header Info Bar: Balance + Weekly Rotation Info + Countdown */}
      <div className="gp-balance-bar" style={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 12, padding: "14px 18px", borderRadius: 10, background: "var(--bg2)", border: "1px solid var(--bg3)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <IconCoin size={16} color="var(--ind, #fcd535)" />
            <span style={{ fontSize: 13, color: "var(--tx2)" }}>Poin Tersedia:</span>
            <span style={{ fontSize: 16, fontWeight: 700, color: "var(--tx)" }}>
              {reward.toLocaleString("id-ID")}
            </span>
          </div>
          {catalogueData.week_start && (
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "var(--tx3)" }}>
              <span>·</span>
              <span>Minggu {catalogueData.week_start}</span>
            </div>
          )}
        </div>

        {catalogueData.expires_at && (
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: poolExpired ? "var(--rd)" : "var(--tx2)" }}>
            <IconClock size={14} color={poolExpired ? "var(--rd)" : "var(--ind)"} />
            <span>Rotasi Baru Dalam: <strong>{poolTimeLeft}</strong></span>
          </div>
        )}
      </div>

      {/* Filter Row: Category Tabs */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, margin: "16px 0 10px" }}>
        {CATEGORIES.map(c => (
          <button
            key={c.id}
            onClick={() => setCategoryFilter(c.id)}
            className={`gp-filter-btn ${categoryFilter === c.id ? "active" : ""}`}
            style={{ fontSize: 12, padding: "6px 12px", borderRadius: 6 }}
          >
            {c.label}
          </button>
        ))}
      </div>

      {/* Sub-filter: Tier Pills */}
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 18 }}>
        <span style={{ fontSize: 11, color: "var(--tx3)", marginRight: 4 }}>Tier:</span>
        {TIERS.map(t => (
          <button
            key={t.id}
            onClick={() => setTierFilter(t.id)}
            style={{
              background: tierFilter === t.id ? "var(--bg3)" : "transparent",
              color: tierFilter === t.id ? "var(--tx)" : "var(--tx3)",
              border: `1px solid ${tierFilter === t.id ? "var(--bg4)" : "transparent"}`,
              borderRadius: 4,
              padding: "2px 8px",
              fontSize: 11,
              cursor: "pointer",
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Main Content Area: 5 UI States */}
      {loading ? (
        <ShopSkeleton />
      ) : error ? (
        <ShopError error={error} onRetry={() => fetchCatalogue(true)} />
      ) : items.length === 0 ? (
        <ShopEmpty onRefresh={() => fetchCatalogue(true)} />
      ) : visibleItems.length === 0 ? (
        <div style={{ padding: "36px 20px", textAlign: "center", color: "var(--tx3)", fontSize: 13, background: "var(--bg2)", borderRadius: 10 }}>
          Tidak ada item reward untuk filter yang dipilih.
        </div>
      ) : (
        <div className="gp-shop-grid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 16 }}>
          {visibleItems.map(item => (
            <WeeklyRewardCard
              key={item.id}
              item={item}
              userReward={reward}
              onClaim={handleClaim}
              onRedeem={handleRedeem}
              submitting={submittingId === item.id}
            />
          ))}
        </div>
      )}

    </div>
  );
}
