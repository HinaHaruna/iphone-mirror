# iPhone Mirror — รับภาพ AirPlay จาก iPhone บน Windows

[English](README.md)

โปรแกรม GUI สำหรับรับภาพ **AirPlay screen mirroring** จาก iPhone / iPad มาแสดงบน Windows ผ่าน LAN เดียวกัน
ใช้ [UxPlay](https://github.com/FDH2/UxPlay) (โอเพ่นซอร์ส) เป็น backend และตั้งค่าไว้ให้ได้ **ภาพ เฟรมเรต และเสียงสูงสุด** เท่าที่โปรโตคอลจะส่งมาได้

## คุณสมบัติ

- **ภาพสูงสุด 4K HEVC** (3840×2160) ส่วน H.264 ถูก AirPlay จำกัดไว้ที่ 1080p
- **สูงสุด 120 fps** สำหรับ iPhone/iPad ที่จอเป็น ProMotion แอปแจ้ง refresh rate ไปให้ตรงกับที่เลือกด้วย iPhone จะได้ไม่ลดเหลือ 60 fps เอง
- **GPU zero-copy** ถอดรหัสด้วย Direct3D 11 แล้วส่งภาพต่อไปที่จอโดยตรง ไม่ผ่าน CPU แม้ที่ 4K120
- **เสียง low-latency** ผ่าน WASAPI2 เล่นเสียง AAC-ELD ที่ได้จาก AirPlay แบบไม่สูญเสีย
- **เลือกความละเอียด / FPS ทุกครั้งที่กดเริ่ม** หรือจะปิดไม่ให้ถามก็ได้
- **เสถียร** ถ้า UxPlay หลุดกลางทางจะรีสตาร์ทให้อัตโนมัติ เริ่มทำงานในไม่ถึง 1 วินาทีเพราะมี plugin cache และรันด้วย priority สูงเพื่อให้เฟรมสม่ำเสมอ
- **ใช้ใน LAN เท่านั้น** ไม่มีข้อมูลออกอินเทอร์เน็ต
- **แคปหน้าจอ** ด้วย hotkey (ค่าเริ่มต้น `F8`) บันทึกเป็น PNG เรียงเลขให้อัตโนมัติ แยกโฟลเดอร์ตามชื่อเรื่องและตอน

---

## ติดตั้งครั้งแรก

1. **Python 3.10+** จาก https://www.python.org/downloads/ ตอนติดตั้งให้ติ๊ก ✅ *Add Python to PATH*
2. **Apple Bonjour** (จำเป็น) iPhone ใช้ Bonjour หาเครื่องรับ ถ้ามี iTunes อยู่แล้วก็มี Bonjour แล้ว ถ้ายังไม่มีให้ติดตั้งจาก https://support.apple.com/kb/dl999
3. **UxPlay** ต้องมีไฟล์ `bin\uxplay.exe` พร้อม DLL ทำได้ 2 ทาง
   - ถ้ามีไฟล์ zip ในหน้า Releases ให้แตกไฟล์ลงโฟลเดอร์ `bin\`
   - หรือ build เองด้วย MSYS2 ตามขั้นตอนใน [BUILD_WINDOWS.md](BUILD_WINDOWS.md) ครั้งแรกใช้เวลา 10–30 นาที
4. ดับเบิลคลิก **`run.bat`** ระบบจะสร้าง venv ติดตั้ง dependency แล้วเปิด GUI ให้เอง

## วิธีใช้งาน

1. คอมกับ iPhone ต้องต่อ **Wi-Fi วงเดียวกัน**
2. กด **▶ เริ่มรับสัญญาณ AirPlay** แล้วเลือกความละเอียดกับ FPS
3. ที่ iPhone ปัดเปิด Control Center → **Screen Mirroring** → เลือก `Windows AirPlay`
4. ครั้งแรก Windows จะถามเรื่อง Firewall ให้อนุญาต `uxplay.exe` บน **Private network**
5. กด **Alt+Enter** ที่หน้าต่างภาพเพื่อสลับเข้า/ออกจากโหมดเต็มจอ

### ตั้งค่าให้ได้ภาพดีที่สุด

| Setting | ค่าที่ดีที่สุด | หมายเหตุ |
| --- | --- | --- |
| ความละเอียด | **3840×2160** | ต้องใช้ HEVC iPhone จะย่อภาพให้พอดีกรอบนี้ ความสูงเป็นตัวกำหนดขนาด |
| FPS | **120** | ส่งเกิน 60 ได้เฉพาะ iPhone Pro / iPad Pro ที่มี ProMotion และ**จอคอมต้อง ≥120Hz** ถึงจะเห็นครบ ถ้าจอไม่ถึง แอปจะขึ้นเตือน |
| Codec | **hevc** | ยังรับ iPhone ที่ส่ง H.264 ได้อัตโนมัติ เลือก `h264` เฉพาะกับเครื่องเก่ามาก |
| Low-latency | เปิดตอนเล่นเกม ปิดตอนดูวิดีโอ | ปิดไว้ภาพกับเสียงจะซิงก์ตาม timestamp ถ้าเปิด ภาพและเสียงจะแสดงทันทีที่มาถึง |
| เครือข่าย | 5GHz / Wi-Fi 6 และคอมต่อสาย LAN | 4K120 ใช้แบนด์วิดธ์เยอะ ถ้าใช้ 2.4GHz ภาพจะกระตุก |

**เรื่องเสียง:** AirPlay screen mirroring ส่งเสียงเป็น AAC-ELD 44.1kHz stereo เสมอ ฝั่งรับถอดรหัสได้ครบไม่สูญเสียอะไรอยู่แล้ว ไม่มีค่าไหนตั้งให้สูงกว่านี้ได้ ส่วน AirPlay แบบเสียงอย่างเดียว (เปิดเพลง) จะเป็น ALAC lossless ซึ่ง UxPlay รองรับด้วย

---

## ปัญหาที่พบบ่อย

**iPhone มองไม่เห็นเครื่องนี้**
- ดูใน GUI ว่าขึ้น `Bonjour: ทำงานปกติ ✔` หรือเปล่า
- อนุญาต `uxplay.exe` ใน Windows Firewall บน Private network และตั้งโปรไฟล์ Wi-Fi เป็น *Private* (ไม่ใช่ Public)
- ทั้งสองเครื่องต้องอยู่ SSID เดียวกัน Guest network หรือเราเตอร์ที่เปิด AP isolation จะบล็อกการค้นหา

**ภาพกระตุก / FPS ต่ำ**
- ใช้ 5GHz / Wi-Fi 6 เข้าใกล้เราเตอร์ หรือให้คอมต่อสาย LAN
- ลองลดเป็น 2560×1440 หรือ 1920×1080

**`uxplay.exe` หา DLL ไม่เจอ**
- รัน `build_uxplay.ps1 -SkipBuild` เพื่อ copy DLL และ plugin ทั้งหมดลง `bin\` ใหม่

**อัปเดต `bin\` แล้ว plugin หายไป**
- ลบไฟล์ `bin\gst-registry.bin` ทิ้ง ครั้งถัดไปที่เปิด ระบบจะสร้างใหม่ให้ (ช้าราว 5 วินาทีแค่ครั้งเดียว)

---

## โครงสร้างไฟล์

```
app.py              GUI หลัก (customtkinter)
start_dialog.py     หน้าต่างเลือกความละเอียด / FPS ตอนกดเริ่ม
uxplay_manager.py   สร้างคำสั่ง UxPlay + รัน + อ่าน log
display_utils.py    อ่านความละเอียด / refresh rate ของจอ
network_utils.py    LAN IP + เช็ก Bonjour
setup_uxplay.py     ค้นหา uxplay.exe
capture.py          แคปหน้าจอเป็น PNG เรียงเลข
build_uxplay.ps1    build UxPlay ผ่าน MSYS2 แล้วรวมไฟล์ลง bin\
run.bat             ตัวเปิดโปรแกรมแบบดับเบิลคลิก
```

## License และเครดิต

[GPL-3.0](LICENSE) (license เดียวกับ UxPlay)

- **UxPlay**: https://github.com/FDH2/UxPlay (GPL-3.0) เป็นตัวทำงานฝั่ง AirPlay ทั้งหมด
- **GStreamer**: https://gstreamer.freedesktop.org/ (LGPL)
- **CustomTkinter**, **Pillow**, **keyboard**: Python dependency

AirPlay, iPhone, iPad และ Bonjour เป็นเครื่องหมายการค้าของ Apple Inc. โปรเจกต์นี้ไม่มีส่วนเกี่ยวข้องและไม่ได้รับการรับรองจาก Apple
