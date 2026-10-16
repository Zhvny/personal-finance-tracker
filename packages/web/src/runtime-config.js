export function getRuntimeApiBase() {
  try {
    if (window.__API_BASE__ && typeof window.__API_BASE__ === "string") {
      return window.__API_BASE__.replace(/\/$/, "");
    }
  } catch {
    // ignore
  }
  return "/api";
}
