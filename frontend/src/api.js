/**
 * api.js — thin wrapper over window.pywebview.api.
 * pywebview injects the api object asynchronously after page load,
 * so all calls go through waitForApi() which retries until ready.
 */

function waitForApi() {
  return new Promise((resolve) => {
    function check() {
      if (window.pywebview && window.pywebview.api) {
        resolve(window.pywebview.api);
      } else {
        setTimeout(check, 50);
      }
    }
    check();
  });
}

export async function ping() {
  const api = await waitForApi();
  return api.ping();
}

export async function getRushes() {
  const api = await waitForApi();
  return api.get_rushes();
}

export async function parseSeed(rushName, seed) {
  const api = await waitForApi();
  return api.parse_seed(rushName, String(seed));
}

export async function reorderSplits(rushName, seed, gold, segments) {
  const api = await waitForApi();
  return api.reorder_splits(rushName, String(seed), gold, segments);
}

export async function standardizeSplits(rushName, seed, gold, segments) {
  const api = await waitForApi();
  return api.standardize_splits(rushName, String(seed), gold, segments);
}
