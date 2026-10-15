#!/usr/bin/env python3
"""Create synthetic test media and a bilingual six-style showcase plan."""
import json
import math
import struct
import sys
import wave
from pathlib import Path
from PIL import Image
from engine import ff

def create(directory):
    d=Path(directory).resolve();d.mkdir(parents=True,exist_ok=True)
    if (d/'showcase.json').exists():raise FileExistsError('Demo directory already contains showcase.json')
    w,h=1280,720
    im=Image.new('RGB',(w,h));px=im.load()
    for y in range(h):
        for x in range(w):
            glow=max(0,1-math.hypot((x-w*.78)/w,(y-h*.28)/h)*1.3)
            rim=max(0,1-math.hypot((x-w*.12)/w,(y-h*.9)/h)*1.8)
            px[x,y]=(int(8+glow*12+rim*14),int(12+glow*20+rim*3),int(20+glow*34+rim*10))
    im.save(d/'background.png')
    ff(['-loop','1','-i',str(d/'background.png'),'-vf',"zoompan=z='min(zoom+0.0003,1.08)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s=1280x720:fps=30,drawgrid=w=160:h=120:t=1:c=white@0.025",'-t','4','-c:v','libx264','-pix_fmt','yuv420p',str(d/'source.mp4')])
    rate=48000;n=rate*21
    with wave.open(str(d/'music.wav'),'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(rate)
        data=bytearray()
        for i in range(n):
            t=i/rate;env=min(1,t/1.5,(21-t)/2)
            val=.08*env*(math.sin(2*math.pi*110*t)+.35*math.sin(2*math.pi*164.81*t)+.2*math.sin(2*math.pi*220*t))
            data.extend(struct.pack('<h',int(val*32767)))
        f.writeframes(data)
    spec=[('clean','เรียบง่าย แต่ชัดเจน','CLEAN / EDITORIAL','fade'),('bold','หยุดดู...ตรงนี้!','BOLD / IMPACT','pop'),('smooth','ปล่อยให้ภาพเล่าเรื่อง','SMOOTH / CINEMATIC','slide'),('horror','อย่าหันกลับมา','HORROR / SLOW REVEAL','ghost'),('neon','โลกใหม่ เริ่มที่คุณ','NEON / FUTURE','fade'),('clean','ทุกคำ มีจังหวะของมัน','TYPE / STORYTELLING','typewriter')]
    plan={'version':1,'output':'Video-Director-Thai-English-Demo.mp4','video':{'width':w,'height':h,'fps':30,'crf':19,'preset':'fast'},'clips':[],'texts':[],'audio':{'duck_music':False,'normalize_lufs':-18,'tracks':[{'source':'music.wav','role':'music','volume':.8,'duration':20,'fade_in':1,'fade_out':1}]}}
    for i,(style,title,label,animation) in enumerate(spec):
        start=i*3.3333333333
        plan['clips'].append({'source':'source.mp4','in':0,'out':3.3333333333,'transition':{'type':'cut'}})
        plan['texts'] += [
            {'text':'VIDEO DIRECTOR  /  TH + EN','start':start,'end':start+3.3,'style':'clean','position':'top','size':19,'color':'94A3B8'},
            {'text':title,'start':start+.15,'end':start+3.15,'style':style,'animation':animation,'size':64,'position':'center'},
            {'text':label,'start':start+.25,'end':start+3.15,'style':'clean','size':21,'y':.65,'color':'A5B4FC'},
            {'text':f'0{i+1}  /  06     •     MOTION TYPE SYSTEM','start':start,'end':start+3.3,'style':'caption','size':16,'y':.88,'color':'94A3B8'}]
    # Keep symbol repertoire inside the bundled font.
    (d/'showcase.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    print(d/'showcase.json')

if __name__=='__main__':create(sys.argv[1])
