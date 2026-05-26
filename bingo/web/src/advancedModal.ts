// Advanced Square Pool modal — host-only editor for per-square exclusions.
//
// Opens on top of the lobby. Section tabs (Standard / Level Completion /
// Modded), search box that filters within the active tab, tile grid of all
// squares with toggle-on-click, bulk select/deselect for visible items, and
// chapter-grouped headers (with tri-state toggle) on the Level Completion tab.
//
// Working state (`excluded` set + expand/collapse map) is local to the modal;
// changes commit only when the user clicks Save & close.

import squaresData from "../../squares.json";
import type { Settings } from "./protocol";

type Square = {
  id: string;
  name: string;
  mods_required: string[];
  verification: string;
  chapter?: string;
  stat_code?: string;
};
type SquaresJson = {
  standard: Square[];
  level_completion: Square[];
  modded: Square[];
};

const squares = squaresData as unknown as SquaresJson;

const SECTIONS = ["standard", "level_completion", "modded"] as const;
type SectionKey = (typeof SECTIONS)[number];
const SECTION_LABEL: Record<SectionKey, string> = {
  standard: "Standard",
  level_completion: "Level Completion",
  modded: "Modded",
};

export function openAdvancedModal(
  currentSettings: Settings,
  onSave: (excludedIds: string[]) => void,
): void {
  const excluded = new Set(currentSettings.excludedSquareIds);
  let activeTab: SectionKey = "standard";
  let searchQuery = "";
  const expandedChapters = new Map<string, boolean>();

  // ─── Overlay + chrome ───────────────────────────────────────────────────────
  const overlay = document.createElement("div");
  overlay.style.cssText =
    "position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:1000;display:flex;align-items:center;justify-content:center;";

  const modal = document.createElement("div");
  modal.style.cssText =
    "background:#1a1a1a;border:1px solid #444;border-radius:6px;width:min(92vw,900px);max-height:90vh;display:flex;flex-direction:column;font-family:monospace;color:#eee;";
  overlay.appendChild(modal);
  document.body.appendChild(overlay);

  const close = (): void => {
    document.removeEventListener("keydown", onEsc);
    overlay.remove();
  };
  const onEsc = (e: KeyboardEvent): void => {
    if (e.key === "Escape") close();
  };
  document.addEventListener("keydown", onEsc);
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) close();
  });

  // Header
  const header = document.createElement("div");
  header.style.cssText =
    "padding:14px 18px;border-bottom:1px solid #333;display:flex;align-items:center;gap:12px;";
  const title = document.createElement("h2");
  title.textContent = "Advanced: Square Pool";
  title.style.cssText = "margin:0;flex:1;font-size:1rem;";
  const closeBtn = document.createElement("button");
  closeBtn.textContent = "×";
  closeBtn.style.cssText =
    "background:transparent;color:#aaa;border:none;font-size:1.5rem;cursor:pointer;padding:0 8px;line-height:1;";
  closeBtn.addEventListener("click", close);
  header.appendChild(title);
  header.appendChild(closeBtn);
  modal.appendChild(header);

  // Tab bar
  const tabBar = document.createElement("div");
  tabBar.style.cssText =
    "display:flex;gap:4px;padding:8px 18px 0;border-bottom:1px solid #333;";
  modal.appendChild(tabBar);

  // Toolbar (search + count + bulk actions)
  const toolbar = document.createElement("div");
  toolbar.style.cssText =
    "padding:10px 18px;display:flex;gap:10px;align-items:center;flex-wrap:wrap;border-bottom:1px solid #2a2a2a;";
  modal.appendChild(toolbar);

  const searchInput = document.createElement("input");
  searchInput.type = "text";
  searchInput.placeholder = "Filter squares…";
  searchInput.style.cssText =
    "flex:1;min-width:200px;padding:6px 10px;background:#222;border:1px solid #444;color:#eee;font-family:monospace;border-radius:3px;";
  searchInput.addEventListener("input", () => {
    searchQuery = searchInput.value.toLowerCase().trim();
    renderBody();
  });
  toolbar.appendChild(searchInput);

  const countLabel = document.createElement("span");
  countLabel.style.cssText = "font-size:0.8rem;color:#888;white-space:nowrap;";
  toolbar.appendChild(countLabel);

  toolbar.appendChild(mkSmallBtn("Select all visible", () => bulkSet(true)));
  toolbar.appendChild(mkSmallBtn("Deselect all visible", () => bulkSet(false)));

  // Body (scrollable)
  const body = document.createElement("div");
  body.style.cssText = "flex:1;overflow-y:auto;padding:14px 18px;";
  modal.appendChild(body);

  // Footer
  const footer = document.createElement("div");
  footer.style.cssText =
    "padding:12px 18px;border-top:1px solid #333;display:flex;justify-content:flex-end;gap:8px;";
  const cancelBtn = document.createElement("button");
  cancelBtn.textContent = "Cancel";
  cancelBtn.style.cssText =
    "padding:8px 18px;background:#374151;color:#eee;border:none;border-radius:4px;cursor:pointer;font-family:monospace;";
  cancelBtn.addEventListener("click", close);
  const saveBtn = document.createElement("button");
  saveBtn.textContent = "Save & close";
  saveBtn.style.cssText =
    "padding:8px 18px;background:#2563eb;color:#fff;border:none;border-radius:4px;cursor:pointer;font-family:monospace;";
  saveBtn.addEventListener("click", () => {
    onSave(Array.from(excluded));
    close();
  });
  footer.appendChild(cancelBtn);
  footer.appendChild(saveBtn);
  modal.appendChild(footer);

  // ─── Render helpers ─────────────────────────────────────────────────────────
  function filteredSquaresFor(tab: SectionKey): Square[] {
    const all = squares[tab];
    if (!searchQuery) return all;
    return all.filter((s) => {
      if (s.name.toLowerCase().includes(searchQuery)) return true;
      if (s.mods_required.some((m) => m.toLowerCase().includes(searchQuery))) return true;
      const chapter = (s.chapter ?? "").toLowerCase();
      if (chapter.includes(searchQuery)) return true;
      // Also match "ch7" / "chapter 7" against a numeric chapter like "7 - Reckoning".
      const chapNum = chapter.match(/^(\d+)\s*-/)?.[1];
      if (chapNum) {
        if (searchQuery === `ch${chapNum}` || searchQuery === `chapter ${chapNum}` || searchQuery === `chapter${chapNum}`) return true;
      }
      return false;
    });
  }

  function bulkSet(enabled: boolean): void {
    for (const sq of filteredSquaresFor(activeTab)) {
      if (enabled) excluded.delete(sq.id);
      else excluded.add(sq.id);
    }
    renderTabs();
    renderBody();
  }

  function renderTabs(): void {
    tabBar.innerHTML = "";
    for (const tab of SECTIONS) {
      const total = squares[tab].length;
      const enabled = squares[tab].filter((s) => !excluded.has(s.id)).length;
      const btn = document.createElement("button");
      btn.textContent = `${SECTION_LABEL[tab]} (${enabled}/${total})`;
      const isActive = tab === activeTab;
      btn.style.cssText = `padding:8px 14px;background:${isActive ? "#1a1a1a" : "#2a2a2a"};color:${isActive ? "#fff" : "#aaa"};border:1px solid #333;border-bottom-color:${isActive ? "#1a1a1a" : "#333"};border-radius:4px 4px 0 0;cursor:pointer;font-family:monospace;font-size:0.85rem;margin-bottom:-1px;`;
      btn.addEventListener("click", () => {
        activeTab = tab;
        renderTabs();
        renderBody();
      });
      tabBar.appendChild(btn);
    }
  }

  function renderBody(): void {
    body.innerHTML = "";
    const visible = filteredSquaresFor(activeTab);
    const enabledVisible = visible.filter((s) => !excluded.has(s.id)).length;
    countLabel.textContent = `${enabledVisible} of ${visible.length} enabled${searchQuery ? " (filtered)" : ""}`;

    if (visible.length === 0) {
      const empty = document.createElement("div");
      empty.textContent = "No squares match your filter.";
      empty.style.cssText = "color:#666;text-align:center;padding:40px 0;";
      body.appendChild(empty);
      return;
    }

    if (activeTab === "level_completion") {
      renderGroupedBy(visible, (s) => s.chapter ?? "?");
    } else if (activeTab === "modded") {
      renderGroupedBy(visible, (s) => (s.mods_required.length > 0 ? [...s.mods_required].sort().join(" + ") : "Vanilla"));
    } else {
      renderTiles(visible, body);
    }
  }

  function renderGroupedBy(visible: Square[], keyFor: (s: Square) => string): void {
    // Preserve squares.json ordering via Map insertion order.
    const groups = new Map<string, Square[]>();
    for (const sq of visible) {
      const key = keyFor(sq);
      const arr = groups.get(key) ?? [];
      arr.push(sq);
      groups.set(key, arr);
    }

    for (const [chapter, items] of groups) {
      const enabledHere = items.filter((s) => !excluded.has(s.id)).length;
      const triState =
        enabledHere === items.length ? "all" : enabledHere === 0 ? "none" : "mixed";
      const triMark = triState === "all" ? "☑" : triState === "none" ? "☐" : "◐";
      const expanded = expandedChapters.get(chapter) ?? true;

      const headerEl = document.createElement("div");
      headerEl.style.cssText =
        "display:flex;align-items:center;gap:10px;margin:14px 0 8px;padding:6px 0;border-bottom:1px solid #2a2a2a;cursor:pointer;user-select:none;";

      const caret = document.createElement("span");
      caret.textContent = expanded ? "▼" : "▶";
      caret.style.cssText = "font-size:0.7rem;color:#666;width:12px;";

      const titleSpan = document.createElement("span");
      titleSpan.textContent = chapter;
      titleSpan.style.cssText = "flex:1;color:#ccc;font-weight:bold;font-size:0.9rem;";

      const counter = document.createElement("span");
      counter.textContent = `${triMark} ${enabledHere}/${items.length}`;
      counter.style.cssText =
        "font-size:0.8rem;color:#888;padding:2px 8px;background:#2a2a2a;border-radius:3px;";
      counter.title = "Click to toggle all stages in this chapter";
      counter.addEventListener("click", (e) => {
        e.stopPropagation();
        const enableAll = triState !== "all";
        for (const sq of items) {
          if (enableAll) excluded.delete(sq.id);
          else excluded.add(sq.id);
        }
        renderTabs();
        renderBody();
      });

      headerEl.appendChild(caret);
      headerEl.appendChild(titleSpan);
      headerEl.appendChild(counter);
      headerEl.addEventListener("click", () => {
        expandedChapters.set(chapter, !expanded);
        renderBody();
      });
      body.appendChild(headerEl);

      if (expanded) {
        const groupWrap = document.createElement("div");
        renderTiles(items, groupWrap);
        body.appendChild(groupWrap);
      }
    }
  }

  function renderTiles(items: Square[], parent: HTMLElement): void {
    const grid = document.createElement("div");
    grid.style.cssText =
      "display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:8px;";
    for (const sq of items) {
      const enabled = !excluded.has(sq.id);
      const tile = document.createElement("div");
      // Strip "Complete " prefix on level_completion tiles — chapter header already provides context.
      const displayName =
        activeTab === "level_completion" && sq.name.startsWith("Complete ")
          ? sq.name.slice("Complete ".length)
          : sq.name;
      tile.textContent = displayName;
      const titleParts: string[] = [sq.name];
      if (sq.chapter) titleParts.push(sq.chapter);
      if (sq.mods_required.length > 0) titleParts.push(`Mods: ${sq.mods_required.join(", ")}`);
      tile.title = titleParts.join(" — ");
      tile.style.cssText = `min-height:80px;padding:8px;border:1px solid ${enabled ? "#2563eb" : "#333"};background:${enabled ? "#1e2a4a" : "#1a1a1a"};color:${enabled ? "#fff" : "#666"};border-radius:4px;cursor:pointer;font-size:0.7rem;line-height:1.3;display:flex;align-items:center;justify-content:center;text-align:center;word-break:break-word;user-select:none;${enabled ? "" : "text-decoration:line-through;"}`;
      tile.addEventListener("click", () => {
        if (excluded.has(sq.id)) excluded.delete(sq.id);
        else excluded.add(sq.id);
        renderTabs();
        renderBody();
      });
      grid.appendChild(tile);
    }
    parent.appendChild(grid);
  }

  function mkSmallBtn(label: string, onClick: () => void): HTMLButtonElement {
    const b = document.createElement("button");
    b.textContent = label;
    b.style.cssText =
      "padding:5px 10px;background:#2a2a2a;color:#ccc;border:1px solid #444;border-radius:3px;cursor:pointer;font-family:monospace;font-size:0.75rem;";
    b.addEventListener("click", onClick);
    return b;
  }

  renderTabs();
  renderBody();
}
