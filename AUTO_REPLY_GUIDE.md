# คู่มือการใช้งาน Auto Reply

## ภาพรวม
ฟีเจอร์ Auto Reply จะตรวจจับ comment ใหม่ของ**เจ้าของโพส**และ reply กลับโดยอัตโนมัติทันที

**ความสะดวก**: ระบบจะดึงชื่อเจ้าของโพสจากหน้า Facebook โดยอัตโนมัติ ไม่ต้องกรอกชื่อเอง!

## การตั้งค่า

### 1. แก้ไข `config.yaml`

```yaml
auto_reply:
  enabled: true  # เปิดใช้งาน
  reply_message: "ขอบคุณสำหรับความคิดเห็นครับ"  # ข้อความที่จะตอบกลับ
  reply_tier: 2  # ระดับการ reply (2 = reply ไปที่ T1 comment)
```

**ไม่ต้องกรอก `post_owner_name`** - ระบบจะดึงจากหน้าโพสอัตโนมัติ!

### 2. ตัวอย่างการตั้งค่า

**ตัวอย่างที่ 1: ตอบกลับเจ้าของโพส**
```yaml
auto_reply:
  enabled: true
  reply_message: "ขอบคุณครับ 🙏"
  reply_tier: 2
```

**ตัวอย่างที่ 2: ปิดการใช้งาน**
```yaml
auto_reply:
  enabled: false
  reply_message: ""
  reply_tier: 2
```

## วิธีการทำงาน

1. **โหลดหน้าโพส**: ระบบจะเปิดหน้าโพสและดึงชื่อเจ้าของโพสอัตโนมัติ

2. **ตรวจจับ comment ใหม่**: ระบบจะตรวจจับ comment ใหม่ทุก 300ms (ตาม `monitor.refresh_interval`)

3. **เช็คเงื่อนไข**:
   - `auto_reply.enabled = true`
   - Author ของ comment ตรงกับชื่อเจ้าของโพสที่ดึงมา
   - Comment tier = 1 (T1 comment หลัก)

3. **Reply ทันที**: เมื่อเงื่อนไขตรงทุกข้อ ระบบจะ:
   - หา comment container โดยใช้ comment ID
   - คลิกปุ่ม "ตอบกลับ"
   - พิมพ์ข้อความจาก `reply_message`
   - กด Enter เพื่อส่ง

4. **บันทึก log**: ทุกการ reply จะถูกบันทึกใน `output.log`

## ตรวจสอบ Log

ดู log การ reply:
```powershell
Get-Content output.log -Tail 50 | Select-String "Auto reply"
```

ตัวอย่าง log ที่จะเห็น:
```
2026-08-18 18:55:30,123 - INFO - Auto reply triggered for post owner's comment by Possawee Dechsaradecho
2026-08-18 18:55:30,124 - INFO - Comment ID: 1234567890
2026-08-18 18:55:30,125 - INFO - Comment: Test comment...
2026-08-18 18:55:35,456 - INFO - Reply posted successfully to comment 1234567890
```

## ข้อควรระวัง

1. **ชื่อเจ้าของโพส**: ระบบจะดึงจากหน้า Facebook โดยอัตโนมัติ โดยจับจากโพสหลัก (role="article")

2. **การเทียบชื่อ**: ระบบใช้ `.lower()` เพื่อเทียบชื่อแบบไม่สนใจตัวพิมพ์ใหญ่-เล็ก และใช้ `in` เพื่อเช็คว่าชื่อเจ้าของโพสอยู่ใน author ของ comment

3. **Reply เฉพาะ T1**: ระบบจะ reply เฉพาะ comment หลัก (T1) ไม่ reply nested replies

4. **Reply ครั้งเดียว**: แต่ละ comment ใหม่จะถูก reply เพียงครั้งเดียว

5. **การตรวจจับล้มเหลว**: ถ้าดึงชื่อเจ้าของโพสไม่ได้ ระบบจะแสดง warning และ auto reply จะไม่ทำงาน

6. **รอ browser โหลด**: การ reply อาจใช้เวลา 2-3 วินาที รอ browser ประมวลผล

## การทดสอบ

1. **เปิด config**:
   ```yaml
   auto_reply:
     enabled: true
     reply_message: "TEST_AUTO_REPLY"
     reply_tier: 2
   ```

2. **รัน CLI**:
   ```powershell
   python run.py
   ```
   
   เช็ค log ว่าระบบดึงชื่อเจ้าของโพสได้:
   ```
   INFO - Post author detected: Possawee Dechsaradecho
   ```

3. **โพส comment ทดสอบ** (ใช้บัญชีเจ้าของโพส):
   - ไปที่โพสต์ใน Facebook
   - เขียน comment ทดสอบ เช่น "TEST_AUTO_REPLY_185500"
   - รอ 5-10 วินาที

4. **ตรวจสอบ**:
   - ดู CLI มี notification "Auto reply triggered"
   - ดู Facebook ควรมี reply T2 ใต้ comment ของคุณ
   - ดู `output.log` ควรมี log "Auto reply posted successfully"

## Troubleshooting

### ไม่ reply อัตโนมัติ

**เช็ค**:
1. `auto_reply.enabled = true`
2. Log แสดง "Post author detected: [ชื่อ]" หรือไม่
3. ชื่อใน log ตรงกับชื่อ author ของ comment หรือไม่
4. Comment เป็น T1 (ไม่ใช่ reply ซ้อน)
5. ดู `output.log` หา error

### ดึงชื่อเจ้าของโพสไม่ได้

**อาการ**:
- Log แสดง "Could not detect post author"
- Auto reply ไม่ทำงานแม้ตั้งค่าถูกต้อง

**สาเหตุ**:
- Facebook เปลี่ยน DOM structure
- โพสเป็น shared post หรือ crosspost
- หน้าโพสยังโหลดไม่เสร็จ

**แก้ไข**:
1. ลองรีสตาร์ท CLI
2. เช็ค `debug_full_page.html` เพื่อดู DOM structure
3. ถ้ายังไม่ได้ ให้ report issue พร้อม screenshot

### Reply ช้า

**สาเหตุ**:
- Browser ต้องหา comment container และปุ่ม reply
- Facebook load ช้า
- `monitor.refresh_interval` สูงเกินไป

**แก้ไข**:
- ลด `monitor.refresh_interval` เหลือ 200-300ms
- เพิ่ม `browser.slow_mo` เป็น 50ms (เร็วขึ้น)

### Reply ซ้ำ

**ไม่ควรเกิด**: ระบบเช็ค `is_new` flag จาก cache แล้ว
ถ้าเกิด → ให้ restart CLI

## เทคนิค

### ข้อความแบบไดนามิก

ปรับแต่ง `reply_message` ใน code:
```python
# ใน detector.py _check_auto_reply()
reply_message = f"ขอบคุณ {comment.author} สำหรับความคิดเห็น"
```

### Reply หลายคน

แก้ไข logic ใน `detector.py`:
```python
post_owner_names = ['Owner 1', 'Owner 2', 'Owner 3']
if any(name.lower() in comment.author.lower() for name in post_owner_names):
    # reply
```

## สรุป

- ✅ Reply เฉพาะ comment ของเจ้าของโพส
- ✅ ทำงานอัตโนมัติเมื่อตรวจจับ comment ใหม่
- ✅ กำหนด config ได้ง่าย
- ✅ บันทึก log ทุกการ reply
- ✅ ใช้ Enter key เพื่อส่ง (ไม่ใช้ปุ่ม - หลีกเลี่ยง confirmation dialog)
