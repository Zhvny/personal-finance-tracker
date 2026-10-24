// ─── rewardCatalogue.js ───────────────────────────────────────────────────────
// Reward catalogue loader — reads from API (which merges local + Google Drive).
//
// Clean Architecture: Infrastructure layer. Only this file knows about the
//   data source for rewards. Components use the resolved catalogue objects.
// ─────────────────────────────────────────────────────────────────────────────

import { apiFetch } from "../finance/useApi.js";

const BASE = "/rewards";

// ── Tier metadata (DRY — single source of truth for UI rendering) ─────────────
export const TIER_META = Object.freeze({
  basic:   { color: "#38bdf8",  label: "Basic",   order: 1 },
  mid:     { color: "#34d399",  label: "Mid",     order: 2 },
  premium: { color: "#a78bfa",  label: "Premium", order: 3 },
  ultra:   { color: "#fcd535",  label: "Ultra",   order: 4 },
});

export const CATEGORY_META = Object.freeze({
  minuman:    { label: "Minuman",    en: "Drinks",      order: 1 },
  makanan:    { label: "Makanan",    en: "Food",        order: 2 },
  snack:      { label: "Snack",      en: "Snacks",      order: 3 },
  barang:     { label: "Barang",     en: "Goods",       order: 4 },
  pengalaman: { label: "Pengalaman", en: "Experiences", order: 5 },
});

// ── Content file → public URL ─────────────────────────────────────────────────
export const contentUrl = (manifest, filename) => {
  const item = manifest.contents?.find(c => c.file === filename);
  
  // If backend provided a direct URL (e.g. Drive Proxy), use it
  if (item?.url) return item.url;
  
  // Otherwise fallback to local public/rewards path
  return `${BASE}/${manifest.id}/${filename}`;
};

// ── Thumbnail: thumbnail_url → first photo → first video → null ──────────────
export const thumbnailUrl = (manifest) => {
  if (manifest.thumbnail_url) return manifest.thumbnail_url;
  const firstPhoto = manifest.contents?.find(c => c.type === "photo");
  if (firstPhoto) return contentUrl(manifest, firstPhoto.file);
  const firstVideo = manifest.contents?.find(c => c.type === "video");
  if (firstVideo) return contentUrl(manifest, firstVideo.file);
  return null;
};

// ── Is the thumbnail a video file (needs <video> element to render) ───────────
export const thumbnailIsVideo = (manifest) => {
  // If the backend provided a masked thumbnail (Drive Proxy sz=w500), it's always an image
  if (manifest._thumb_is_drive) return false;
  
  const hasPhoto = manifest.contents?.some(c => c.type === "photo");
  if (hasPhoto) return false;
  return manifest.contents?.some(c => c.type === "video") ?? false;
};

// ── In-memory cache for the catalogue ─────────────────────────────────────────
let _cachedCatalogue = null;

// ── Load full catalogue from API ──────────────────────────────────────────────
export async function loadCatalogue(forceRefresh = false) {
  if (_cachedCatalogue && !forceRefresh) return _cachedCatalogue;
  
  try {
    const data = await apiFetch("/rewards/catalogue");
    if (!data) return { week_start: null, expires_at: null, items: [] };
    
    const isArray = Array.isArray(data);
    const rawItems = isArray ? data : (data.items ?? []);
    
    const sorted = rawItems.sort((a, b) => {
      const ta = TIER_META[a.tier]?.order ?? 0;
      const tb = TIER_META[b.tier]?.order ?? 0;
      if (ta !== tb) return ta - tb;
      return a.cost - b.cost;
    });

    const result = {
      week_start: isArray ? null : data.week_start,
      expires_at: isArray ? null : data.expires_at,
      halal_only: isArray ? true : (data.halal_only ?? true),
      items: sorted,
    };
    
    _cachedCatalogue = result;
    return result;
  } catch (err) {
    console.error("Failed to load rewards catalogue:", err);
    return { week_start: null, expires_at: null, items: [], error: err.message || "Failed to load catalogue" };
  }
}

export async function claimWeeklyReward(itemId, weekStart) {
  return await apiFetch("/rewards/weekly/claim", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ item_id: itemId, week_start: weekStart }),
  });
}

export async function redeemWeeklyReward(claimId) {
  return await apiFetch("/rewards/weekly/redeem", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ claim_id: claimId }),
  });
}

export async function updateRewardPreferences(preferences) {
  return await apiFetch("/rewards/preferences", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(preferences),
  });
}

// ── Count content by type ─────────────────────────────────────────────────────
export const countContent = (manifest) => ({
  photos: (manifest.contents ?? []).filter(c => c.type === "photo").length,
  videos: (manifest.contents ?? []).filter(c => c.type === "video").length,
});

// ── Content type → display label ─────────────────────────────────────────────
export const contentLabel = ({ photos, videos }) => {
  const parts = [];
  if (photos > 0) parts.push(`${photos} photos`);
  if (videos > 0) parts.push(`${videos} video`);
  return parts.join(" · ") || "No content";
};
