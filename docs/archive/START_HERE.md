# Facebook Comment Monitor

🌟 **สร้างโปรเจกต์สำเร็จ!** 🌟

โปรเจกต์ Facebook Group Comment Monitor พร้อมใช้งานแล้ว

## 📁 โครงสร้างโปรเจกต์

```
fbcommentviewrt/
├── app/                      # โค้ดหลักของแอปพลิเคชัน
│   ├── main.py              # Entry point หลัก
│   ├── models/              # Data models (Comment, PostInfo)
│   ├── scraper/             # Browser automation & parsing
│   ├── monitor/             # Change detection & monitoring
│   ├── renderer/            # CLI display (Rich)
│   └── database/            # SQLite operations
│
├── session/                 # Facebook session storage
├── database/                # SQLite database files
├── logs/                    # Application logs
│
├── config.yaml.example      # ตัวอย่างไฟล์ config
├── requirements.txt         # Python dependencies
│
├── run.py                   # สคริปต์รันโปรแกรม
├── run.bat                  # Windows run script
├── run.sh                   # Linux/Mac run script
├── install.bat              # Windows installer
├── install.sh               # Linux/Mac installer
│
└── เอกสาร (Documentation)
    ├── README.md            # คู่มือหลัก (อังกฤษ)
    ├── README_TH.md         # คู่มือหลัก (ไทย)
    ├── QUICKSTART.md        # คู่มือเริ่มต้นใช้งาน
    ├── BUILD.md             # คู่มือ Build & Deploy
    ├── ERROR_HANDLING.md    # กลยุทธ์จัดการข้อผิดพลาด
    ├── SESSION_RECOVERY.md  # การจัดการ Session
    ├── PROJECT_STRUCTURE.md # โครงสร้างโปรเจกต์
    ├── CONTRIBUTING.md      # แนวทางการมีส่วนร่วม
    ├── CHANGELOG.md         # ประวัติการเปลี่ยนแปลง
    └── LICENSE              # ใบอนุญาต MIT
```

## 🚀 วิธีเริ่มใช้งาน (Quick Start)

### 1️⃣ ติดตั้ง Dependencies

**Windows:**
```bash
install.bat
```

**Linux/Mac:**
```bash
chmod +x install.sh
./install.sh
```

**หรือติดตั้งเอง:**
```bash
pip install -r requirements.txt
playwright install chromium
copy config.yaml.example config.yaml  # Windows
cp config.yaml.example config.yaml    # Linux/Mac
```

### 2️⃣ รันโปรแกรม

**Windows:**
```bash
run.bat
```

**Linux/Mac:**
```bash
./run.sh
```

**หรือ:**
```bash
python -m app.main
```

### 3️⃣ Login Facebook (ครั้งแรกเท่านั้น)

- เบราว์เซอร์จะเปิดขึ้นอัตโนมัติ
- Login เข้า Facebook ตามปกติ
- Session จะถูกบันทึกไว้ที่ `session/fb_session.json`
- ครั้งต่อไปไม่ต้อง Login ใหม่

### 4️⃣ ใส่ URL ของโพสต์

```
Enter Facebook Post URL: https://www.facebook.com/groups/123456/posts/789
```

### 5️⃣ เริ่มติดตามคอมเมนต์!

โปรแกรมจะแสดงคอมเมนต์แบบเรียลไทม์:

```
================================================
Facebook Group Comment Monitor
================================================

Group: ชื่อกลุ่ม
Post URL: https://www.facebook.com/...
Last Refresh: 2026-08-17 10:30:45
Total Comments: 42
Total Replies: 87
Session Status: ✅ Active

================================================

📝 Comments
[T1][NEW]
สมชาย
🕒 09:30:21 (5 sec ago)
└─ สนใจครับ

   [T2][NEW]
   Admin
   🕒 09:30:33 (2 min ago)
   └─ ทัก inbox ได้เลยครับ
```

## ✨ Features (คุณสมบัติ)

- ✅ **Real-time Monitoring** - อัปเดตทุก 0.5 วินาที
- ✅ **Session Management** - Login ครั้งเดียว ใช้ได้ตลอด
- ✅ **Tree View Display** - แสดงโครงสร้างแบบต้นไม้
- ✅ **Color-coded Tiers** - แยกสีตามระดับคอมเมนต์
- ✅ **SQLite Storage** - บันทึกข้อมูลถาวร
- ✅ **Notifications** - แจ้งเตือนคอมเมนต์ใหม่
- ✅ **Public & Private Groups** - รองรับทุกประเภทกลุ่ม
- ✅ **Nested Replies** - ตอบกลับซ้อนไม่จำกัดระดับ
- ✅ **Multi-language** - รองรับไทย/อังกฤษ
- ✅ **Production Ready** - พร้อมใช้งานจริง

## 🎨 Color Legend (ความหมายสี)

