"""Wrap the UxPlay binary as a managed subprocess with a log queue and FPS parser."""
from __future__ import annotations

import os
import queue
import re
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

FPS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*fps", re.IGNORECASE)
RES_RE = re.compile(r"^\s*(\d{3,4})\s*[xX×]\s*(\d{3,4})\s*$")

# Largest resolution each codec can stream over AirPlay mirroring.
# h264 tops out at 1080p; h265 (HEVC) goes up to 4K.
DEFAULT_RESOLUTION = {"hevc": "3840x2160", "h264": "1920x1080"}
RESOLUTION_PRESETS = ["3840x2160", "2560x1440", "1920x1080", "1280x720"]
FPS_CHOICES = [30, 60, 90, 120]


def needs_hevc(resolution: str) -> bool:
    """AirPlay h264 mirroring stops at 1080p — anything taller needs HEVC."""
    _, h = parse_resolution(resolution)
    return h > 1080
MAX_FPS = 255  # UxPlay limit for both -fps and the @refresh part of -s


def parse_resolution(value: str | None, codec: str = "hevc") -> tuple[int, int]:
    """'3840x2160' -> (3840, 2160). Falls back to the codec's max resolution."""
    m = RES_RE.match(value or "")
    if m:
        w, h = int(m.group(1)), int(m.group(2))
        if w > 0 and h > 0:
            return w, h
    fallback = DEFAULT_RESOLUTION.get(codec.lower(), DEFAULT_RESOLUTION["hevc"])
    w, h = fallback.split("x")
    return int(w), int(h)


@dataclass
class UxPlayConfig:
    name: str = "Windows AirPlay"
    fps: int = 120
    codec: str = "hevc"          # "hevc" or "h264"
    resolution: str = "3840x2160"
    audio: bool = True
    fullscreen: bool = False
    low_latency: bool = True
    extra_args: list[str] | None = None


