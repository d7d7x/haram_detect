import os
import sys
import zipfile
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
MPV_DIR = BASE_DIR / "data" / "mpv"

def download_and_extract_mpv():
    MPV_DIR.mkdir(parents=True, exist_ok=True)
    target_exe = MPV_DIR / "mpv.exe"
    if target_exe.exists():
        print(f"Portable MPV already exists at: {target_exe}")
        return str(target_exe)

    zip_url = "https://github.com/mpv-player/mpv/releases/download/v0.41.0/mpv-v0.41.0-x86_64-pc-windows-msvc.zip"
    zip_path = MPV_DIR / "mpv_portable.zip"

    print(f"Downloading portable MPV from {zip_url}...")
    headers = {"User-Agent": "Mozilla/5.0"}
    req = urllib.request.Request(zip_url, headers=headers)
    with urllib.request.urlopen(req) as resp, open(zip_path, "wb") as f:
        f.write(resp.read())

    print("Extracting portable MPV...")
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(MPV_DIR)

    if zip_path.exists():
        try:
            os.remove(zip_path)
        except Exception:
            pass

    if target_exe.exists():
        print(f"Portable MPV extracted successfully to {target_exe}")
        return str(target_exe)
    
    return None

if __name__ == "__main__":
    download_and_extract_mpv()
