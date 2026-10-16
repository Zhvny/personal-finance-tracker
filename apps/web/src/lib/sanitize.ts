/**
 * lib/sanitize.ts
 * ─────────────────────────────────────────────────────────────────────────────
 * Centralized input sanitization utilities.
 * Apply these at BOTH the onChange layer (real-time) AND at submit time.
 * ─────────────────────────────────────────────────────────────────────────────
 */

/** Strip all HTML/XML tags to neutralize XSS vectors. */
export function stripTags(value: string): string {
  return value.replace(/<[^>]*>?/gm, "");
}

/**
 * Sanitize free-form text (notes, descriptions, tasks).
 * - Strips HTML tags
 * - Collapses repeated whitespace / newlines to a single space/newline
 * - Trims leading/trailing whitespace
 * - Enforces max length (default 500 chars)
 */
export function sanitizeText(value: string, maxLength = 500): string {
  if (!value) return "";
  return stripTags(value)
    .replace(/[\u0000-\u001F\u007F]/g, " ") // strip control characters
    .replace(/  +/g, " ")                    // collapse multiple spaces
    .trim()
    .slice(0, maxLength);
}

/**
 * Sanitize a single-line text input (no newlines allowed).
 * Suitable for: project names, titles, short descriptions.
 */
export function sanitizeOneLiner(value: string, maxLength = 200): string {
  if (!value) return "";
  return stripTags(value)
    .replace(/[\r\n\t]/g, " ")              // flatten newlines/tabs
    .replace(/[\u0000-\u001F\u007F]/g, "")  // strip control chars
    .replace(/  +/g, " ")                   // collapse spaces
    .trim()
    .slice(0, maxLength);
}

/**
 * Sanitize a search query string.
 * - Strips HTML tags
 * - Removes characters commonly used in injection attacks
 * - Enforces max length (default 120 chars)
 */
export function sanitizeSearch(value: string, maxLength = 120): string {
  if (!value) return "";
  return stripTags(value)
    .replace(/[<>"'`;]/g, "")              // strip injection-prone punctuation
    .replace(/[\u0000-\u001F\u007F]/g, "") // strip control chars
    .trim()
    .slice(0, maxLength);
}

/**
 * Validate and normalize a date string to YYYY-MM-DD.
 * Returns the original string if it matches, empty string if invalid.
 */
export function sanitizeDate(value: string): string {
  if (!value) return "";
  const trimmed = value.trim();
  // Must match YYYY-MM-DD exactly
  if (!/^\d{4}-\d{2}-\d{2}$/.test(trimmed)) return "";
  const d = new Date(trimmed);
  if (isNaN(d.getTime())) return "";
  // Prevent absurd future/past dates (reasonable range: 2000–2100)
  const year = d.getFullYear();
  if (year < 2000 || year > 2100) return "";
  return trimmed;
}

/**
 * Clamp a numeric string to [min, max].
 * Returns the clamped number as a string, or "" if the input is not a valid number.
 */
export function sanitizeNumber(
  value: string,
  min = -Infinity,
  max = Infinity
): string {
  if (value === "" || value === "-") return value; // allow typing in progress
  const n = parseFloat(value);
  if (isNaN(n)) return "";
  return String(Math.min(max, Math.max(min, n)));
}

/**
 * Parse a sanitized numeric string into a number for API submission.
 * Falls back to `fallback` if empty/NaN.
 */
export function parseNum(value: string, fallback = 0): number {
  const n = parseFloat(value);
  return isNaN(n) ? fallback : n;
}