- 🟢 **Green (Tier 1)** - คอมเมนต์หลัก
- 🔵 **Cyan (Tier 2)** - ตอบกลับครั้งแรก
- 🟡 **Yellow (Tier 3)** - ตอบกลับซ้อนครั้งที่ 2
- 🔴 **Red (Tier 4+)** - ตอบกลับซ้อนหลายชั้น
- ✨ **Bright Colors** - คอมเมนต์/Reply ใหม่

## ⚙️ Configuration (การตั้งค่า)

แก้ไขไฟล์ `config.yaml`:

```yaml
# ความเร็วรีเฟรช
monitor:
  refresh_interval: 0.5  # วินาที (0.5 = เร็ว, 1.0 = ปกติ, 2.0 = ช้า)

# ซ่อนเบราว์เซอร์
browser:
  headless: false  # true = ซ่อน, false = แสดง

# การแจ้งเตือน
monitor:
  enable_notifications: true  # true = เปิด, false = ปิด

# การแสดงผล
display:
  max_message_length: 200      # ความยาวข้อความสูงสุด
  show_relative_time: true     # แสดงเวลาแบบสัมพัทธ์
```

## 🛠️ Technologies (เทคโนโลยีที่ใช้)

- **Python 3.12+** - ภาษาโปรแกรม
- **Playwright** - Browser automation
- **Rich** - CLI rendering
- **SQLite** - Database
- **AsyncIO** - Async programming
- **BeautifulSoup4** - HTML parsing
- **PyYAML** - Configuration

## 📚 Documentation (เอกสาร)

| ไฟล์ | คำอธิบาย |
|------|----------|
| `README.md` | คู่มือหลัก (English) |
| `README_TH.md` | คู่มือหลัก (ไทย) |
| `QUICKSTART.md` | เริ่มต้นใช้งานเร็ว |
| `BUILD.md` | วิธี Build โปรเจกต์ |
| `ERROR_HANDLING.md` | การจัดการ Error |
| `SESSION_RECOVERY.md` | การจัดการ Session |
| `PROJECT_STRUCTURE.md` | โครงสร้างโปรเจกต์ |
| `CONTRIBUTING.md` | แนวทางการมีส่วนร่วม |
| `CHANGELOG.md` | ประวัติเวอร์ชัน |

## 🐛 Troubleshooting (แก้ปัญหา)

### Session หมดอายุ
```bash
# ลบไฟล์ session แล้ว login ใหม่
del session\fb_session.json  # Windows
rm session/fb_session.json   # Linux/Mac
```

### ติดตั้ง Playwright ใหม่
```bash
playwright install chromium
```

### ดู Logs
```bash
# Windows PowerShell
Get-Content logs/app.log -Wait

# Linux/Mac
tail -f logs/app.log
```

## 🔒 Security (ความปลอดภัย)

- ⚠️ **อย่าแชร์** `session/fb_session.json` (มี token การ login)
- ⚠️ **อย่า commit** ไฟล์ session ลง Git
- ⚠️ **ใช้รหัสผ่าน** ป้องกันเครื่อง
- ✅ ไฟล์สำคัญอยู่ใน `.gitignore` แล้ว

## 📋 Requirements (ความต้องการ)

- Python 3.12 หรือสูงกว่า
- Internet connection
- บัญชี Facebook
- RAM 500 MB+
- Disk space 100 MB+

## 🎯 Use Cases (กรณีการใช้งาน)

- 📊 **Marketing** - ติดตามความสนใจลูกค้า
- 🛒 **E-commerce** - ตอบคำถามลูกค้าเร็วขึ้น
- 👥 **Community Management** - จัดการกลุ่มได้ดีขึ้น
- 📈 **Analytics** - วิเคราะห์พฤติกรรม
- 🔍 **Research** - รวบรวมข้อมูล

## ⚖️ License (ใบอนุญาต)

MIT License - ใช้งานได้อย่างอิสระ

ดูรายละเอียดใน `LICENSE`

## 🤝 Contributing (การมีส่วนร่วม)

ยินดีรับ Pull Requests!

ดูแนวทางใน `CONTRIBUTING.md`

## 📞 Support (การสนับสนุน)

- 📖 อ่านเอกสารใน `README.md` และ `README_TH.md`
- 🔍 ตรวจสอบ `logs/app.log`
- 💬 เปิด Issue บน GitHub
- 📧 ติดต่อผู้พัฒนา

## 🎉 สรุป

โปรเจกต์นี้พร้อมใช้งานแล้ว! มีทุกอย่างที่ต้องการ:

✅ Clean Architecture  
✅ Modular Design  
✅ Production Ready  
✅ Full Documentation  
✅ Error Handling  
✅ Session Management  
✅ Real-time Monitoring  
✅ Beautiful CLI  
✅ Database Storage  
✅ Easy Installation  

**เริ่มใช้งานได้เลย!** 🚀

```bash
python -m app.main
```

---

Made with ❤️ for monitoring Facebook comments efficiently
