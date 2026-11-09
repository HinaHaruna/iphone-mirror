"""iPhone Mirror — GUI wrapper around UxPlay.

Run:    python app.py
Build:  pip install -r requirements.txt
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import tkinter as tk
import traceback
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from capture import WebtoonCapture, next_chapter_label
from display_utils import primary_display_mode
from network_utils import bonjour_running, get_lan_ip, try_start_bonjour
from setup_uxplay import build_instructions, find_uxplay
from start_dialog import StartDialog
from uxplay_manager import (
    DEFAULT_RESOLUTION,
    FPS_CHOICES,
    RESOLUTION_PRESETS,
    UxPlayConfig,
    UxPlayManager,
    needs_hevc,
    parse_resolution,
)

try:
    import keyboard as _kb  # global hotkey support (optional)
except Exception:
    _kb = None

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
BUILD_SCRIPT = ROOT / "build_uxplay.ps1"

DEFAULT_CAPTURE_BASE = str(Path.home() / "Pictures" / "iPhone Mirror")

# If UxPlay dies on its own after running at least this long, restart it automatically.
# (A crash right after start usually means a config/DLL problem — restarting would just loop.)
AUTO_RESTART_MIN_UPTIME = 10.0
MAX_AUTO_RESTARTS = 5

DEFAULT_CONFIG = {
    "name": "Windows AirPlay",
    "fps": 120,
    "codec": "hevc",
    "resolution": DEFAULT_RESOLUTION["hevc"],
    "audio": True,
    "fullscreen": False,
    "low_latency": True,
    "ask_on_start": True,
    "uxplay_path": "",
    "capture_base": DEFAULT_CAPTURE_BASE,
    "capture_series": "",
    "capture_chapter": "01",
    "capture_hotkey": "f8",
    "capture_all_screens": False,
}


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            return {**DEFAULT_CONFIG, **data}
        except json.JSONDecodeError:
            pass
    return dict(DEFAULT_CONFIG)


def save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("iPhone Mirror — AirPlay Receiver")
        self.geometry("820x820")
        self.minsize(760, 720)

        self.cfg = load_config()
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.manager: UxPlayManager | None = None
        self._capturer: WebtoonCapture | None = None
        self._hotkey_handle = None
        self._registered_hotkey: str | None = None
        self._restart_count = 0

        self._build_ui()
        self._refresh_status()
        self._update_cap_status()
        self._setup_hotkey()
        self.after(200, self._drain_logs)
        self.after(1000, self._tick)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- UI ----------
    def _build_ui(self) -> None:
        header = ctk.CTkFrame(self, corner_radius=0)
        header.pack(fill="x", padx=0, pady=0)

        ctk.CTkLabel(
            header, text="iPhone Mirror", font=ctk.CTkFont(size=22, weight="bold")
        ).pack(side="left", padx=20, pady=14)
        self.status_dot = ctk.CTkLabel(header, text="●  หยุด", text_color="#888")
        self.status_dot.pack(side="right", padx=20)

        body = ctk.CTkFrame(self)
        body.pack(fill="both", expand=True, padx=14, pady=10)

        # Connection info card
        info = ctk.CTkFrame(body)
        info.pack(fill="x", padx=10, pady=10)
        self.ip_label = ctk.CTkLabel(info, text="LAN IP: ...", font=ctk.CTkFont(size=14))
        self.ip_label.pack(anchor="w", padx=14, pady=(10, 2))
        self.name_label = ctk.CTkLabel(info, text=f"ชื่อเครื่องรับ: {self.cfg['name']}")
        self.name_label.pack(anchor="w", padx=14, pady=2)
        self.bonjour_label = ctk.CTkLabel(info, text="Bonjour: ตรวจสอบ...")
        self.bonjour_label.pack(anchor="w", padx=14, pady=(2, 10))

        # Settings
        settings = ctk.CTkFrame(body)
        settings.pack(fill="x", padx=10, pady=6)

        ctk.CTkLabel(settings, text="FPS").grid(row=0, column=0, padx=(14, 6), pady=(10, 4), sticky="w")
        self.fps_var = tk.IntVar(value=self.cfg["fps"])
        self.fps_menu = ctk.CTkOptionMenu(
            settings, values=[str(f) for f in FPS_CHOICES], width=90,
            command=self._on_fps_change,
        )
        self.fps_menu.set(str(self.cfg["fps"]))
        self.fps_menu.grid(row=0, column=1, padx=6, pady=(10, 4), sticky="w")

        ctk.CTkLabel(settings, text="Codec").grid(row=0, column=2, padx=(16, 6), pady=(10, 4), sticky="w")
        self.codec_var = tk.StringVar(value=self.cfg["codec"])
        codec_menu = ctk.CTkOptionMenu(
            settings, values=["hevc", "h264"], width=90,
            variable=self.codec_var, command=self._on_codec_change,
        )
        codec_menu.grid(row=0, column=3, padx=6, pady=(10, 4), sticky="w")

        ctk.CTkLabel(settings, text="ความละเอียด").grid(
            row=0, column=4, padx=(16, 6), pady=(10, 4), sticky="w"
        )
        self.res_var = tk.StringVar(
            value=self.cfg.get("resolution") or DEFAULT_RESOLUTION.get(self.cfg["codec"], "3840x2160")
        )
        ctk.CTkComboBox(
            settings, values=RESOLUTION_PRESETS, variable=self.res_var, width=130,
        ).grid(row=0, column=5, padx=(6, 14), pady=(10, 4), sticky="w")

        self.audio_var = tk.BooleanVar(value=self.cfg["audio"])
        ctk.CTkCheckBox(settings, text="เสียง", variable=self.audio_var).grid(
            row=1, column=0, columnspan=2, padx=14, pady=(4, 6), sticky="w"
        )
        self.low_lat_var = tk.BooleanVar(value=self.cfg["low_latency"])
        ctk.CTkCheckBox(settings, text="Low-latency", variable=self.low_lat_var).grid(
            row=1, column=2, columnspan=2, padx=14, pady=(4, 6), sticky="w"
        )
        self.fs_var = tk.BooleanVar(value=self.cfg["fullscreen"])
        ctk.CTkCheckBox(settings, text="Fullscreen (Alt+Enter สลับได้)", variable=self.fs_var).grid(
            row=1, column=4, columnspan=2, padx=14, pady=(4, 6), sticky="w"
        )

        self.ask_start_var = tk.BooleanVar(value=self.cfg.get("ask_on_start", True))
        ctk.CTkCheckBox(
            settings, text="ให้เลือกความละเอียด / FPS ทุกครั้งที่กดเริ่ม",
            variable=self.ask_start_var, command=self._persist,
        ).grid(row=2, column=0, columnspan=6, padx=14, pady=(4, 6), sticky="w")

        self.display_label = ctk.CTkLabel(settings, text="", anchor="w", justify="left")
        self.display_label.grid(row=3, column=0, columnspan=6, padx=14, pady=(0, 10), sticky="w")
        self._update_display_hint()

        # Buttons
        btn_row = ctk.CTkFrame(body, fg_color="transparent")
        btn_row.pack(fill="x", padx=10, pady=(8, 4))
        self.start_btn = ctk.CTkButton(
            btn_row, text="▶  เริ่มรับสัญญาณ AirPlay", height=44,
            font=ctk.CTkFont(size=15, weight="bold"), command=self._on_start,
        )
        self.start_btn.pack(side="left", padx=(4, 8), pady=4)
        self.stop_btn = ctk.CTkButton(
            btn_row, text="■  หยุด", height=44, fg_color="#a23",
            hover_color="#812", command=self._on_stop, state="disabled",
        )
        self.stop_btn.pack(side="left", padx=4, pady=4)
        ctk.CTkButton(
            btn_row, text="เลือกไฟล์ uxplay.exe...", height=44,
            command=self._on_browse,
        ).pack(side="right", padx=4, pady=4)
        ctk.CTkButton(
            btn_row, text="Build UxPlay (MSYS2)", height=44, fg_color="#555",
            hover_color="#444", command=self._on_build,
        ).pack(side="right", padx=4, pady=4)

        # Webtoon capture card
        cap = ctk.CTkFrame(body)
        cap.pack(fill="x", padx=10, pady=6)
        cap.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            cap, text="📸 Webtoon Capture", font=ctk.CTkFont(size=15, weight="bold")
        ).grid(row=0, column=0, columnspan=4, padx=14, pady=(10, 4), sticky="w")

        ctk.CTkLabel(cap, text="โฟลเดอร์").grid(row=1, column=0, padx=(14, 6), pady=4, sticky="e")
        self.cap_base_var = tk.StringVar(value=self.cfg.get("capture_base", DEFAULT_CAPTURE_BASE))
        ctk.CTkEntry(cap, textvariable=self.cap_base_var).grid(
            row=1, column=1, columnspan=2, padx=4, pady=4, sticky="we"
        )
        ctk.CTkButton(cap, text="...", width=42, command=self._on_pick_capture_base).grid(
            row=1, column=3, padx=(4, 14), pady=4
        )

        ctk.CTkLabel(cap, text="ชื่อเรื่อง").grid(row=2, column=0, padx=(14, 6), pady=4, sticky="e")
        self.cap_series_var = tk.StringVar(value=self.cfg.get("capture_series", ""))
        ctk.CTkEntry(cap, textvariable=self.cap_series_var).grid(
            row=2, column=1, padx=4, pady=4, sticky="we"
        )
        ctk.CTkLabel(cap, text="ตอน").grid(row=2, column=2, padx=(14, 6), pady=4, sticky="e")
        self.cap_chapter_var = tk.StringVar(value=self.cfg.get("capture_chapter", "01"))
        ctk.CTkEntry(cap, textvariable=self.cap_chapter_var, width=120).grid(
            row=2, column=3, padx=(4, 14), pady=4, sticky="w"
        )

        ctk.CTkLabel(cap, text="Hotkey").grid(row=3, column=0, padx=(14, 6), pady=4, sticky="e")
        self.cap_hotkey_var = tk.StringVar(value=self.cfg.get("capture_hotkey", "f8"))
        ctk.CTkEntry(cap, textvariable=self.cap_hotkey_var, width=120).grid(
            row=3, column=1, padx=4, pady=4, sticky="w"
        )
        ctk.CTkButton(cap, text="ใช้ Hotkey นี้", width=140, command=self._on_apply_hotkey).grid(
            row=3, column=2, padx=4, pady=4, sticky="w"
        )
        self.cap_all_screens_var = tk.BooleanVar(value=self.cfg.get("capture_all_screens", False))
        ctk.CTkCheckBox(
            cap, text="ทุกจอ", variable=self.cap_all_screens_var, command=self._persist
        ).grid(row=3, column=3, padx=(4, 14), pady=4, sticky="w")

        action_row = ctk.CTkFrame(cap, fg_color="transparent")
        action_row.grid(row=4, column=0, columnspan=4, padx=10, pady=(4, 12), sticky="we")
        action_row.grid_columnconfigure(0, weight=1)

        self.cap_status = ctk.CTkLabel(action_row, text="พร้อม · 0 หน้า", anchor="w")
        self.cap_status.grid(row=0, column=0, padx=8, sticky="w")

        ctk.CTkButton(
            action_row, text="📂 เปิดโฟลเดอร์", width=130, command=self._on_open_capture_folder
        ).grid(row=0, column=1, padx=4)
        ctk.CTkButton(
            action_row, text="ตอนถัดไป ▶", width=130, command=self._on_next_chapter
        ).grid(row=0, column=2, padx=4)
        ctk.CTkButton(
            action_row, text="📸  แคปหน้านี้", width=170, height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#06a", hover_color="#048", command=self._on_capture,
        ).grid(row=0, column=3, padx=(4, 8))

        # Log
        log_frame = ctk.CTkFrame(body)
        log_frame.pack(fill="both", expand=True, padx=10, pady=10)
        ctk.CTkLabel(log_frame, text="บันทึกการทำงาน").pack(anchor="w", padx=10, pady=(6, 0))
        self.log = tk.Text(
            log_frame, bg="#111", fg="#cfc", insertbackground="#cfc",
            relief="flat", height=12, font=("Consolas", 10),
        )
        self.log.pack(fill="both", expand=True, padx=10, pady=8)
        self.log.configure(state="disabled")

    # ---------- actions ----------
    def _current_cfg(self) -> UxPlayConfig:
        return UxPlayConfig(
            name=self.cfg["name"],
            fps=int(self.fps_var.get()),
            codec=self.codec_var.get(),
            resolution=self._resolution_value(),
            audio=bool(self.audio_var.get()),
            fullscreen=bool(self.fs_var.get()),
            low_latency=bool(self.low_lat_var.get()),
        )

    def _persist(self) -> None:
        c = self._current_cfg()
        self.cfg.update({
            "name": c.name, "fps": c.fps, "codec": c.codec, "resolution": c.resolution,
            "audio": c.audio, "fullscreen": c.fullscreen, "low_latency": c.low_latency,
            "capture_base": self.cap_base_var.get(),
            "capture_series": self.cap_series_var.get(),
            "capture_chapter": self.cap_chapter_var.get(),
            "capture_hotkey": self.cap_hotkey_var.get(),
            "capture_all_screens": bool(self.cap_all_screens_var.get()),
            "ask_on_start": bool(self.ask_start_var.get()),
        })
        save_config(self.cfg)

    def _apply_quality(self, resolution: str, fps: int) -> None:
        """Push a resolution/FPS choice into the main-window controls."""
        w, h = parse_resolution(resolution, self.codec_var.get())
        self.res_var.set(f"{w}x{h}")
        self.fps_var.set(int(fps))
        self.fps_menu.set(str(int(fps)))
        self._update_display_hint()

    def _ensure_codec_fits_resolution(self) -> None:
        if self.codec_var.get() == "h264" and needs_hevc(self.res_var.get()):
            self.codec_var.set("hevc")
            self._log_line("[setup] ความละเอียดเกิน 1080p ต้องใช้ HEVC — สลับ codec เป็น hevc ให้อัตโนมัติ")

    def _resolution_value(self) -> str:
        w, h = parse_resolution(self.res_var.get(), self.codec_var.get())
        return f"{w}x{h}"

    def _on_fps_change(self, value: str) -> None:
        self.fps_var.set(int(value))
        self._update_display_hint()

    def _on_codec_change(self, codec: str) -> None:
        # h264 mirroring tops out at 1080p; HEVC is what unlocks 4K.
        _, h = parse_resolution(self.res_var.get(), codec)
        if codec == "h264" and h > 1080:
            self.res_var.set(DEFAULT_RESOLUTION["h264"])
        elif codec == "hevc" and self.res_var.get() == DEFAULT_RESOLUTION["h264"]:
            self.res_var.set(DEFAULT_RESOLUTION["hevc"])

    def _update_display_hint(self) -> None:
        mode = primary_display_mode()
        if mode is None:
            self.display_label.configure(text="")
            return
        w, h, hz = mode
        fps = int(self.fps_var.get())
        text = f"จอหลัก: {w}x{h} @ {hz}Hz"
        color = "#9a9"
        if hz and fps > hz:
            text += f"  —  จอนี้แสดงได้สูงสุด {hz} fps (iPhone ส่ง {fps} ได้ แต่จอจะโชว์ไม่ครบทุกเฟรม)"
            color = "#db8"
        self.display_label.configure(text=text, text_color=color)

    # ---------- capture ----------
    def _ensure_capturer(self) -> WebtoonCapture:
        base = self.cap_base_var.get().strip() or DEFAULT_CAPTURE_BASE
        series = self.cap_series_var.get().strip() or "untitled"
        chapter = self.cap_chapter_var.get().strip() or "01"
        all_screens = bool(self.cap_all_screens_var.get())
        if self._capturer is None:
            self._capturer = WebtoonCapture(base, series, chapter, all_screens=all_screens)
        else:
            self._capturer.update(base_dir=base, series=series, chapter=chapter)
            self._capturer.all_screens = all_screens
        return self._capturer

    def _update_cap_status(self, prefix: str = "พร้อม") -> None:
        cap = self._ensure_capturer()
        self.cap_status.configure(
            text=f"{prefix} · ตอน '{cap.chapter}' · {cap.counter} หน้า"
        )

    def _on_capture(self) -> None:
        try:
            cap = self._ensure_capturer()
            path = cap.capture()
            self._log_line(f"[capture] {path}")
            self.cap_status.configure(
                text=f"บันทึก {cap.counter} หน้า · ตอน '{cap.chapter}' · ล่าสุด {path.name}"
            )
            self._persist()
        except Exception as e:
            self._log_line(f"[capture error] {type(e).__name__}: {e}")

    def _on_next_chapter(self) -> None:
        cur = self.cap_chapter_var.get().strip()
        nxt = next_chapter_label(cur)
        self.cap_chapter_var.set(nxt)
        self._update_cap_status("เริ่มตอนใหม่")
        self._log_line(f"[capture] ขึ้นตอนใหม่: '{nxt}'")
        self._persist()

    def _on_pick_capture_base(self) -> None:
        initial = self.cap_base_var.get().strip() or str(ROOT)
        picked = filedialog.askdirectory(title="เลือกโฟลเดอร์เก็บภาพ", initialdir=initial)
        if not picked:
            return
        self.cap_base_var.set(picked)
        self._update_cap_status()
        self._persist()

    def _on_open_capture_folder(self) -> None:
        cap = self._ensure_capturer()
        cap.output_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(cap.output_dir))
        except Exception as e:
            self._log_line(f"[capture] เปิดโฟลเดอร์ไม่ได้: {e}")

    # ---------- hotkey ----------
    def _setup_hotkey(self) -> None:
        if _kb is None:
            self._log_line(
                "[capture] โมดูล 'keyboard' ไม่ได้ติดตั้ง — hotkey ปิด "
                "(ใช้ปุ่มแคปได้ปกติ ติดตั้งเพิ่มด้วย: pip install keyboard)"
            )
            return
        self._unregister_hotkey()
        hk = self.cap_hotkey_var.get().strip().lower()
        if not hk:
            return
        try:
            self._hotkey_handle = _kb.add_hotkey(hk, self._hotkey_capture)
            self._registered_hotkey = hk
            self._log_line(f"[capture] hotkey '{hk}' พร้อมใช้งาน — กดที่ไหนก็ได้เพื่อแคปหน้า")
        except Exception as e:
            self._hotkey_handle = None
            self._registered_hotkey = None
            self._log_line(f"[capture] ตั้ง hotkey '{hk}' ไม่ได้: {e}")

    def _unregister_hotkey(self) -> None:
        if _kb is None or self._hotkey_handle is None:
            return
        try:
            _kb.remove_hotkey(self._hotkey_handle)
        except Exception:
            pass
        self._hotkey_handle = None
        self._registered_hotkey = None

    def _hotkey_capture(self) -> None:
        # `keyboard` callbacks fire on a background thread — bounce to the tk main thread.
        self.after(0, self._on_capture)

    def _on_apply_hotkey(self) -> None:
        self._setup_hotkey()
        self._persist()

    def _on_start(self) -> None:
        try:
            bin_path = find_uxplay(self.cfg.get("uxplay_path") or None)
            if bin_path is None:
                messagebox.showwarning("ไม่พบ UxPlay", build_instructions())
                return
            if self.ask_start_var.get():
                dlg = StartDialog(
                    self, self._resolution_value(), int(self.fps_var.get()), ask_on_start=True
                )
                self.wait_window(dlg)
                if dlg.result is None:
                    return
                self._apply_quality(dlg.result["resolution"], dlg.result["fps"])
                self.ask_start_var.set(dlg.result["ask_on_start"])
            self._ensure_codec_fits_resolution()
            if not bonjour_running():
                self._log_line("[warn] Bonjour ไม่ทำงาน — กำลังพยายาม start...")
                if not try_start_bonjour():
                    messagebox.showwarning(
                        "Bonjour ไม่ทำงาน",
                        "Apple Bonjour Service จำเป็นสำหรับให้ iPhone ค้นเจอเครื่องนี้\n"
                        "ติดตั้งจาก: https://support.apple.com/kb/dl999",
                    )
            self.manager = UxPlayManager(bin_path, self.log_queue)
            self.manager.start(self._current_cfg())
            self._restart_count = 0
            self._persist()
            self.start_btn.configure(state="disabled")
            self.stop_btn.configure(state="normal")
            self.status_dot.configure(text="●  พร้อมรับ AirPlay", text_color="#3c3")
        except Exception as e:
            self._log_line(f"[error] {e}\n{traceback.format_exc()}")
            messagebox.showerror("ผิดพลาด", str(e))

    def _on_stop(self) -> None:
        try:
            if self.manager:
                self.manager.stop()
        except Exception as e:
            self._log_line(f"[error] stop: {type(e).__name__}: {e}\n{traceback.format_exc()}")
        finally:
            self.manager = None
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
            self.status_dot.configure(text="●  หยุด", text_color="#888")

    def _on_browse(self) -> None:
        picked = filedialog.askopenfilename(
            title="เลือกไฟล์ uxplay.exe",
            filetypes=[("UxPlay executable", "uxplay.exe UxPlay.exe"), ("All files", "*.*")],
        )
        if not picked:
            return
        self.cfg["uxplay_path"] = picked
        save_config(self.cfg)
        self._log_line(f"[setup] เลือก UxPlay: {picked}")
        messagebox.showinfo("บันทึกแล้ว", f"ใช้ไฟล์: {picked}")

    def _on_build(self) -> None:
        if not BUILD_SCRIPT.exists():
            messagebox.showerror("ไม่พบสคริปต์", str(BUILD_SCRIPT))
            return
        if not messagebox.askyesno(
            "Build UxPlay",
            "เปิด PowerShell เพื่อ build UxPlay ด้วย MSYS2?\n"
            "ต้องติดตั้ง MSYS2 ก่อน (https://www.msys2.org/)\n"
            "ครั้งแรกใช้เวลา 10-30 นาที",
        ):
            return
        try:
            subprocess.Popen(
                ["powershell", "-NoExit", "-ExecutionPolicy", "Bypass",
                 "-File", str(BUILD_SCRIPT)],
                cwd=str(ROOT),
            )
            self._log_line("[build] เปิด PowerShell แล้ว — รอจน build เสร็จแล้วกลับมากด ▶")
        except Exception as e:
            messagebox.showerror("เปิด PowerShell ไม่ได้", str(e))

    # ---------- background loops ----------
    def _refresh_status(self) -> None:
        ip = get_lan_ip()
        self.ip_label.configure(text=f"LAN IP: {ip}    (iPhone ต้องอยู่วง Wi-Fi เดียวกัน)")
        if bonjour_running():
            self.bonjour_label.configure(text="Bonjour: ทำงานปกติ ✔", text_color="#6c6")
        else:
            self.bonjour_label.configure(
                text="Bonjour: ไม่ทำงาน — iPhone จะมองไม่เห็นเครื่องนี้", text_color="#e84"
            )

    def _drain_logs(self) -> None:
        try:
            while True:
                line = self.log_queue.get_nowait()
                self._append_log(line)
        except queue.Empty:
            pass
        self.after(150, self._drain_logs)

    def _tick(self) -> None:
        if self.manager and self.manager.is_running():
            fps = self.manager.last_fps
            extra = f"  ·  {fps:.0f} fps" if fps else ""
            self.status_dot.configure(text=f"●  พร้อมรับ AirPlay{extra}", text_color="#3c3")
        elif self.manager and self.manager.exited_on_its_own():
            self._handle_unexpected_exit()
        self._refresh_status()
        self._update_display_hint()
        self.after(1500, self._tick)

    def _handle_unexpected_exit(self) -> None:
        mgr = self.manager
        assert mgr is not None
        code, uptime = mgr.returncode, mgr.uptime()
        if uptime >= AUTO_RESTART_MIN_UPTIME and self._restart_count < MAX_AUTO_RESTARTS:
            self._restart_count += 1
            self._log_line(
                f"[manager] UxPlay หยุดเอง (exit {code}) หลังทำงาน {uptime:.0f}s — "
                f"เริ่มใหม่อัตโนมัติ (ครั้งที่ {self._restart_count}/{MAX_AUTO_RESTARTS})"
            )
            try:
                mgr.proc = None
                mgr.start(self._current_cfg())
                return
            except Exception as e:
                self._log_line(f"[error] restart: {type(e).__name__}: {e}")
        else:
            self._log_line(
                f"[manager] UxPlay หยุดทำงาน (exit {code}) — ดู log ด้านบน แล้วกด ▶ เพื่อเริ่มใหม่"
            )
        self._on_stop()

    def _log_line(self, line: str) -> None:
        self.log_queue.put(str(line))

    def _append_log(self, line: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", line + "\n")
        self.log.see("end")
        # cap log size
        if int(self.log.index("end-1c").split(".")[0]) > 800:
            self.log.delete("1.0", "200.0")
        self.log.configure(state="disabled")

    def _on_close(self) -> None:
        try:
            self._unregister_hotkey()
            if self.manager:
                self.manager.stop()
        finally:
            self.destroy()


def main() -> int:
    try:
        app = App()
        app.mainloop()
        return 0
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
