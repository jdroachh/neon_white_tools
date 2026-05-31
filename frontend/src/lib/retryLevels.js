/**
 * loadWithRetry — fetch a list from the bridge with first-boot resilience.
 *
 * Bridge metadata calls (getLevels, getChapters, ...) occasionally reject or
 * return an empty array on the very first call after pywebview boots, even
 * past waitForApi(). Retrying for ~5s past that gets the dropdown populated
 * without forcing a user-visible restart.
 *
 * Returns a cancel function — call from a useEffect cleanup.
 */
export function loadWithRetry(fetchFn, { onData, attempts = 20, delayMs = 250 } = {}) {
  let cancelled = false;
  let n = 0;
  function tryLoad() {
    fetchFn().then(data => {
      if (cancelled) return;
      if (Array.isArray(data) && data.length) { onData(data); return; }
      if (n++ < attempts) setTimeout(tryLoad, delayMs);
    }).catch(() => {
      if (!cancelled && n++ < attempts) setTimeout(tryLoad, delayMs);
    });
  }
  tryLoad();
  return () => { cancelled = true; };
}

/**
 * loadLevelsWithRetry — thin alias kept for existing call sites. Wraps
 * loadWithRetry, mapping its `onLevels` option onto the generic `onData`.
 */
export function loadLevelsWithRetry(getLevels, { onLevels, attempts = 20, delayMs = 250 } = {}) {
  return loadWithRetry(getLevels, { onData: onLevels, attempts, delayMs });
}
