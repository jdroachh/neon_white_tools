import { useState } from "react";

// Crosshair hover highlight for result grids. Spread `tbodyProps` on the
// <tbody>, put `data-row={i}` on each <tr>, and merge `cellHL(rowIdx, colIdx)`
// into each cell's style. A cell brightens when its row OR column is under the
// mouse. The highlight is an inset box-shadow (not a background) so it layers
// over any existing cell background — see --row-hl in styles.css.
//
// Bounded to ~level-count rows (~90–121) on the pages that use it, so the
// per-move re-render is cheap. Hover detection is delegated to one pair of
// handlers on the tbody rather than per-cell listeners.
export function useCrosshair() {
  const [hover, setHover] = useState({ row: -1, col: -1 });

  const tbodyProps = {
    onMouseOver: (e) => {
      const td = e.target.closest("td");
      if (!td) return;
      const tr = td.closest("tr");
      const row = tr ? Number(tr.getAttribute("data-row")) : -1;
      const col = td.cellIndex;
      setHover((h) => (h.row === row && h.col === col ? h : { row, col }));
    },
    onMouseLeave: () => setHover({ row: -1, col: -1 }),
  };

  const HL = { boxShadow: "inset 0 0 0 9999px var(--row-hl)" };
  const HL_CENTER = { boxShadow: "inset 0 0 0 9999px var(--row-hl-center)" };
  const cellHL = (row, col) => {
    const onRow = row === hover.row;
    const onCol = col === hover.col;
    if (onRow && onCol) return HL_CENTER;   // the hovered cell itself — brightest
    return onRow || onCol ? HL : null;
  };

  return { hover, tbodyProps, cellHL };
}
