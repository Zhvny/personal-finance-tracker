// ─── RewardShop.jsx ─────────────────────────────────────────────────────────────
// Reward Shop — reads from public/rewards/ folder system.
// Zero emojis — all icons from ../icons.jsx.
// ─────────────────────────────────────────────────────────────────────────────

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { createPortal } from "react-dom";
import { loadCatalogue, TIER_META, contentUrl, thumbnailUrl, thumbnailIsVideo, countContent, contentLabel } from "./rewardCatalogue.js";
import { currentSeason } from "./rewardEngine.js";
import {
  IconCoin, IconAward, IconStar, IconTrophy, IconSparkles, IconImage,
  IconVideo, IconUnlock, IconClose, IconWarning, IconCheck, IconSeason,
  IconStore, IconGift,
} from "../icons.jsx";

// ─── ContentViewer ─────────────────────────────────────────────────────────────
function ContentViewer({ manifest, onClose }) {
  const [idx, setIdx] = useState(0);
  const contents = manifest.contents ?? [];
  const item = contents[idx];

  useEffect(() => {
    // Lock scroll on body/content when viewer is open
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const contentEl = document.querySelector(".content");
    const prevContent = contentEl ? contentEl.style.overflow : "";
    if (contentEl) contentEl.style.overflow = "hidden";

    const h = (e) => {
      if (e.key === "ArrowLeft")  setIdx(i => Math.max(0, i - 1));
      if (e.key === "ArrowRight") setIdx(i => Math.min(contents.length - 1, i + 1));
      if (e.key === "Escape")     onClose();
    };
    window.addEventListener("keydown", h);
    return () => {
      window.removeEventListener("keydown", h);
      document.body.style.overflow = prev;
      if (contentEl) contentEl.style.overflow = prevContent;
    };
  }, [contents.length, onClose]);

  if (!item) return null;

  return createPortal(
    <div className="gp-modal-overlay" onClick={onClose}
      style={{ alignItems: "flex-start", padding: 20, overflowY: "auto" }}
    >
      <div className="gp-content-viewer" onClick={e => e.stopPropagation()}>
        <div className="gcv-header">
          <div>
            <div className="gcv-title">{manifest.title}</div>
            <div className="gcv-count">{idx + 1} / {contents.length} · {item.caption || item.file}</div>
          </div>
          <button className="gcv-close" onClick={onClose}><IconClose size={14} /></button>
        </div>

        <div className="gcv-stage">
          {item.type === "photo"
            ? <img src={contentUrl(manifest, item.file)} alt={item.caption || ""} className="gcv-img" loading="lazy" onError={e => { e.target.style.display = "none"; }} />
            : item.type === "video"
            ? <video key={item.file} src={contentUrl(manifest, item.file)} className="gcv-video" controls autoPlay playsInline />
            : <div className="gcv-unsupported">Unsupported format</div>
          }
        </div>

        <div className="gcv-strip">
          {contents.map((c, i) => {
            const isDrive = !!c.drive_id;
            const thumbUrl = isDrive 
              ? `/api/rewards/media/${c.drive_id}?sz=w120` 
              : contentUrl(manifest, c.file);
              
            return (
              <div key={i} className={"gcv-thumb" + (i === idx ? " active" : "")} onClick={() => setIdx(i)}>
                {c.type === "photo"
                  ? <img src={thumbUrl} alt="" className="gcv-thumb-img" onError={() => {}} />
                  : <div className="gcv-thumb-vid" style={{ position: "relative", width: "100%", height: "100%" }}>
                      <img src={thumbUrl} alt="" className="gcv-thumb-img" style={{ opacity: .7 }} />
                      <div style={{ 
                        position: "absolute", bottom: 2, right: 2, 
                        background: "rgba(0,0,0,0.6)", borderRadius: 4, 
                        width: 14, height: 14, display: "flex", 
                        alignItems: "center", justifyContent: "center",
                        pointerEvents: "none" 
                      }}>
                        <IconVideo size={10} color="#fff" />
                      </div>
                    </div>
                }
              </div>
            );
          })}
        </div>

        {contents.length > 1 && (
          <>
            <button className="gcv-nav left"  onClick={() => setIdx(i => Math.max(0, i - 1))}                    disabled={idx === 0}>‹</button>
            <button className="gcv-nav right" onClick={() => setIdx(i => Math.min(contents.length - 1, i + 1))}  disabled={idx === contents.length - 1}>›</button>
          </>
        )}
      </div>
    </div>,
    document.body
  );
}

