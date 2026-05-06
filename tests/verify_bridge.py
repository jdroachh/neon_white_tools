"""Quick verification script for bridge methods — run directly, not via pytest."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "SteamScraper"))
from webview_app.bridge import JsApi

api = JsApi()

r = api.parse_seed("White / Mikey", "12345")
assert r["ok"], r
assert r["level_count"] == 96
assert len(r["level_order"]) == 96
print("parse_seed OK:", r["level_order"][:3])

gold_in = [str(i + 1) for i in range(96)]
r2 = api.reorder_splits("White / Mikey", "12345", "\n".join(gold_in), "")
assert r2["ok"], r2
assert len(r2["gold"]) == 96
print("reorder_splits OK:", r2["gold"][:3])

r3 = api.standardize_splits("White / Mikey", "12345", "\n".join(r2["gold"]), "")
assert r3["ok"], r3
assert r3["gold"] == gold_in, f"round-trip failed: {r3['gold'][:5]}"
print("standardize round-trip OK")

r4 = api.parse_seed("White / Mikey", "0")
assert not r4["ok"]
print("error handling OK:", r4["error"])

# 8-level rush
r5 = api.parse_seed("Red", "999")
assert r5["ok"] and r5["level_count"] == 8
print("Red rush OK:", r5["level_order"])

print("\nAll bridge method checks passed.")
