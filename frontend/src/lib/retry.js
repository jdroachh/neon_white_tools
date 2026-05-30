/**
 * retryUntilOk — call an async bridge method until it returns an acceptable
 * value, retrying through transient first-boot failures.
 *
 * pywebview's JS bridge is occasionally not fully wired up when the first
 * useEffect runs after launch. getConfig() / getSteamStatus() can reject or
 * resolve to null in that window; the frontend then silently falls back to
 * defaults ("welcome unseen", no accent, no DLL) and the user sees a wrong
 * boot state. Retrying for ~10s past that gets the real values without
 * forcing the user to restart.
 *
 * @param {() => Promise<any>} fn       Bridge call.
 * @param {(v:any) => boolean} isOk     Predicate — true means the value is real.
 * @param {object}             opts
 * @param {number}             opts.attempts  Default 40.
 * @param {number}             opts.delayMs   Default 250.
 * @param {string}             opts.label     For console.warn on retries.
 * @returns {Promise<any|null>}                Resolves with the first ok value,
 *                                             or null after exhaustion.
 */
export function retryUntilOk(fn, isOk, { attempts = 40, delayMs = 250, label = "bridge" } = {}) {
  return new Promise(resolve => {
    let n = 0;
    function tryOnce() {
      fn().then(v => {
        if (isOk(v)) { resolve(v); return; }
        if (n++ < attempts) { console.warn(`[retry] ${label} returned not-ok (attempt ${n}/${attempts})`); setTimeout(tryOnce, delayMs); }
        else { console.warn(`[retry] ${label} gave up after ${attempts} attempts`); resolve(null); }
      }).catch(err => {
        if (n++ < attempts) { console.warn(`[retry] ${label} threw (attempt ${n}/${attempts}):`, err && err.message || err); setTimeout(tryOnce, delayMs); }
        else { console.warn(`[retry] ${label} gave up after ${attempts} attempts`); resolve(null); }
      });
    }
    tryOnce();
  });
}