// ─── UnlockModal ───────────────────────────────────────────────────────────────
function UnlockModal({ manifest, currentReward, onConfirm, onClose }) {
  const canAfford  = currentReward >= manifest.cost;
  const counts     = countContent(manifest);
  const thumb      = thumbnailUrl(manifest);
  const isVidThumb = thumbnailIsVideo(manifest);

  // Task 3 — Reward modal behavior:
  //   • Freeze background scroll while unlock modal is open.
  //   • Block Esc key — modal is only closeable via explicit Cancel/Unlock buttons.
  //   • gp-modal is pinned to center via CSS position:fixed (handled in rewards.css).
  useEffect(() => {
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const blockEsc = (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopImmediatePropagation();
      }
    };
    // Capture phase so it fires before any other handlers
    window.addEventListener("keydown", blockEsc, true);

    return () => {
      document.body.style.overflow = prevOverflow;
      window.removeEventListener("keydown", blockEsc, true);
    };
  }, []);

  return createPortal(
    // Overlay does NOT close modal on click — interaction is fully controlled by buttons
    <div className="gp-modal-overlay gp-modal-overlay--locked">
      <div className="gp-modal" onClick={e => e.stopPropagation()}>
        <div className="gp-modal-thumb">
          {thumb
            ? isVidThumb
              ? <video src={thumb} muted playsInline preload="metadata"
                  style={{ width: "100%", height: "100%", objectFit: "cover", opacity: .45, display: "block" }}
                  onError={e => { e.target.style.display = "none"; }} />
              : <img src={thumb} alt="" style={{ width: "100%", height: "100%", objectFit: "cover", opacity: .45 }} onError={() => {}} />
            : <IconGift size={48} color="var(--gp-tx3)" />
          }
          <div className="gp-modal-thumb-overlay" />
          <div className="gp-modal-thumb-label">{contentLabel(counts).toUpperCase()}</div>
        </div>

        <div className="gp-modal-title">{manifest.title}</div>


        <div className="gp-modal-cost">
          <div>
            <div className="gp-modal-cost-lbl">Price</div>
            <div className="gp-modal-cost-val">
              <IconCoin size={16} color="var(--gp-fire)" />
              {manifest.cost.toLocaleString("id-ID")} Reward
            </div>
          </div>
          <div style={{ textAlign: "right" }}>
            <div className="gp-modal-cost-lbl">Your Reward</div>
            <div style={{ fontFamily: "var(--gp-mono)", fontSize: 18, fontWeight: 700, color: canAfford ? "#4ade80" : "var(--gp-tx3)" }}>
              {currentReward.toLocaleString("id-ID")}
            </div>
          </div>
        </div>

        {!canAfford && (
          <div className="gp-modal-warn">
            <IconWarning size={13} />
            Need {(manifest.cost - currentReward).toLocaleString("id-ID")} more Reward. Keep saving!
          </div>
        )}

        <div className="gp-modal-btns">
          <button className="gp-btn gp-btn-ghost" onClick={onClose}>Cancel</button>
          {canAfford && (
            <button className="gp-btn gp-btn-primary" onClick={() => { onConfirm(manifest); onClose(); }}>
              <IconUnlock size={14} /> Unlock Now
            </button>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
}

// ─── LazyMedia ────────────────────────────────────────────────────────────────
function LazyMedia({ src, isVideo, alt, style, className }) {
  const [visible, setVisible] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setVisible(true); },
      { rootMargin: "100px" }
    );
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={ref} className={className} style={{ ...style, position: "relative", overflow: "hidden", background: "var(--gp-bg3)" }}>
      {visible && (
        isVideo ? (
          <video
            src={src}
            muted playsInline preload="metadata"
            className={"gp-lazy-media" + (loaded ? " loaded" : "")}
            style={{ 
              width: "100%", height: "100%", objectFit: "cover", display: "block", 
              transition: "opacity .6s ease, filter .6s ease",
              filter: loaded ? "none" : "blur(10px)"
            }}
            onLoadedData={() => setLoaded(true)}
            onError={e => { e.target.style.display = "none"; }}
          />
        ) : (
          <img
            src={src}
            alt={alt}
            className={"gp-lazy-media" + (loaded ? " loaded" : "")}
            style={{ 
              width: "100%", height: "100%", objectFit: "cover", display: "block", 
              transition: "opacity .6s ease, filter .6s ease",
              filter: loaded ? "none" : "blur(10px)"
            }}
            onLoad={() => setLoaded(true)}
            onError={() => {}}
          />
        )
      )}
      {!loaded && <div className="gp-shimmer" style={{ position: "absolute", inset: 0 }} />}
    </div>
  );
}

