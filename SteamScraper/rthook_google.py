# rthook_google.py
# Runtime hook — forces Google namespace packages to initialize correctly
# when running from a PyInstaller bundle on Python 3.12+
import sys
import importlib
import pkgutil

# Ensure the google namespace package is properly initialized
# before any google.* submodules are imported
try:
    import google
    if not hasattr(google, '__path__'):
        google.__path__ = []
except ImportError:
    pass

# Pre-initialize key subpackages to prevent lazy import failures
for pkg in [
    'google.auth',
    'google.oauth2',
    'google.api_core',
    'google.auth.transport',
    'google.auth.transport.requests',
    'google_auth_oauthlib',
    'googleapiclient',
]:
    try:
        importlib.import_module(pkg)
    except Exception:
        pass
