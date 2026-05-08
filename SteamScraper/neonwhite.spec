# neonwhite.spec
# PyInstaller spec file for Neon White Leaderboard Tool
# Run with: pyinstaller neonwhite.spec  (from SteamScraper/)

import sys
from PyInstaller.building.build_main import Analysis, PYZ, EXE
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

# Google libraries — kept for sheets.py (optional feature; not used by the
# webview frontend but still present in SteamScraper/ and pulled in by
# PyInstaller's static analysis). Remove this block once confirmed unused
# in a post-migration smoke test.
google_auth_datas,        google_auth_bins,        google_auth_hidden        = collect_all('google.auth')
google_oauth2_datas,      google_oauth2_bins,      google_oauth2_hidden      = collect_all('google.oauth2')
google_api_core_datas,    google_api_core_bins,    google_api_core_hidden    = collect_all('google.api_core')
googleapiclient_datas,    googleapiclient_bins,    googleapiclient_hidden    = collect_all('googleapiclient')
google_oauthlib_datas,    google_oauthlib_bins,    google_oauthlib_hidden    = collect_all('google_auth_oauthlib')
httplib2_datas,           httplib2_bins,           httplib2_hidden           = collect_all('httplib2')
requests_datas,           requests_bins,           requests_hidden           = collect_all('requests')
requests_oauthlib_datas,  requests_oauthlib_bins,  requests_oauthlib_hidden  = collect_all('requests_oauthlib')
uritemplate_datas,        uritemplate_bins,        uritemplate_hidden        = collect_all('uritemplate')

all_datas = (
    google_auth_datas + google_oauth2_datas + google_api_core_datas +
    googleapiclient_datas + google_oauthlib_datas + httplib2_datas +
    requests_datas + requests_oauthlib_datas + uritemplate_datas +
    # React frontend build — served by the local HTTP server in main.py
    [('../frontend/dist', 'frontend/dist')]
)

all_binaries = (
    google_auth_bins + google_oauth2_bins + google_api_core_bins +
    googleapiclient_bins + google_oauthlib_bins + httplib2_bins +
    requests_bins + requests_oauthlib_bins + uritemplate_bins
    # steam_api64.dll is NOT bundled — users supply it from their Neon White
    # install via the dll_path setting. See README for placement instructions.
)

all_hidden = (
    google_auth_hidden + google_oauth2_hidden + google_api_core_hidden +
    googleapiclient_hidden + google_oauthlib_hidden + httplib2_hidden +
    requests_hidden + requests_oauthlib_hidden + uritemplate_hidden +
    collect_submodules('google') +
    collect_submodules('googleapiclient') +
    collect_submodules('google_auth_oauthlib') +
    [
        'google.oauth2.credentials',
        'google.auth.transport.requests',
        'google.auth.transport.urllib3',
        'google.auth._helpers',
        'google.auth.exceptions',
        'google.auth.crypt',
        'google.auth.crypt._python_rsa',
        'google.auth.crypt._cryptography_rsa',
        'google_auth_oauthlib.flow',
        'googleapiclient.discovery',
        'googleapiclient.errors',
        'googleapiclient.http',
        'googleapiclient._helpers',
        'httplib2',
        'uritemplate',
        'requests',
        'requests.adapters',
        'requests.auth',
        'requests.cookies',
        'requests_oauthlib',
        'oauthlib',
        'oauthlib.oauth2',
        'urllib.request',
        'json',
        'csv',
        'threading',
        'ctypes',
    ]
)

a = Analysis(
    ['webview_app/main.py'],
    pathex=[],
    binaries=all_binaries,
    datas=all_datas,
    hiddenimports=all_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['rthook_google.py'],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'PIL',
        'scipy',
        'setuptools',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='NeonWhiteLeaderboardTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='icon.ico',
)
