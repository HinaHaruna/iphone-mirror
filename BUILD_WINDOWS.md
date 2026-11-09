# Build UxPlay บน Windows

UxPlay **ไม่มี Windows binary สำเร็จรูป** ต้อง compile เองผ่าน **MSYS2** สคริปต์ `build_uxplay.ps1` จะทำทุกอย่างให้
รวมถึง copy `uxplay.exe` พร้อม DLL และ GStreamer plugin ที่ต้องใช้ทั้งหมดลง `bin\` หลังจากนั้นจะรันได้โดยไม่ต้องมี MSYS2 อยู่ใน PATH

## สิ่งที่ต้องมี

1. **MSYS2** จาก https://www.msys2.org/ ติดตั้งที่ `C:\msys64` (ค่าเริ่มต้น)
   แล้วเปิด **MSYS2 UCRT64** หนึ่งครั้ง รัน `pacman -Syu` (ถ้าระบบบอกให้ปิด terminal ก็ปิดแล้วเปิดใหม่ รันซ้ำอีกรอบ)
2. **Bonjour SDK for Windows v3.0** (ใช้ตอน compile)
   - ดาวน์โหลดจาก [Apple Developer](https://developer.apple.com/download/all/?q=Bonjour%20SDK%20for%20Windows) (ต้องล็อกอิน Apple ID) โปรแกรมติดตั้งจะลงไว้ที่ `C:\Program Files\Bonjour SDK`
   - หรือ copy โฟลเดอร์ `Include\` กับ `Lib\` ของ SDK มาไว้ที่ `.\bonjour_sdk\` ในโปรเจกต์นี้
   - หรือตั้ง environment variable `BONJOUR_SDK_HOME` ให้ชี้ไปที่ SDK
3. **Apple Bonjour Service** (ใช้ตอนรัน) ติดมากับ iTunes หรือติดตั้งจาก https://support.apple.com/kb/dl999

## Build

คลิกขวาที่ **`build_uxplay.ps1`** แล้วเลือก **Run with PowerShell** หรือรันคำสั่งนี้

```powershell
powershell -ExecutionPolicy Bypass -File .\build_uxplay.ps1
```

สคริปต์จะทำตามลำดับนี้

1. ติดตั้ง toolchain, libplist, OpenSSL และ GStreamer (base/good/bad/ugly/libav) ผ่าน `pacman`
2. clone source ของ UxPlay ลง `build_uxplay\` (ถ้ามีอยู่แล้วจะ `git pull` แทน)
3. build ด้วย CMake + Ninja (Release)
4. copy `uxplay.exe`, GStreamer plugin ทั้งหมด, `gst-plugin-scanner.exe` และ DLL ทุกตัวที่ต้องใช้ (หาด้วย `ldd`) ลง `bin\`

ครั้งแรกใช้เวลา **10–30 นาที** ครั้งต่อไปเหลือไม่กี่นาที

### ตัวเลือก

| ตัวเลือก | ทำอะไร |
| --- | --- |
| `-SkipBuild` | ไม่ build ใหม่ แค่ copy `uxplay.exe` และ runtime ลง `bin\` อีกรอบ (ใช้ตอน DLL หาย) |
| `-OutDir <path>` | รวมไฟล์ไปไว้โฟลเดอร์อื่นแทน `bin\` (เช่นตอนเตรียม zip สำหรับ Release) |

## ตรวจสอบหลัง build

```powershell
.\bin\uxplay.exe -v
```

ถ้าขึ้นเลข version แปลว่าใช้งานได้ ถ้าขึ้น error ว่าหา DLL ไม่เจอ ให้รันสคริปต์อีกครั้งด้วย `-SkipBuild`

## Build เอง (manual)

เปิด terminal **MSYS2 UCRT64**

```bash
pacman -S --needed git \
  mingw-w64-ucrt-x86_64-toolchain mingw-w64-ucrt-x86_64-cmake mingw-w64-ucrt-x86_64-ninja \
  mingw-w64-ucrt-x86_64-pkgconf mingw-w64-ucrt-x86_64-openssl mingw-w64-ucrt-x86_64-libplist \
  mingw-w64-ucrt-x86_64-gstreamer mingw-w64-ucrt-x86_64-gst-plugins-base \
  mingw-w64-ucrt-x86_64-gst-plugins-good mingw-w64-ucrt-x86_64-gst-plugins-bad \
  mingw-w64-ucrt-x86_64-gst-plugins-ugly mingw-w64-ucrt-x86_64-gst-libav

git clone https://github.com/FDH2/UxPlay.git && cd UxPlay
mkdir build && cd build
BONJOUR_SDK_HOME="C:/Program Files/Bonjour SDK" cmake -G Ninja -DCMAKE_BUILD_TYPE=Release ..
ninja
```

เสร็จแล้วใน GUI กดปุ่ม **"เลือกไฟล์ uxplay.exe..."** แล้วชี้ไปที่ `build/uxplay.exe` (ต้องมี `C:\msys64\ucrt64\bin` อยู่ใน PATH)
หรือรัน `build_uxplay.ps1 -SkipBuild` เพื่อรวมไฟล์ลง `bin\`

## คำถามที่พบบ่อย

**Q: ทำไมไม่ใช้ binary ที่คนอื่น build ไว้?**
A: เพราะ UxPlay จัดการทั้งเครือข่ายและการเข้ารหัสภาพ ไม่ควรใช้ binary จากแหล่งที่ไม่รู้ที่มา build จาก source ทางการผ่าน MSYS2 น่าเชื่อถือกว่า

**Q: ใช้ Visual Studio compile ได้ไหม?**
A: ในทางเทคนิคได้ แต่ UxPlay ไม่ได้ทดสอบกับ MSVC และตั้งค่า GStreamer dev libs สำหรับ MSVC ก็ยากกว่า แนะนำ MSYS2 ตามที่ UxPlay แนะนำอย่างเป็นทางการ
