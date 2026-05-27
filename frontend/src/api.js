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

export async function getCheaterCount() {
  const api = await waitForApi();
  return api.get_cheater_count();
}

export async function minimizeWindow() {
  const api = await waitForApi();
  return api.minimize_window();
}


export async function toggleMaximize() {
  const api = await waitForApi();
  return api.toggle_maximize();
}

export async function closeWindow() {
  const api = await waitForApi();
  return api.close_window();
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

export async function startFinder(rushName, levelsStr, depth, mode, maxSeeds, hellRush, hellRushMin, forceFirst, excludedLevels, excludedWindow, orderMatters) {
  const api = await waitForApi();
  return api.start_finder(rushName, levelsStr, String(depth), mode, String(maxSeeds),
                          !!hellRush, String(hellRushMin ?? "70"), String(forceFirst ?? ""),
                          String(excludedLevels ?? ""), String(excludedWindow ?? ""),
                          !!orderMatters);
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

// ── Accent color ─────────────────────────────────────────────────────────────

export function applyAccent(hex) {
  const el = document.querySelector('.hifi') || document.documentElement;
  el.style.setProperty('--accent', hex);
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

export async function saveConfigFields(fields) {
  const api = await waitForApi();
  return api.save_config_fields(fields);
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

export async function pickFolder() {
  const api = await waitForApi();
  return api.pick_folder();
}

export async function openLogFolder() {
  const api = await waitForApi();
  return api.open_log_folder();
}

export async function findSteamDll() {
  const api = await waitForApi();
  return api.find_steam_dll();
}

export async function getAppVersion() {
  const api = await waitForApi();
  return api.get_app_version();
}

export async function checkForUpdate() {
  const api = await waitForApi();
  return api.check_for_update();
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

export async function runGlobalExport(count, outMode = "display", folder = "") {
  const api = await waitForApi();
  return api.run_global_export(String(count), outMode, folder);
}

export async function runGlobalNeonRankings(count, outMode = "display", folder = "") {
  const api = await waitForApi();
  return api.run_global_neon_rankings(String(count), outMode, folder);
}

export async function getGlobalNeonRank(steamId) {
  const api = await waitForApi();
  return api.get_global_neon_rank(String(steamId));
}

export async function runLevelSearch(levelName, count, outMode = "display", folder = "") {
  const api = await waitForApi();
  return api.run_level_search(levelName, String(count), outMode, folder);
}

export async function runPlayerLookup(steamId, mode, target, outMode = "display", folder = "") {
  const api = await waitForApi();
  return api.run_player_lookup(String(steamId), mode, String(target), outMode, folder);
}

export async function runComparePlayers(steamId1, steamId2, mode, target, outMode = "display", folder = "") {
  const api = await waitForApi();
  return api.run_compare_players(String(steamId1), String(steamId2), mode, String(target), outMode, folder);
}

export async function runMultiCompare(steamIds, mode, target = "") {
  const api = await waitForApi();
  return api.run_multi_compare(steamIds.map(String), mode, String(target));
}

export async function stopMultiCompare() {
  const api = await waitForApi();
  return api.stop_multi_compare();
}

export async function stopLeaderboard() {
  const api = await waitForApi();
  return api.stop_leaderboard();
}

export async function getMedalTimes(level) {
  const api = await waitForApi();
  return api.get_medal_times(level);
}

// ── Resources (Ghosts + Route Videos) ────────────────────────────────────────

export async function getResourcesStatus() {
  const api = await waitForApi();
  return api.get_resources_status();
}

export async function getGhosts(level, medal) {
  const api = await waitForApi();
  return api.get_ghosts(level, medal);
}

export async function getVideos(level, medal) {
  const api = await waitForApi();
  return api.get_videos(level, medal);
}

export async function getWorldRecord(level, platform) {
  const api = await waitForApi();
  return api.get_world_record(level, platform);
}

export async function openExternalUrl(url) {
  const api = await waitForApi();
  return api.open_external_url(url);
}

export async function getGuides() {
  const api = await waitForApi();
  return api.get_guides();
}

export async function getHelpfulLinks() {
  const api = await waitForApi();
  return api.get_helpful_links();
}
