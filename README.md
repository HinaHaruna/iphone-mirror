# iPhone Mirror — AirPlay receiver for Windows

[ภาษาไทย](README.th.md)

A small Windows GUI that turns your PC into an **AirPlay screen-mirroring receiver** for iPhone / iPad on the same LAN.
It drives [UxPlay](https://github.com/FDH2/UxPlay) (the open-source AirPlay server) and is tuned for the
**highest picture quality, frame rate and audio fidelity** the protocol allows.

- **Up to 4K HEVC** (3840×2160). H.264 is limited to 1080p by AirPlay.
- **Up to 120 fps** on ProMotion iPhones/iPads. The app also advertises the matching refresh rate, so the device does not fall back to 60 fps.
- **Zero-copy GPU pipeline.** Direct3D 11 hardware decode → D3D11 video sink. Frames never touch the CPU, even at 4K120.
- **Low-latency audio.** WASAPI2 output plays the AirPlay AAC-ELD stream without loss.
- **Quality picker on start.** Choose resolution + FPS every time you press Start, or turn the prompt off.
- **Stable.** Auto-restarts UxPlay if it crashes mid-session. The plugin cache makes startup under 1 s. UxPlay runs at high CPU priority for steady frame pacing.
- **LAN only.** Nothing goes over the internet.
- **Screen capture.** Save numbered PNGs with a global hotkey (default `F8`), organised by title/chapter.

> This is a GUI wrapper. All AirPlay protocol work is done by UxPlay.
> The interface is currently in Thai. Translations are welcome.

---

## Requirements

| What | Why |
| --- | --- |
| Windows 10/11 64-bit, a GPU with D3D11 video decode (any NVIDIA/AMD/Intel from the last ~8 years) | hardware HEVC/H.264 decoding |
| [Python 3.10+](https://www.python.org/downloads/) (tick *Add Python to PATH*) | runs the GUI |
| [Apple Bonjour](https://support.apple.com/kb/dl999) (comes with iTunes) | lets the iPhone discover the PC |
| `bin\uxplay.exe` + its DLLs | included in the [release zip](https://github.com/HinaHaruna/iphone-mirror/releases/latest), or build it with [`build_uxplay.ps1`](BUILD_WINDOWS.md) |

## Quick start

1. Download **`iPhone-Mirror-…-win64.zip`** from the [latest release](https://github.com/HinaHaruna/iphone-mirror/releases/latest)
   and extract it anywhere. It already includes `bin\uxplay.exe` and every DLL/plugin it needs, so no build is required.
   - Or build UxPlay yourself: install [MSYS2](https://www.msys2.org/) and the Bonjour SDK, then run
     `powershell -ExecutionPolicy Bypass -File .\build_uxplay.ps1`. See [BUILD_WINDOWS.md](BUILD_WINDOWS.md).
2. Double-click **`run.bat`**. It creates a virtualenv, installs `requirements.txt`, and opens the GUI.
3. Press **▶ Start** (`เริ่มรับสัญญาณ AirPlay`), pick resolution + FPS, then on the iPhone open Control Center → **Screen Mirroring** → choose
   `Windows AirPlay`.
4. Allow `uxplay.exe` through Windows Firewall (**Private** networks) the first time Windows asks.

## Getting the best picture

| Setting | Best value | Notes |
| --- | --- | --- |
| Resolution | **3840×2160** | Needs HEVC. The iPhone fits its screen inside this box. Height is the controlling dimension. |
| FPS | **120** | Only ProMotion (Pro) iPhones and iPad Pros send >60. Your monitor must be ≥120 Hz to *show* 120. The app warns you if it is not. |
| Codec | **hevc** | Also accepts H.264 clients automatically. Pick `h264` only for very old devices. |
| Low-latency | on for games, off for video | Off keeps audio/video timestamp sync. On shows each frame and sample as soon as it arrives. |
| Network | 5 GHz / Wi-Fi 6, PC on Ethernet | 4K120 is a lot of data. 2.4 GHz will stutter. |

**About audio:** AirPlay screen mirroring always sends AAC-ELD, 44.1 kHz stereo. The receiver decodes it
without loss. No setting can raise that ceiling. Audio-only AirPlay (music) uses ALAC lossless, and UxPlay handles that too.

Press **Alt+Enter** in the video window to toggle fullscreen.

## Troubleshooting

**The iPhone does not list the PC**
- The GUI must show Bonjour as running (`Bonjour: ทำงานปกติ ✔`).
- Allow `uxplay.exe` in Windows Firewall on **Private** networks. Make sure your Wi-Fi profile is *Private*, not *Public*.
- Both devices must be on the same SSID. Guest networks / AP isolation block discovery.

**Choppy video or low FPS**
- Use 5 GHz / Wi-Fi 6, move closer to the router, put the PC on Ethernet.
- Try 2560×1440 or 1920×1080.

**`uxplay.exe` cannot find a DLL**
- Re-run `build_uxplay.ps1 -SkipBuild` to re-copy all runtime DLLs and plugins into `bin\`.

**A plugin seems missing after updating `bin\`**
- Delete `bin\gst-registry.bin`. It is rebuilt on the next start, which takes about 5 s once.

## Project layout

```
app.py              GUI (customtkinter)
start_dialog.py     resolution / FPS picker shown on Start
uxplay_manager.py   builds the UxPlay command line, runs it, pumps logs
display_utils.py    reads the monitor resolution / refresh rate
network_utils.py    LAN IP + Bonjour service checks
setup_uxplay.py     locates uxplay.exe
capture.py          numbered PNG screen capture
build_uxplay.ps1    builds UxPlay with MSYS2 and bundles it into bin\
run.bat             one-click launcher
```

## License

[GPL-3.0](LICENSE), the same license as UxPlay.

Credits and third-party software:
- **UxPlay**: https://github.com/FDH2/UxPlay (GPL-3.0). Does all the AirPlay work.
- **GStreamer**: https://gstreamer.freedesktop.org/ (LGPL)
- **CustomTkinter**, **Pillow**, **keyboard**: Python dependencies

AirPlay, iPhone, iPad and Bonjour are trademarks of Apple Inc. This project is not affiliated with or endorsed by Apple.
