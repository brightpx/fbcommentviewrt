# 🧪 TESTING GUIDE - Optimized Version

## การทดสอบระบบที่ปรับปรุงแล้ว

---

## 📋 Pre-Test Checklist

- [ ] Python 3.8+ installed
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] `config.yaml` configured with your post URL
- [ ] Facebook account logged in
- [ ] Original version tested and working

---

## 🎯 Test Scenarios

### Scenario 1: Basic Detection Test

**Objective:** Verify owner comment detection works

**Steps:**
1. Run optimized version:
   ```bash
   python run_optimized.py
   ```

2. Wait for "✅ System initialized" message

3. Post a comment as the POST OWNER on Facebook

4. Watch console for detection message:
   ```
   🎯 NEW OWNER COMMENT DETECTED: [comment_id]
      Author: [Your Name]
      Message: [Your comment]
   ⚡ Detection latency: XX ms
   ```

**Expected Results:**
- ✅ Comment detected within 100ms
- ✅ Detection latency shown
- ✅ Correct author name displayed

**Pass Criteria:**
- Detection latency < 200ms
- No false positives

---

### Scenario 2: Auto-Reply Test

**Objective:** Verify instant reply posting

**Prerequisites:**
```yaml
auto_reply:
  enabled: true
  reply_message: "ทดสอบระบบตอบกลับอัตโนมัติ"
```

**Steps:**
1. Run optimized version
2. Post owner comment
3. Wait for auto-reply

**Expected Console Output:**
```
🎯 NEW OWNER COMMENT DETECTED: 123456789
⚡ Detection latency: 87ms
📤 Auto-replying...
✅ REPLY POSTED SUCCESSFULLY
⚡ Reply latency: 145ms
```

**Expected Facebook Result:**
- ✅ Reply appears under your comment
- ✅ Reply posted within 300ms total
- ✅ Correct reply message

**Pass Criteria:**
- Total latency < 500ms
- Reply appears correctly threaded
- Reply message matches config

---

### Scenario 3: Performance Benchmark

**Objective:** Measure actual performance gains

**Steps:**

1. **Prepare test environment:**
   - Close other applications
   - Open Task Manager (Windows) or htop (Linux)
   - Note baseline CPU/Memory

2. **Run old version for 5 minutes:**
   ```bash
   python run.py
   ```
   - Monitor CPU usage
   - Monitor memory usage
   - Post 3-5 test comments
   - Record detection times

3. **Run new version for 5 minutes:**
   ```bash
   python run_optimized.py
   ```
   - Monitor CPU usage
   - Monitor memory usage
   - Post 3-5 test comments
   - Record detection times

4. **Compare results:**

   | Metric | Old Version | New Version | Improvement |
   |--------|-------------|-------------|-------------|
   | Avg Detection (ms) | | | |
   | Avg Reply (ms) | | | |
   | CPU Usage (%) | | | |
   | Memory Usage (MB) | | | |

**Pass Criteria:**
- Detection at least 5x faster
- Reply at least 3x faster
- CPU usage at least 50% lower
- Memory usage at least 40% lower

---

### Scenario 4: Rapid Comment Test

**Objective:** Test miss rate under load

**Steps:**
1. Run optimized version
2. Post 10 owner comments rapidly (1 per second)
3. Count how many were detected
4. Count how many got auto-replies

**Expected Results:**
- ✅ All 10 comments detected
- ✅ All 10 comments auto-replied
- ✅ No duplicates
- ✅ Correct order

**Pass Criteria:**
- Detection rate: 100% (10/10)
- No duplicate replies
- Console shows all 10 detections

---

### Scenario 5: Mixed Comment Test

**Objective:** Verify filtering accuracy

**Steps:**
1. Run optimized version
2. Have friend post 5 non-owner comments
3. Post 2 owner comments (you)
4. Have friend post 5 more non-owner comments

**Expected Results:**
- ✅ Only 2 owner comments detected
- ✅ 0 false positives (non-owner detected)
- ✅ Both owner comments auto-replied

**Pass Criteria:**
- Precision: 100% (2/2 correct)
- Recall: 100% (2/2 detected)
- Zero false positives

---

### Scenario 6: Long Message Test

**Objective:** Verify long reply handling

**Configuration:**
```yaml
auto_reply:
  reply_message: "ขอบคุณมากครับสำหรับความคิดเห็น! เรายินดีที่จะตอบทุกคำถามและข้อสงสัยของคุณ ทีมงานของเราพร้อมให้บริการตลอด 24 ชั่วโมง หากมีคำถามเพิ่มเติมกรุณาแจ้งมาได้เลยครับ 🙏✨"
```

**Steps:**
1. Configure long message (150+ characters)
2. Run optimized version
3. Post owner comment
4. Measure reply latency

**Expected Results:**
- ✅ Full message posted correctly
- ✅ Reply latency < 300ms
- ✅ No truncation
- ✅ Thai characters display correctly

**Pass Criteria:**
- Reply latency < 500ms (even for 150 chars)
- Message complete and correct

---

### Scenario 7: 24-Hour Stability Test

**Objective:** Verify no memory leaks or crashes

**Steps:**
1. Run optimized version
2. Leave running for 24 hours
3. Post test comment every hour
4. Monitor:
   - Memory usage trend
   - CPU usage trend
   - Detection accuracy
   - Process stability

