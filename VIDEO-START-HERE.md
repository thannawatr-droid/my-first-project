# Video Director — เริ่มใช้งาน

ติดตั้ง Skill ไว้ใน `.agents/skills/edit-video-director/` แล้ว มีโค้ดตัดต่อ ฟอนต์ไทย–อังกฤษ ระบบข้อความเคลื่อนไหว และเครื่องมือตรวจไฟล์

## ตั้งค่าสภาพแวดล้อมครั้งแรก

ต้องมี Python 3.10+ และ FFmpeg ที่รองรับ libass/libx264 อยู่ในเครื่องที่รันงานก่อน การอัปโหลดไฟล์ซอร์ส FFmpeg `.tar.xz` เข้า GitHub อย่างเดียวไม่ได้ติดตั้งโปรแกรม

```bash
python3 setup_video.py --transcribe --download-model small
```

คำสั่งนี้สร้าง `.venv` ภายในโปรเจกต์ ติดตั้งไลบรารี และดาวน์โหลดโมเดลถอดเสียงหลายภาษา โมเดล small ใช้งานเริ่มต้นได้ แต่ความแม่นยำภาษาไทยและชื่อเฉพาะต้องตรวจแก้ โมเดลขนาดใหญ่ใช้ทรัพยากรมากขึ้น

หากยังไม่ต้องใช้การถอดเสียง:

```bash
python3 setup_video.py
```

บน Windows ใช้ `py setup_video.py` แทน `python3 setup_video.py` และใช้ `.venv\Scripts\python.exe` แทน `.venv/bin/python`

## สั่ง Codex

เลือก repository นี้ แล้วสั่ง:

> ใช้ $edit-video-director ตรวจสภาพแวดล้อมและตัดฟุตเทจที่แนบเป็นคลิปแนวตั้ง 45 วินาที โทนหลอนแต่กระชับ ข้อความไทยแบบ Horror เฉพาะจุดสำคัญ ซับอ่านง่าย ใช้เพลงที่ให้และลดเพลงตอนพูด เก็บไฟล์ต้นฉบับไว้ ส่ง MP4 ฉบับร่างพร้อมรายงานตรวจไฟล์

ถ้าระบบยังไม่พร้อม ให้ Codex อ่าน AGENTS.md และเรียก setup_video.py ก่อน อย่าใส่ฟุตเทจจริงลง repository สาธารณะ ให้ใช้พื้นที่ไฟล์ที่อนุญาตหรือโฟลเดอร์ media/ ในเครื่องทำงาน

## ทดลองก่อนใช้ฟุตเทจจริง

```bash
.venv/bin/python .agents/skills/edit-video-director/scripts/director.py doctor
.venv/bin/python .agents/skills/edit-video-director/scripts/create_demo.py outputs/demo
.venv/bin/python .agents/skills/edit-video-director/scripts/director.py render outputs/demo/showcase.json
```

## ถอดเสียงไทย

```bash
.venv/bin/python .agents/skills/edit-video-director/scripts/director.py transcribe media/clip.mp4 outputs/transcript.json --language th --model models/faster-whisper-small
```

ได้ JSON และ SRT เวลาของไฟล์ต้นฉบับ ต้องปรับเวลาก่อนใช้กับคลิปที่ตัดแล้วตาม Skill

## ขอบเขต

สร้าง MP4 ได้ ไม่ใช่โปรเจกต์ CapCut ข้อความใน MP4 เป็นภาพที่ฝังแล้ว มี ASS และ CSV ประกอบสำหรับตรวจแก้แผน ระบบนี้ไม่เปิด CapCut หรือควบคุมหน้าจอเครื่องผู้ใช้

การติดตั้งในสภาพแวดล้อมแชต/คลาวด์ไม่ได้ติดตั้งบน Mac/Windows ของผู้ใช้ และสภาพแวดล้อมใหม่อาจต้องรัน setup ซ้ำ จึงเก็บตัวติดตั้งนี้ไว้ใน repository
