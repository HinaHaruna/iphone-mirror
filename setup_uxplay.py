"""Locate the UxPlay binary on Windows.

UxPlay does NOT ship a Windows .exe in its GitHub releases — it has to be
compiled from source via MSYS2. This module's job is to *find* an existing
build, not to download one.

Resolution order:
  1. Explicit path in config.json -> "uxplay_path"
  2. ./bin/uxplay.exe (bundled / built by build_uxplay.ps1)
  3. PATH lookup for `uxplay`
  4. Common MSYS2 install locations
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BIN_DIR = ROOT / "bin"

COMMON_MSYS2_PREFIXES = [
    Path(r"C:\msys64\ucrt64\bin"),
    Path(r"C:\msys64\mingw64\bin"),
    Path(r"C:\msys64\clang64\bin"),
    Path(r"D:\msys64\ucrt64\bin"),
    Path(r"D:\msys64\mingw64\bin"),
]


def find_uxplay(custom_path: str | None = None) -> Path | None:
    """Return the first uxplay.exe we can locate, or None."""
    candidates: list[Path] = []
    if custom_path:
        candidates.append(Path(custom_path))
    candidates += [
        BIN_DIR / "uxplay.exe",
        BIN_DIR / "UxPlay.exe",
    ]
    for prefix in COMMON_MSYS2_PREFIXES:
        candidates.append(prefix / "uxplay.exe")

    for c in candidates:
        if c.is_file():
            return c.resolve()

    on_path = shutil.which("uxplay") or shutil.which("uxplay.exe")
    if on_path:
        return Path(on_path).resolve()
    return None


def build_instructions() -> str:
    """Human-readable instructions shown when the binary cannot be found."""
    return (
        "ไม่พบ uxplay.exe บนเครื่อง\n\n"
        "UxPlay บน Windows ต้อง build เองด้วย MSYS2:\n"
        "  1) ติดตั้ง MSYS2: https://www.msys2.org/\n"
        "  2) เปิดสคริปต์ build_uxplay.ps1 ในโฟลเดอร์นี้ (Run with PowerShell)\n"
        "     หรือดูคู่มือใน BUILD_WINDOWS.md\n\n"
        "ถ้า build ที่อื่นแล้ว: กดปุ่ม \"เลือกไฟล์ uxplay.exe...\" ใน GUI"
    )


if __name__ == "__main__":
    p = find_uxplay()
    if p:
        print(f"Found: {p}")
    else:
        print(build_instructions())
        os._exit(1)
