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

export async function getStandardOrder(rushName) {
  const api = await waitForApi();
  return api.get_standard_order(rushName);
}

export async function startFinder(rushName, levelsStr, depth, mode, maxSeeds) {
  const api = await waitForApi();
  return api.start_finder(rushName, levelsStr, String(depth), mode, String(maxSeeds));
}

export async function stopFinder() {
  const api = await waitForApi();
  return api.stop_finder();
}

export async function loadTimerSeed(rushName, seed) {
  const api = await waitForApi();
  return api.load_timer_seed(rushName, String(seed));
}

export async function calculateTimer(rushName, seed, splitsText) {
  const api = await waitForApi();
  return api.calculate_timer(rushName, String(seed), splitsText);
}

// ── Config ──────────────────────────────────────────────────────────────────

export async function getConfig() {
  const api = await waitForApi();
  return api.get_config();
}

export async function saveConfigField(key, value) {
  const api = await waitForApi();
  return api.save_config_field(key, value);
}

// ── Steam ────────────────────────────────────────────────────────────────────

export async function initSteam(dllPath) {
  const api = await waitForApi();
  return api.init_steam(dllPath);
}

export async function getSteamStatus() {
  const api = await waitForApi();
  return api.get_steam_status();
}

export async function pickDllFile() {
  const api = await waitForApi();
  return api.pick_dll_file();
}

// ── Leaderboard metadata ─────────────────────────────────────────────────────

export async function getLevels() {
  const api = await waitForApi();
  return api.get_levels();
}

export async function getChapters() {
  const api = await waitForApi();
  return api.get_chapters();
}

// ── Leaderboard operations ───────────────────────────────────────────────────

export async function runGlobalExport(count) {
  const api = await waitForApi();
  return api.run_global_export(String(count));
}

export async function runLevelSearch(levelName, count) {
  const api = await waitForApi();
  return api.run_level_search(levelName, String(count));
}

export async function runPlayerLookup(steamId, mode, target) {
  const api = await waitForApi();
  return api.run_player_lookup(String(steamId), mode, String(target));
}

export async function stopLeaderboard() {
  const api = await waitForApi();
  return api.stop_leaderboard();
}
