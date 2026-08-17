# วิธีใช้งาน Facebook Comment Monitor

คู่มือการใช้งานฉบับภาษาไทย

## สารบัญ

1. [การติดตั้ง](#การติดตั้ง)
2. [การใช้งานครั้งแรก](#การใช้งานครั้งแรก)
3. [การใช้งานประจำวัน](#การใช้งานประจำวัน)
4. [การตั้งค่า](#การตั้งค่า)
5. [การแก้ปัญหา](#การแก้ปัญหา)

## การติดตั้ง

### ความต้องการของระบบ

- Python 3.12 หรือสูงกว่า
- Windows 10/11, Linux, หรือ macOS
- อินเทอร์เน็ต
- บัญชี Facebook

### ขั้นตอนการติดตั้ง

#### Windows

1. **ติดตั้ง Python**
   - ดาวน์โหลดจาก https://www.python.org/downloads/
   - เลือก "Add Python to PATH" ตอนติดตั้ง

2. **รันไฟล์ติดตั้ง**
   ```
   คลิกขวาที่ install.bat
   เลือก "Run as administrator"
   ```

3. **รอการติดตั้งเสร็จสิ้น**
   - โปรแกรมจะติดตั้ง dependencies อัตโนมัติ
   - ติดตั้งเบราว์เซอร์สำหรับ Playwright
   - สร้างไฟล์ config.yaml

#### Linux/Mac

1. **เปิด Terminal**

2. **รันสคริปต์ติดตั้ง**
   ```bash
   chmod +x install.sh
   ./install.sh
   ```

3. **รอการติดตั้งเสร็จสิ้น**

## การใช้งานครั้งแรก

### 1. เปิดโปรแกรม

**Windows:**
```
คลิก 2 ครั้งที่ run.bat
```

**Linux/Mac:**
```bash
./run.sh
```

หรือ
```bash
python -m app.main
```

### 2. Login Facebook

1. **หน้าต่างเบราว์เซอร์จะเปิดขึ้น**
   ```
   ℹ️  Info: Please login in the browser window...
   ```

2. **ล็อกอินเข้า Facebook**
   - ใส่อีเมล/เบอร์โทร
   - ใส่รหัสผ่าน
   - ผ่านการยืนยันตัวตน (ถ้ามี)

3. **รอจนล็อกอินสำเร็จ**
   ```
   ✅ Success: Login successful
   ✅ Success: Session saved
   ```

4. **Session จะถูกบันทึก**
   - ไฟล์: `session/fb_session.json`
   - ไม่ต้องล็อกอินใหม่ในครั้งต่อไป

### 3. ตั้งค่า URL ของโพสต์

เปิดไฟล์ `config.yaml` และแก้ไข URL ของโพสต์ที่ต้องการติดตาม:

```yaml
target:
  post_url: "https://www.facebook.com/groups/123456789/posts/987654321/"
```

**ตัวอย่าง URL ที่ใช้ได้:**
```
https://www.facebook.com/groups/123456789/posts/987654321
https://www.facebook.com/groups/groupname/posts/123456789
https://www.facebook.com/groups/123456789/permalink/987654321
```

### 4. เริ่มการติดตาม

รันโปรแกรมอีกครั้ง โปรแกรมจะเริ่มแสดงคอมเมนต์แบบเรียลไทม์อัตโนมัติ

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
🕒 09:30:21 (5 วินาที ที่แล้ว)
└─ สนใจครับ

   [T2][NEW]
   Admin
   🕒 09:30:33 (2 นาที ที่แล้ว)
   └─ ทัก inbox ได้เลยครับ
```

## การใช้งานประจำวัน

### 1. ตั้งค่า URL ในไฟล์ config

เปิดไฟล์ `config.yaml` และแก้ไข URL ของโพสต์:

```yaml
target:
  post_url: "https://www.facebook.com/groups/YOUR_GROUP_ID/posts/YOUR_POST_ID/"
```

### 2. เปิดโปรแกรม

**Windows:** คลิก `run.bat`

**Linux/Mac:** `./run.sh`

### 3. ติดตามคอมเมนต์

- โปรแกรมจะอ่าน URL จาก config อัตโนมัติ
- อัปเดทคอมเมนต์ทุก 0.5 วินาที
- แสดงคอมเมนต์ใหม่ด้วยป้าย [NEW]
- แสดงสีตาม Tier

### 4. หยุดการติดตาม

กด `Ctrl+C` เพื่อหยุด

## การตั้งค่า

### แก้ไขไฟล์ config.yaml

```yaml
# URL ของโพสต์ที่ต้องการติดตาม
target:
  post_url: "https://www.facebook.com/groups/123456789/posts/987654321/"

# ความเร็วในการรีเฟรช
monitor:
  refresh_interval: 0.5  # วินาที (0.5 = เร็ว, 1.0 = ปานกลาง, 2.0 = ช้า)

# ซ่อนหน้าต่างเบราว์เซอร์
browser:
  headless: false  # true = ซ่อน, false = แสดง

# การแจ้งเตือน
monitor:
  enable_notifications: true  # true = เปิด, false = ปิด

# การแสดงผล
display:
  max_message_length: 200      # ตัดข้อความยาว
  show_relative_time: true     # แสดง "5 นาทีที่แล้ว"
```

## การแก้ปัญหา

### ล็อกอินไม่ได้

**วิธีแก้:**
1. ตรวจสอบอินเทอร์เน็ต
2. ลองปิด VPN
3. ติดตั้ง Playwright ใหม่
   ```bash
   playwright install chromium
   ```

### Session หมดอายุ

**วิธีแก้:**
```bash
# ลบไฟล์ session แล้วล็อกอินใหม่

# Windows
del session\fb_session.json

# Linux/Mac
rm session/fb_session.json
```

### ไม่แสดงคอมเมนต์

**วิธีตรวจสอบ:**
1. ตรวจสอบ URL ว่าถูกต้อง
2. ตรวจสอบว่าโพสต์มีคอมเมนต์
3. รอสักครู่ให้โหลด
4. ดูไฟล์ log: `logs/app.log`

### เข้ากลุ่มส่วนตัวไม่ได้

**สาเหตุ:**
- บัญชีไม่ได้เป็นสมาชิกกลุ่ม

**วิธีแก้:**
- เข้าเป็นสมาชิกกลุ่มก่อน
- ล็อกอินด้วยบัญชีที่ถูกต้อง

### ใช้ CPU สูง

**วิธีแก้:**
เพิ่มเวลารีเฟรชใน `config.yaml`:
```yaml
monitor:
  refresh_interval: 1.0  # ลดความถี่การรีเฟรช
```

## ความหมายของสี

- **เขียว** = Tier 1 (คอมเมนต์หลัก)
- **ฟ้า** = Tier 2 (ตอบกลับครั้งแรก)
- **เหลือง** = Tier 3 (ตอบกลับซ้อน)
- **แดง** = Tier 4+ (ตอบกลับซ้อนหลายชั้น)
- **สีสว่าง** = คอมเมนต์ใหม่

## โครงสร้างการแสดงผล

```
[T1][NEW]           ← ระดับที่ 1 (คอมเมนต์หลัก), ป้าย NEW
สมชาย               ← ชื่อผู้เขียน
🕒 09:30:21 (5วิ)   ← เวลา (เวลาสัมพัทธ์)
└─ สนใจครับ         ← ข้อความ

   [T2]             ← ระดับที่ 2 (ตอบกลับ T1)
   Admin            ← ผู้ตอบกลับ
   🕒 09:30:33 (2น)
   └─ ทัก inbox ได้เลย

      [T3]          ← ระดับที่ 3 (ตอบกลับ T2)
      สมชาย
      🕒 09:31:10
      └─ ขอบคุณครับ
```

## คำสั่งที่ใช้บ่อย

```bash
# เริ่มโปรแกรม
python -m app.main

# ติดตั้ง dependencies ใหม่
pip install -r requirements.txt

# ติดตั้งเบราว์เซอร์ใหม่
playwright install chromium

# ดู logs (Windows PowerShell)
Get-Content logs/app.log -Wait

# ดู logs (Linux/Mac)
tail -f logs/app.log

# ล็อกเอาต์ (ลบ session)
del session\fb_session.json  # Windows
rm session/fb_session.json   # Linux/Mac

# รีเซ็ตฐานข้อมูล
del database\comments.db     # Windows
rm database/comments.db      # Linux/Mac
```

## เคล็ดลับการใช้งาน

### 1. ติดตามหลายโพสต์

หยุดการติดตามปัจจุบัน (Ctrl+C) แล้วเริ่มใหม่ด้วย URL ใหม่

### 2. ประหยัดทรัพยากร

เพิ่มค่า `refresh_interval` เป็น 1 หรือ 2 วินาที

### 3. ซ่อนเบราว์เซอร์

ตั้งค่า `headless: true` ใน config.yaml

### 4. ดูประวัติ

คอมเมนต์ทั้งหมดถูกบันทึกใน `database/comments.db`

### 5. ความปลอดภัย

- อย่าแชร์ไฟล์ `session/fb_session.json` (มี token ล็อกอิน)
- ตั้งรหัสผ่านคอมพิวเตอร์
- ใช้บัญชี Facebook ที่แยกต่างหาก (แนะนำ)

## การอัปเดตโปรแกรม

### ตรวจสอบเวอร์ชันใหม่

ดูที่ `CHANGELOG.md` หรือ GitHub repository

### อัปเดต dependencies

```bash
pip install -r requirements.txt --upgrade
```

### อัปเดตเบราว์เซอร์

```bash
playwright install chromium
```

## การสำรองข้อมูล

### สำรองฐานข้อมูล

```bash
# Windows
copy database\comments.db backup\comments_backup.db

# Linux/Mac
cp database/comments.db backup/comments_backup.db
```

### สำรอง session

```bash
# Windows
copy session\fb_session.json backup\session_backup.json

# Linux/Mac
cp session/fb_session.json backup/session_backup.json
```

## ข้อควรระวัง

### 1. นโยบายของ Facebook

- ใช้งานอย่างมีจริยธรรม
- ไม่ใช้เพื่อสแปม
- เคารพความเป็นส่วนตัว
- ปฏิบัติตามข้อกำหนดการใช้งานของ Facebook

### 2. อัตราการรีเฟรช

- อย่ารีเฟรชบ่อยเกินไป (< 0.5 วินาที)
- อาจถูก Facebook จำกัดอัตรา
- ใช้ค่าเริ่มต้น 0.5 วินาที

### 3. กลุ่มขนาดใหญ่

- กลุ่มที่มีคอมเมนต์มาก (10,000+) อาจช้า
- การโหลดครั้งแรกอาจใช้เวลานาน
- ใช้ทรัพยากรมากขึ้น

## ติดต่อและสอบถาม

### เมื่อเจอปัญหา

1. ตรวจสอบ `logs/app.log`
2. อ่าน README.md
3. ดู QUICKSTART.md
4. ตรวจสอบการตั้งค่าใน config.yaml

### เอกสารเพิ่มเติม

- **README.md**: คู่มือหลักภาษาอังกฤษ
- **QUICKSTART.md**: คู่มือเริ่มต้นใช้งานเร็ว
- **ERROR_HANDLING.md**: วิธีจัดการข้อผิดพลาด
- **SESSION_RECOVERY.md**: การจัดการ session

## ขอบคุณ

ขอบคุณที่ใช้งาน Facebook Comment Monitor!

หวังว่าเครื่องมือนี้จะเป็นประโยชน์ในการติดตามคอมเมนต์

หากมีข้อเสนอแนะ กรุณาติดต่อผ่าน GitHub Issues
