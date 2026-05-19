/**
 * loadLevelsWithRetry — fetch the level list with first-boot resilience.
 *
 * getLevels() occasionally rejects or returns an empty array on the very
 * first call after pywebview boots; retrying for ~5s past that gets the
 * dropdown populated without forcing a user-visible restart.
 *
 * Returns a cancel function — call from a useEffect cleanup.
 */
export function loadLevelsWithRetry(getLevels, { onLevels, attempts = 20, delayMs = 250 } = {}) {
  let cancelled = false;
  let n = 0;
  function tryLoad() {
    getLevels().then(ls => {
      if (cancelled) return;
      if (Array.isArray(ls) && ls.length) { onLevels(ls); return; }
      if (n++ < attempts) setTimeout(tryLoad, delayMs);
    }).catch(() => {
      if (!cancelled && n++ < attempts) setTimeout(tryLoad, delayMs);
    });
  }
  tryLoad();
  return () => { cancelled = true; };
}