// ─── RewardCard ────────────────────────────────────────────────────────────────
function RewardCard({ manifest, isUnlocked, canAfford, onSelect, onView }) {
  const tier   = TIER_META[manifest.tier] ?? TIER_META.basic;
  const counts = countContent(manifest);
  const thumb  = thumbnailUrl(manifest);
  const isVidThumb = thumbnailIsVideo(manifest);
  const isActiveSeason = manifest.season === currentSeason();

  // PRE-FETCH LOGIC: When user hovers, tell backend to warm up the actual content
  const handleMouseEnter = () => {
    if (isUnlocked && manifest.contents?.[0]?.drive_id) {
      const fid = manifest.contents[0].drive_id;
      // Trigger a silent probe request to warm up the server-to-google connection
      fetch(`/api/rewards/media/${fid}`, { method: "GET", headers: { "Range": "bytes=0-1" } }).catch(() => {});
    }
  };

  const status = isUnlocked ? "unlocked" : canAfford ? "locked" : "locked cant-afford";

  return (
    <div 
      className={"gp-card " + status} 
      onClick={() => isUnlocked ? onView(manifest) : onSelect(manifest)}
      onMouseEnter={handleMouseEnter}
    >
      <div className="gp-card-thumb">
        {thumb ? (
          <LazyMedia
            src={thumb}
            isVideo={isVidThumb}
            alt={manifest.title}
            className="gp-card-thumb-media"
            style={{ width: "100%", height: "100%", opacity: isUnlocked ? 1 : 0.35 }}
          />
        ) : (
          <div className="gp-card-thumb-placeholder"><IconGift size={36} color="var(--gp-tx3)" /></div>
        )}

        {isUnlocked
          ? <div className="gp-card-unlocked-badge"><IconCheck size={9} /> UNLOCKED</div>
          : !canAfford
          ? <div className="gp-card-thumb-lock"><IconStar size={22} color="var(--gp-tx3)" /></div>
          : null
        }
      </div>

      <div className="gp-card-body">
        <div className="gp-card-meta">
          <span className="gp-card-type" style={{ color: tier.color }}>{manifest.type} · {tier.label}</span>
          <div style={{ display: "flex", alignItems: "center", gap: 4, flexShrink: 0 }}>
            {isActiveSeason && (
              <span className="gp-card-season-badge" style={{ position: "static", display: "inline-flex" }}>
                <IconSeason size={8} /> S{manifest.season + 1}
              </span>
            )}
            <span className="gp-card-season-tag">S{manifest.season + 1}</span>
          </div>
        </div>
        <div className="gp-card-title">{manifest.title}</div>

        <div className="gp-card-content-count">
          {counts.photos > 0 && <span><IconImage size={10} /> {counts.photos} photos</span>}
          {counts.videos > 0 && <span><IconVideo size={10} /> {counts.videos} video</span>}
        </div>

        <div className="gp-card-foot">
          {isUnlocked ? (
            <button
              className="gp-unlock-btn done"
              style={{ width: "100%" }}
              onClick={e => { e.stopPropagation(); onView(manifest); }}
            >
              <IconImage size={12} /> View
            </button>
          ) : (
            <>
              <div className="gp-card-cost">
                <IconCoin size={13} /> {manifest.cost.toLocaleString("id-ID")}
              </div>
              <button
                className={"gp-unlock-btn " + (canAfford ? "buy" : "no")}
                onClick={e => { e.stopPropagation(); onSelect(manifest); }}
              >
                {canAfford ? <><IconUnlock size={12} /> Unlock</> : <><IconStar size={12} /> Lock</>}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── RewardShop ─────────────────────────────────────────────────────────────────
export default function RewardShop({ reward, unlockedRewards, onRedeem }) {
  const [catalogue,  setCatalogue]  = useState([]);
  const [catLoading, setCatLoading] = useState(true);
  const [selected,   setSelected]   = useState(null);
  const [viewing,    setViewing]    = useState(null);
  const [filter,     setFilter]     = useState("all");
  const season = currentSeason();

  useEffect(() => {
    loadCatalogue().then(cat => { setCatalogue(cat); setCatLoading(false); });
  }, []);

  const handleRedeem = useCallback(async (manifest) => {
    const result = await onRedeem({ id: manifest.id, title: manifest.title, cost: manifest.cost });
    if (result?.ok) setViewing(manifest);
  }, [onRedeem]);

  const seasons = [...new Set(catalogue.map(r => r.season))].sort();
  const visible = catalogue.filter(r => filter === "all" ? true : r.season === Number(filter));

  if (catLoading) {
    return (
      <div className="gp-empty">
        <IconStore size={32} color="var(--gp-tx3)" />
        <div className="gp-empty-txt">Loading reward catalogue…</div>
      </div>
    );
  }

  return (
    <div>
      {/* Season filter */}
      <div className="gp-filter-row">
        {[{ label: "All", val: "all" }, ...seasons.map(s => ({ label: "Season " + (s + 1), val: s }))].map(({ label, val }) => {
          const isActive  = filter === val;
          const isCurrent = val === season;
          return (
            <button key={String(val)} onClick={() => setFilter(val)} className={"gp-filter-btn" + (isActive ? " active" : "")}>
              {isCurrent && <IconSeason size={9} />}
              {label}
              {isCurrent && <span className="gp-filter-live">Active</span>}
            </button>
          );
        })}
      </div>

      {/* Balance bar */}
      <div className="gp-balance-bar">
        <div className="gp-balance-left">
          <IconCoin size={13} color="var(--gp-fire2)" />
          <span>Your Reward:</span>
          <span className="gp-balance-val">{reward.toLocaleString("id-ID")}</span>
        </div>
        <div className="gp-balance-right">
          <IconAward size={12} color="var(--gp-tx3)" />
          <span>{unlockedRewards.length} / {catalogue.length} unlocked</span>
        </div>
      </div>

      {visible.length > 0 ? (
        <div className="gp-shop-grid">
          {visible.map(m => (
            <RewardCard key={m.id} manifest={m}
              isUnlocked={unlockedRewards.includes(m.id)}
              canAfford={reward >= m.cost}
              onSelect={setSelected} onView={setViewing}
            />
          ))}
        </div>
      ) : (
        <div className="gp-empty">
          <IconGift size={32} color="var(--gp-tx3)" />
          <div className="gp-empty-txt">No rewards yet.<br />Add a folder in <code>public/rewards/</code></div>
        </div>
      )}

      {selected && !unlockedRewards.includes(selected.id) && (
        <UnlockModal manifest={selected} currentReward={reward} onConfirm={handleRedeem} onClose={() => setSelected(null)} />
      )}
      {viewing && <ContentViewer manifest={viewing} onClose={() => setViewing(null)} />}
    </div>
  );
}
