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
  basic:   { color: "#8a8599",  label: "Basic",   order: 1 },
  mid:     { color: "#ff6f60",  label: "Mid",     order: 2 },
  premium: { color: "#f5c842",  label: "Premium", order: 3 },
  ultra:   { color: "#ffe4fc",  label: "Ultra",   order: 4 },
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
    if (!data) return [];
    
    const sorted = data.sort((a, b) => {
      // Sort: season ASC, then tier order ASC, then cost ASC
      if (a.season !== b.season) return a.season - b.season;
      const ta = TIER_META[a.tier]?.order ?? 0;
      const tb = TIER_META[b.tier]?.order ?? 0;
      if (ta !== tb) return ta - tb;
      return a.cost - b.cost;
    });
    
    _cachedCatalogue = sorted;
    return sorted;
  } catch (err) {
    console.error("Failed to load rewards catalogue:", err);
    return [];
  }
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
