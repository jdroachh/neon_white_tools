"""
hell_rush — Hell Rush Mode healthpack spacing scorer.

Scores a shuffled 96-level order from 0 (terrible) to 100 (ideal spacing).
Used by the Seed Finder when hell_rush=True to rank or filter results.

Algorithm (user-specified 2026-05-06):
  1. Find 1-indexed positions of all 11 HP stages in the play order.
  2. Compute gaps: opening gap (0 → first HP) + gaps between consecutive HPs.
     The trailing gap (last HP → 96) is NOT included.
  3. ideal_gap = last_hp_position / hp_count
  4. std_dev of those gaps (population std dev; lower = more evenly spaced)
  5. early_penalty:       each HP in positions 1–3 → (4 - pos) × 5
  6. consecutive_penalty: each adjacent HP pair with gap ≤ 3 → (4 - gap) × 15
                          each adjacent HP pair with gap ≤ 5 → (6 - gap) × 5
  7. spread_penalty:      if last HP appears before position 70 → (70 - pos) × 2
  8. score = clamp(round(100 - std_dev / ideal_gap × 100)
                   - early_penalty - consecutive_penalty - spread_penalty, 0, 100)
"""
import math

HEALTHPACK_LEVELS: list[str] = [
    "Glass Port",
    "Jumper",
    "The Clocktower",
    "Apartment",
    "Fuse",
    "Estate",
    "Ricochet",
    "Fortress",
    "The Third Temple",
    "Congregation",
    "Absolution",
]
_HP_SET = frozenset(HEALTHPACK_LEVELS)


def score_hell_rush(level_order: list[str]) -> int:
    """
    Score a shuffled level order for Hell Rush healthpack spacing.

    level_order: list of 96 level name strings (White/Mikey rush order).
    Returns an int in [0, 100]. Higher = better spaced.
    """
    positions = [i + 1 for i, name in enumerate(level_order) if name in _HP_SET]
    if not positions:
        return 0

    hp_count = len(positions)
    last_pos  = positions[-1]

    # Gaps: opening gap from 0, then inter-HP gaps (no trailing gap)
    gaps = [positions[0]]  # positions[0] - 0
    for i in range(1, hp_count):
        gaps.append(positions[i] - positions[i - 1])

    ideal_gap = last_pos / hp_count

    mean     = sum(gaps) / len(gaps)
    variance = sum((g - mean) ** 2 for g in gaps) / len(gaps)
    std_dev  = math.sqrt(variance)

    early_penalty = sum((4 - pos) * 5 for pos in positions if pos <= 3)

    consecutive_penalty = 0
    for i in range(1, hp_count):
        gap = positions[i] - positions[i - 1]
        if gap <= 3:
            consecutive_penalty += (4 - gap) * 15
        elif gap <= 5:
            consecutive_penalty += (6 - gap) * 5

    spread_penalty = max(0, (70 - last_pos) * 2) if last_pos < 70 else 0

    base  = (100 - (std_dev / ideal_gap * 100)) if ideal_gap > 0 else 0
    score = round(base) - early_penalty - consecutive_penalty - spread_penalty
    return max(0, min(100, score))
