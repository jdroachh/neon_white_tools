import ctypes
import os
import re

DLL_PATH = r"C:\Program Files (x86)\Steam\steamapps\common\Neon White\Neon White_Data\Plugins\x86_64\steam_api64.dll"

with open(DLL_PATH, 'rb') as f:
    data = f.read()

strings = re.findall(b'SteamAPI_[A-Za-z0-9_]+', data)
unique = sorted(set(strings))

print(f"Found {len(unique)} SteamAPI_* exports:\n")
for s in unique:
    print(s.decode('utf-8'))