class UxPlayManager:
    def __init__(self, binary_path: Path, log_queue: queue.Queue[str]):
        self.binary_path = Path(binary_path)
        self.log_queue = log_queue
        self.proc: subprocess.Popen | None = None
        self._reader: threading.Thread | None = None
        self._stop = threading.Event()
        self.last_fps: float = 0.0
        self.started_at: float | None = None

    def is_running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def exited_on_its_own(self) -> bool:
        """True if the process was started and then died without stop() being called."""
        return self.proc is not None and self.proc.poll() is not None

    @property
    def returncode(self) -> int | None:
        return None if self.proc is None else self.proc.returncode

    def uptime(self) -> float:
        return 0.0 if self.started_at is None else time.time() - self.started_at

    def _build_env(self) -> dict[str, str]:
        """Force GStreamer to find bundled plugins inside bin/, not MSYS2 prefix."""
        bin_dir = self.binary_path.parent.resolve()
        plugins = bin_dir / "gstreamer-1.0"
        scanner = bin_dir / "gst-helpers" / "gst-plugin-scanner.exe"
        registry = bin_dir / "gst-registry.bin"
        env = {**os.environ}
        if plugins.is_dir():
            env["GST_PLUGIN_PATH"] = str(plugins)
            env["GST_PLUGIN_PATH_1_0"] = str(plugins)
            env["GST_PLUGIN_SYSTEM_PATH"] = str(plugins)
            env["GST_PLUGIN_SYSTEM_PATH_1_0"] = str(plugins)
            env["GST_REGISTRY"] = str(registry)
            env["GST_REGISTRY_1_0"] = str(registry)
        if scanner.exists():
            env["GST_PLUGIN_SCANNER"] = str(scanner)
            env["GST_PLUGIN_SCANNER_1_0"] = str(scanner)
        # prepend bin/ to PATH so dnssd.dll and friends resolve
        env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
        env.setdefault("GST_DEBUG", "2")
        return env

    def build_args(self, cfg: UxPlayConfig) -> list[str]:
        codec = cfg.codec.lower()
        hevc = codec == "hevc"
        fps = max(1, min(int(cfg.fps), MAX_FPS))
        width, height = parse_resolution(cfg.resolution, codec)

        args: list[str] = [str(self.binary_path), "-n", cfg.name]

        # Resolution + refresh rate + max fps sent to the iPhone.
        # The "@fps" part matters: without it UxPlay advertises refreshRate=60,
        # and the iPhone caps the stream at 60 fps no matter what -fps says.
        args += ["-s", f"{width}x{height}@{fps}", "-fps", str(fps)]

        # Codec + D3D11 hardware decoder. Decoded frames stay in GPU memory
        # (D3D11Memory) all the way to the sink — no CPU copy, even at 4K120.
        if hevc:
            args += ["-h265", "-vd", "d3d11h265dec"]
        else:
            args += ["-vd", "d3d11h264dec"]

        # Pass the sink with NO extra options: UxPlay only wires up -fs and the
        # Alt+Enter fullscreen toggle when the d3d11videosink option string is empty.
        args += ["-vs", "d3d11videosink"]

        if cfg.low_latency:
            # Present frames/audio as soon as they arrive instead of waiting on timestamps.
            args += ["-vsync", "no"]

        if cfg.audio:
            # WASAPI2 is the modern Windows audio path (what autoaudiosink picks anyway);
            # naming it lets us turn on its low-latency buffer mode.
            sink = "wasapi2sink low-latency=true" if cfg.low_latency else "wasapi2sink"
            args += ["-as", sink]
        else:
            args += ["-as", "0"]

        if cfg.fullscreen:
            args += ["-fs"]
        if cfg.extra_args:
            args += cfg.extra_args
        return args

    def start(self, cfg: UxPlayConfig) -> None:
        if self.is_running():
            return
        if not self.binary_path.exists():
            raise FileNotFoundError(f"ไม่พบ UxPlay ที่: {self.binary_path}")
        # Keep bin/gst-registry.bin between runs: GStreamer re-scans only plugins whose
        # files changed, so startup drops from ~5 s (full rescan) to under 1 s.
        # Delete that file by hand if plugins ever seem to go missing.
        args = self.build_args(cfg)
        self._stop.clear()
        self.last_fps = 0.0
        creationflags = 0
        if os.name == "nt":
            # No console window + high CPU priority so frame pacing stays steady at 120 fps
            # even when the PC is busy. Decoding runs on the GPU, so this costs very little.
            creationflags = subprocess.CREATE_NO_WINDOW | subprocess.HIGH_PRIORITY_CLASS
        self.proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",   # a bad byte must never kill the log reader (pipe would fill and stall UxPlay)
            bufsize=1,
            cwd=str(self.binary_path.parent),
            creationflags=creationflags,
            env=self._build_env(),
        )
        self.started_at = time.time()
        self._reader = threading.Thread(target=self._pump_logs, args=(self.proc,), daemon=True)
        self._reader.start()
        self.log_queue.put(f"[manager] started: {' '.join(args)}")

    def stop(self, timeout: float = 5.0) -> None:
        proc = self.proc
        self.proc = None
        self.started_at = None
        self._stop.set()
        if proc is None or proc.poll() is not None:
            self.log_queue.put("[manager] stopped")
            return
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True, timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            else:
                proc.terminate()
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)
        except Exception as e:
            self.log_queue.put(f"[manager] stop warning: {type(e).__name__}: {e}")
        finally:
            self.log_queue.put("[manager] stopped")

    def _pump_logs(self, proc: subprocess.Popen) -> None:
        assert proc.stdout is not None
        try:
            for line in proc.stdout:
                if self._stop.is_set():
                    break
                line = line.rstrip()
                if not line:
                    continue
                m = FPS_RE.search(line)
                if m:
                    try:
                        self.last_fps = float(m.group(1))
                    except ValueError:
                        pass
                self.log_queue.put(line)
        except (OSError, ValueError) as e:
            self.log_queue.put(f"[manager] log reader error: {type(e).__name__}: {e}")
        self.log_queue.put("[manager] log stream ended")
