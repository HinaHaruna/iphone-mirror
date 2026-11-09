"""Quality picker shown when the user presses Start: choose resolution + FPS."""
from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from display_utils import primary_display_mode
from uxplay_manager import FPS_CHOICES, parse_resolution

# (value, label, hint)
RESOLUTION_CHOICES: list[tuple[str, str, str]] = [
    ("3840x2160", "4K  ·  3840×2160", "ชัดที่สุด — ใช้ HEVC, ต้องเป็น iPhone รุ่นใหม่ + Wi-Fi 5/6"),
    ("2560x1440", "2K  ·  2560×1440", "ชัดมาก — ใช้ HEVC, ภาระเน็ตน้อยกว่า 4K"),
    ("1920x1080", "Full HD  ·  1920×1080", "เสถียรสุด รองรับทุกรุ่น"),
    ("1280x720", "HD  ·  1280×720", "Wi-Fi ไม่แรง / อยากได้ความหน่วงต่ำสุด"),
]


class StartDialog(ctk.CTkToplevel):
    """Modal dialog. After it closes, `result` is None (cancelled) or
    {"resolution": "WxH", "fps": int, "ask_on_start": bool}."""

    def __init__(self, master: ctk.CTk, resolution: str, fps: int, ask_on_start: bool = True):
        super().__init__(master)
        self.result: dict | None = None
        self.title("เลือกคุณภาพภาพ")
        self.resizable(False, False)
        self.transient(master)

        w, h = parse_resolution(resolution)
        current = f"{w}x{h}"
        choices = list(RESOLUTION_CHOICES)
        mode = primary_display_mode()
        if mode:
            mw, mh, hz = mode
            key = f"{mw}x{mh}"
            if key not in (c[0] for c in choices):
                choices.append((key, f"ตามจอคอม  ·  {mw}×{mh}", f"ตรงกับจอหลัก ({hz}Hz)"))
        if current not in (c[0] for c in choices):
            choices.append((current, f"กำหนดเอง  ·  {w}×{h}", "ค่าที่พิมพ์ไว้ในหน้าหลัก"))

        self.res_var = tk.StringVar(value=current)
        self.fps_var = tk.StringVar(value=str(fps) if fps in FPS_CHOICES else str(FPS_CHOICES[-1]))
        self.ask_var = tk.BooleanVar(value=ask_on_start)

        pad = {"padx": 18}
        ctk.CTkLabel(self, text="ความละเอียด", font=ctk.CTkFont(size=15, weight="bold")).pack(
            anchor="w", pady=(16, 6), **pad
        )
        for value, label, hint in choices:
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.pack(fill="x", pady=2, **pad)
            ctk.CTkRadioButton(row, text=label, value=value, variable=self.res_var, width=210).pack(side="left")
            ctk.CTkLabel(row, text=hint, text_color="#9a9a9a").pack(side="left", padx=(8, 0))

        ctk.CTkLabel(self, text="FPS", font=ctk.CTkFont(size=15, weight="bold")).pack(
            anchor="w", pady=(16, 6), **pad
        )
        ctk.CTkSegmentedButton(
            self, values=[str(f) for f in FPS_CHOICES], variable=self.fps_var,
            command=lambda _v: self._update_fps_hint(),
        ).pack(fill="x", **pad)
        self.fps_hint = ctk.CTkLabel(self, text="", anchor="w", justify="left")
        self.fps_hint.pack(fill="x", pady=(6, 0), **pad)
        self._monitor_hz = mode[2] if mode else 0
        self._update_fps_hint()

        ctk.CTkCheckBox(self, text="ถามทุกครั้งที่กดเริ่ม", variable=self.ask_var).pack(
            anchor="w", pady=(14, 4), **pad
        )

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", pady=(10, 16), **pad)
        ctk.CTkButton(
            btns, text="▶  เริ่ม", height=40, font=ctk.CTkFont(size=14, weight="bold"),
            command=self._on_ok,
        ).pack(side="right")
        ctk.CTkButton(
            btns, text="ยกเลิก", height=40, width=100, fg_color="#555", hover_color="#444",
            command=self._on_cancel,
        ).pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda _e: self._on_ok())
        self.bind("<Escape>", lambda _e: self._on_cancel())
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        self._center_on(master)
        # CTkToplevel finishes its own setup asynchronously on Windows; grab after it's visible.
        self.after(150, self._activate)

    def _update_fps_hint(self) -> None:
        fps = int(self.fps_var.get())
        hz = self._monitor_hz
        if hz and fps > hz:
            self.fps_hint.configure(
                text=f"จอหลักเป็น {hz}Hz — โชว์ได้สูงสุด {hz} fps (iPhone ยังส่ง {fps} ได้ ภาพจะตอบสนองไวขึ้นเล็กน้อย)",
                text_color="#db8",
            )
        elif fps >= 90:
            self.fps_hint.configure(
                text="90/120 fps ได้จริงเฉพาะ iPhone ที่มีจอ ProMotion (รุ่น Pro) — รุ่นอื่นจะส่งมาสูงสุด 60",
                text_color="#9a9a9a",
            )
        else:
            self.fps_hint.configure(text="", text_color="#9a9a9a")

    def _center_on(self, master: ctk.CTk) -> None:
        self.update_idletasks()
        mw, mh = master.winfo_width(), master.winfo_height()
        mx, my = master.winfo_rootx(), master.winfo_rooty()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        self.geometry(f"+{mx + max(0, (mw - w) // 2)}+{my + max(0, (mh - h) // 3)}")

    def _activate(self) -> None:
        try:
            self.lift()
            self.focus_force()
            self.grab_set()
        except tk.TclError:
            pass

    def _on_ok(self) -> None:
        self.result = {
            "resolution": self.res_var.get(),
            "fps": int(self.fps_var.get()),
            "ask_on_start": bool(self.ask_var.get()),
        }
        self.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.destroy()
