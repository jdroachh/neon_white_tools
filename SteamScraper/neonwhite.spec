# neonwhite.spec
# PyInstaller spec file for Neon White Leaderboard Tool (webview build)
# Run with: pyinstaller neonwhite.spec  (from SteamScraper/)
#
# Beta build (2026-05-10): Google SDK chain stripped — Sheets push is not
# wired into the pywebview app. To re-enable, restore the collect_all() block
# (see git log for prior version) and add `runtime_hooks=['rthook_google.py']`.

from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT

block_cipher = None

all_datas = [
    # React frontend build — served by the local HTTP server in main.py
    ('../frontend/dist', 'frontend/dist'),
]

# steam_api64.dll is NOT bundled — users supply it from their Neon White
# install via the dll_path setting. See README for placement instructions.
# shuffle.dll IS bundled — own code, required for the seed finder.
all_binaries = [
    ('shuffle.dll', '.'),
]

all_hidden = [
    'urllib.request',
    'json',
    'csv',
    'threading',
    'ctypes',
]

a = Analysis(
    ['run_app.py'],
    pathex=[],
    binaries=all_binaries,
    datas=all_datas,
    hiddenimports=all_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'PIL',
        'scipy',
        'setuptools',
        # Google SDK chain — excluded from beta build. If a transitive import
        # still pulls these in, PyInstaller will warn but exclude them.
        'google',
        'googleapiclient',
        'google_auth_oauthlib',
        'httplib2',
        'requests',
        'requests_oauthlib',
        'oauthlib',
        'uritemplate',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# onedir mode: EXE() holds only the launcher; COLLECT() assembles the full
# folder bundle in dist/NeonWhiteLeaderboardTool/. Logs and config live in
# %APPDATA%\NeonWhiteLeaderboardTool\ (since 1.6.0), not next to the EXE.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NeonWhiteLeaderboardTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='icon.ico',
    version='version_info.txt',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='NeonWhiteLeaderboardTool',
)