**Monitoring Script:**
```python
# monitor_stats.py
import psutil
import time

process_name = "python"
while True:
    for proc in psutil.process_iter(['name', 'memory_info', 'cpu_percent']):
        if process_name in proc.info['name']:
            print(f"{time.ctime()}: "
                  f"CPU: {proc.info['cpu_percent']:.1f}% "
                  f"MEM: {proc.info['memory_info'].rss / 1024 / 1024:.1f}MB")
    time.sleep(60)  # Every minute
```

**Pass Criteria:**
- No crashes
- Memory stable (no continuous growth)
- CPU stable (no degradation)
- 100% detection rate maintained

---

## 📊 Performance Comparison Template

Use this template to record your test results:

```markdown
## Test Results - [Date]

### Environment
- OS: Windows/Linux/Mac
- Python: 3.x.x
- RAM: XGB
- CPU: [Model]

### Detection Performance

| Test | Old Version | New Version | Gain |
|------|-------------|-------------|------|
| Single comment | XXXms | XXms | Xx faster |
| 10 rapid comments | XXXms avg | XXms avg | Xx faster |
| With 50 existing | XXXms | XXms | Xx faster |

### Reply Performance

| Test | Old Version | New Version | Gain |
|------|-------------|-------------|------|
| Short message (20 chars) | XXXms | XXXms | Xx faster |
| Medium (50 chars) | XXXms | XXXms | Xx faster |
| Long (150 chars) | XXXms | XXXms | Xx faster |

### Resource Usage

| Metric | Old Version | New Version | Improvement |
|--------|-------------|-------------|-------------|
| CPU (idle) | XX% | XX% | -XX% |
| CPU (active) | XX% | XX% | -XX% |
| Memory (stable) | XXmb | XXmb | -XX% |
| Memory (peak) | XXmb | XXmb | -XX% |

### Accuracy

| Metric | Old Version | New Version |
|--------|-------------|-------------|
| Detection rate | XX/XX (XX%) | XX/XX (XX%) |
| False positives | X | X |
| False negatives | X | X |

### Issues Found
- [ ] Issue 1: [Description]
- [ ] Issue 2: [Description]

### Verdict
- [ ] ✅ Ready for production
- [ ] ⚠️ Needs minor fixes
- [ ] ❌ Not ready
```

---

## 🐛 Common Issues & Solutions

### Issue 1: "Owner name not found"

**Symptom:**
```
❌ Error: Could not extract post author name
```

**Causes:**
- Post URL incorrect
- Facebook changed DOM structure
- Not logged in

**Solutions:**
1. Verify post URL in config.yaml
2. Check you're logged into Facebook
3. Try manual extraction:
   ```python
   # In browser console
   document.querySelector('[data-ad-rendering-role="profile_name"]')?.innerText
   ```

### Issue 2: No comments detected

**Symptom:**
- Owner comments posted but not detected
- Console shows "👀 Scanning..." but no detection

**Causes:**
- Comment sorting mode wrong
- Owner name mismatch
- Comment ID extraction failed

**Solutions:**
1. Check sorting is "Most Recent"
2. Verify owner name in logs matches your Facebook name
3. Enable debug logging:
   ```yaml
   logging:
     level: DEBUG
   ```

### Issue 3: Reply not posted

**Symptom:**
```
❌ Reply failed: Reply button not found
```

**Causes:**
- Reply button selector changed
- JavaScript not enabled
- Rate limiting

**Solutions:**
1. Manual test: Can you reply manually?
2. Check browser console for errors
3. Increase retry delay:
   ```yaml
   auto_reply:
     retry_delay: 2000
   ```

### Issue 4: High latency

**Symptom:**
- Detection takes > 500ms
- Reply takes > 1000ms

**Causes:**
- Slow network
- Too many comments to scan
- CPU overloaded

**Solutions:**
1. Reduce top_n_comments:
   ```yaml
   monitor:
     top_n_comments: 3
   ```
2. Close other applications
3. Check network speed

### Issue 5: Duplicate replies

**Symptom:**
- Same comment gets multiple replies

**Causes:**
- known_ids not persisting
- Race condition

**Solutions:**
- Should not happen with current implementation
- If occurs, report bug with logs

---

## 📈 Expected Performance Targets

### Tier 1: Acceptable
- Detection: < 300ms
- Reply: < 500ms
- CPU: < 40%
- Accuracy: > 95%

### Tier 2: Good (Expected)
- Detection: < 200ms ✅
- Reply: < 300ms ✅
- CPU: < 20% ✅
- Accuracy: > 98% ✅

### Tier 3: Excellent (Target)
- Detection: < 100ms 🎯
- Reply: < 200ms 🎯
- CPU: < 15% 🎯
- Accuracy: > 99% 🎯

---

## ✅ Sign-Off Checklist

Before deploying to production:

- [ ] All test scenarios passed
- [ ] Performance targets met
- [ ] 24-hour stability test passed
- [ ] No memory leaks detected
- [ ] Accuracy > 98%
- [ ] Documentation reviewed
- [ ] Backup of old version created
- [ ] Rollback plan prepared

---

## 📞 Support

If tests fail or you encounter issues:

1. **Check logs:**
   ```bash
   tail -f logs/app.log
   ```

2. **Enable debug mode:**
   ```yaml
   logging:
     level: DEBUG
   ```

3. **Compare with old version:**
   - Does old version work?
   - What's different?

4. **Report issue:**
   - Console output
   - Log files
   - Test scenario
   - Expected vs actual behavior

---

**Happy Testing! 🚀**

The optimized version should be **significantly faster** and more reliable. If you don't see 5-10x improvement, something is wrong - please investigate before production deployment.
