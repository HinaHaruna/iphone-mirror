"""Webtoon screenshot capture: full-screen PNG, auto-numbered, organized by series/chapter."""
from __future__ import annotations

import re
from pathlib import Path

from PIL import ImageGrab


_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize(name: str) -> str:
    """Make a filesystem-safe folder name on Windows."""
    name = (name or "").strip()
    if not name:
        return "untitled"
    name = _INVALID_CHARS.sub("_", name)
    name = re.sub(r"\s+", "_", name)
    name = name.rstrip(". _")
    return name or "untitled"


def next_chapter_label(current: str) -> str:
    """Increment a chapter label like '01' → '02', 'ep_3' → 'ep_4'. Falls back to suffix '_2'."""
    cur = (current or "").strip()
    if not cur:
        return "01"
    m = re.match(r"^(.*?)(\d+)(\D*)$", cur)
    if m:
        prefix, num, suffix = m.groups()
        new_num = str(int(num) + 1).zfill(len(num))
        return f"{prefix}{new_num}{suffix}"
    return f"{cur}_2"


class WebtoonCapture:
    """Saves full-screen PNGs into <base>/<series>/<chapter>/NNN.png with auto-numbering.

    On (re)opening an existing chapter folder, the counter resumes from the highest
    numeric filename so a session can be paused and continued.
    """

    def __init__(self, base_dir: str | Path, series: str, chapter: str, all_screens: bool = False):
        self.base_dir = Path(base_dir)
        self._series = sanitize(series)
        self._chapter = sanitize(chapter)
        self.all_screens = all_screens
        self._counter = 0
        self._refresh_counter()

    @property
    def output_dir(self) -> Path:
        return self.base_dir / self._series / self._chapter

    @property
    def series(self) -> str:
        return self._series

    @property
    def chapter(self) -> str:
        return self._chapter

    @property
    def counter(self) -> int:
        return self._counter

    def update(
        self,
        base_dir: str | Path | None = None,
        series: str | None = None,
        chapter: str | None = None,
    ) -> bool:
        """Apply new target settings; returns True if the output dir changed."""
        prev_dir = self.output_dir
        if base_dir is not None:
            self.base_dir = Path(base_dir)
        if series is not None:
            self._series = sanitize(series)
        if chapter is not None:
            self._chapter = sanitize(chapter)
        changed = self.output_dir != prev_dir
        if changed:
            self._refresh_counter()
        return changed

    def _refresh_counter(self) -> None:
        out = self.output_dir
        if not out.exists():
            self._counter = 0
            return
        nums: list[int] = []
        for p in out.glob("*.png"):
            stem = p.stem
            if stem.isdigit():
                nums.append(int(stem))
        self._counter = max(nums) if nums else 0

    def capture(self) -> Path:
        """Grab the screen and save the next numbered PNG. Returns the saved path."""
        out = self.output_dir
        out.mkdir(parents=True, exist_ok=True)
        self._counter += 1
        path = out / f"{self._counter:03d}.png"
        img = ImageGrab.grab(all_screens=self.all_screens)
        img.save(path, "PNG")
        return path
