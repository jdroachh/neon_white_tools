"""
progress — evaluate_js helper for server→client event streaming.

Used by long-running operations (Seed Finder, Global Export) to push
progress events to the webview without blocking the Python handler.

M2 implementation: wire a background thread that drains the multiprocessing
Queue from seed_search._seed_search_worker and calls emit() on each item.
"""
# TODO(M2): implement emit() and the drainer thread
