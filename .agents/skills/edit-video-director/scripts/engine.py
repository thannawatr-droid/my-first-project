"""Validated JSON edit plan -> FFmpeg MP4. No shell evaluation."""
import csv
import json
import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typography import STYLES, ANIMATIONS, FONTS, write_ass

TRANSITIONS = {'cut', 'fade', 'dissolve', 'wipeleft', 'wiperight', 'slideleft', 'slideright', 'circleopen'}
GRADES = {
    'natural': None,
    'cinematic': 'eq=contrast=1.07:saturation=0.92:brightness=-0.01',
    'horror': 'eq=contrast=1.12:saturation=0.62:brightness=-0.025,colorbalance=bs=0.035:gs=0.015',
    'warm': 'eq=saturation=0.95,colorbalance=rs=0.035:bs=-0.025',
    'mono': 'hue=s=0',
}

def run(args, cwd=None):
    p = subprocess.run([str(x) for x in args], cwd=cwd, capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError(f'{args[0]} failed ({p.returncode}):\n{p.stderr[-6500:]}')
    return p

def ff(args, cwd=None):
    return run(['ffmpeg', '-hide_banner', '-nostdin', '-loglevel', 'warning', '-y', '-filter_complex_threads', '1', '-filter_threads', '1', *args], cwd)

def probe(path):
    return json.loads(run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(path)]).stdout)

def duration(meta):
    value = meta.get('format', {}).get('duration')
    if value is None:
        value = max((float(s.get('duration',0)) for s in meta['streams']), default=0)
    return float(value)

def has(meta, kind):
    return any(s['codec_type'] == kind for s in meta['streams'])

def keys(obj, allowed, location):
    if not isinstance(obj, dict):
        raise ValueError(location + ' must be an object')
    unknown = set(obj) - set(allowed.split())
    if unknown:
        raise ValueError(f'{location}: unknown fields {sorted(unknown)}')

def number(value, lo, hi, label):
    if isinstance(value, bool) or not isinstance(value, (int,float)) or not math.isfinite(value) or not lo <= value <= hi:
        raise ValueError(f'{label} must be a finite number in [{lo}, {hi}]')
    return float(value)

def choice(value, choices, label):
    if value not in choices:
        raise ValueError(f'{label}: choose one of {sorted(choices)}')

def file_path(value, base):
    p = (base / value).resolve()
    if not p.is_file():
        raise ValueError(f'Input file missing: {p}')
    return p

def load_plan(path):
    path = Path(path).resolve()
    p = json.loads(path.read_text(encoding='utf-8-sig'))
    return validate(p, path.parent)

def validate(p, base):
    keys(p, 'version output video clips texts subtitles audio overlays', 'plan')
    if p.get('version') != 1: raise ValueError('version must be 1')
    if not isinstance(p.get('output'),str) or not p['output'].endswith('.mp4'): raise ValueError('output must end in .mp4')
    p['_output'] = (base / p['output']).resolve()
    v=p.setdefault('video',{})
    keys(v,'width height fps crf preset','video')
    for key,default,lo,hi in [('width',1920,128,7680),('height',1080,128,7680),('fps',30,1,120),('crf',20,0,40)]:
        n=v.setdefault(key,default);number(n,lo,hi,'video.'+key)
        if int(n)!=n: raise ValueError(key+' must be an integer')
    if v['width']%2 or v['height']%2: raise ValueError('width and height must be even')
    choice(v.setdefault('preset','medium'),{'ultrafast','veryfast','fast','medium','slow'},'preset')
    if not isinstance(p.get('clips'),list) or not p['clips']: raise ValueError('At least one clip is required')
    total=0.; cache={}; inputs=[]
    for i,c in enumerate(p['clips']):
        keys(c,'source in out speed fit crop_x crop_y zoom volume grade denoise fade_in fade_out transition','clip')
        src=file_path(c['source'],base);inputs.append(src);c['_source']=src
        if src not in cache: cache[src]=probe(src)
        m=cache[src];c['_meta']=m
        if not has(m,'video'): raise ValueError(f'Clip {i} has no video')
        a=number(c.setdefault('in',0),0,duration(m),'clip.in')
        b=number(c.setdefault('out',duration(m)),0,duration(m)+.05,'clip.out')
        if b<=a: raise ValueError('clip.out must be later than clip.in')
        speed=number(c.setdefault('speed',1),.25,4,'speed')
        # Frame quantization prevents accumulating duration drift over many clips.
        d=round((b-a)/speed*v['fps'])/v['fps']
        if d < 2/v['fps']: raise ValueError('Clip needs at least two output frames')
        c['_duration']=d
        choice(c.setdefault('fit','contain'),{'contain','cover'},'fit')
        choice(c.setdefault('grade','natural'),set(GRADES),'grade')
        for k,default,lo,hi in [('crop_x',.5,0,1),('crop_y',.5,0,1),('zoom',1,1,2),('volume',1,0,4),('fade_in',0,0,d/2),('fade_out',0,0,d/2)]:
            number(c.setdefault(k,default),lo,hi,k)
        if not isinstance(c.get('denoise',False),bool): raise ValueError('denoise must be boolean')
        t=c.setdefault('transition',{'type':'cut'})
        keys(t,'type duration','transition')
        choice(t.setdefault('type','cut'),TRANSITIONS,'transition.type')
        overlap=number(t.get('duration',.4 if t['type']!='cut' else 0),0,5,'transition.duration')
        if t['type']=='cut' and overlap: raise ValueError('A cut cannot have an overlap duration')
        if t['type']!='cut' and (i==0 or overlap<=0): raise ValueError('Transitions need a preceding clip and positive duration')
        overlap=round(overlap*v['fps'])/v['fps']
        if t['type']!='cut' and overlap < 1/v['fps']: raise ValueError('Transition shorter than one frame')
        if i and overlap >= min(d,p['clips'][i-1]['_duration']): raise ValueError('Transition must be shorter than both adjacent clips')
        if i and overlap + p['clips'][i-1]['transition']['duration'] > p['clips'][i-1]['_duration']:
            raise ValueError('Incoming and outgoing overlaps cannot overlap inside the middle clip')
        t['duration']=overlap;c['_start']=total-overlap
        total+=d-overlap
    p['_duration']=total
    cues=p.setdefault('texts',[])
    for t in cues:
        keys(t,'text start end style animation position x y size color max_width max_lines reveal','text')
        if not isinstance(t.get('text'),str) or not t['text'].strip(): raise ValueError('Text must be a nonempty string')
        check_interval(t,total,'text')
        choice(t.get('style','clean'),set(STYLES),'text.style')
        if 'animation' in t: choice(t['animation'],ANIMATIONS,'animation')
        choice(t.get('position','center'),{'top','center','bottom'},'position')
        for k,lo,hi in [('x',.05,.95),('y',.05,.95),('size',10,min(v['width'],v['height'])*.25),('max_width',.1,.9),('max_lines',1,5),('reveal',.1,10)]:
            if k in t: number(t[k],lo,hi,k)
        if 'max_lines' in t and int(t['max_lines'])!=t['max_lines']: raise ValueError('max_lines must be integer')
    sub=p.get('subtitles')
    if sub:
        keys(sub,'source style position','subtitles')
        src=file_path(sub['source'],base);inputs.append(src)
        choice(sub.get('style','caption'),set(STYLES),'subtitle style')
        choice(sub.get('position','bottom'),{'top','center','bottom'},'subtitle position')
        cues.extend(read_srt(src,sub.get('style','caption'),sub.get('position','bottom')))
        for t in cues: check_interval(t,total,'subtitle')
    au=p.setdefault('audio',{})
    keys(au,'tracks duck_music normalize_lufs','audio')
    if not isinstance(au.get('duck_music',True),bool): raise ValueError('duck_music must be boolean')
    if au.get('normalize_lufs') is not None: number(au['normalize_lufs'],-24,-9,'normalize_lufs')
    for t in au.get('tracks',[]):
        keys(t,'source role start in duration volume fade_in fade_out loop','audio track')
        src=file_path(t['source'],base);inputs.append(src);t['_source']=src
        meta=probe(src)
        if not has(meta,'audio'): raise ValueError('Audio track has no audio stream')
        choice(t.setdefault('role','music'),{'music','voice','sfx'},'role')
        start=number(t.setdefault('start',0),0,total,'audio.start')
        a=number(t.setdefault('in',0),0,duration(meta),'audio.in')
        if a >= duration(meta): raise ValueError('audio.in must precede end of source')
        d=number(t.setdefault('duration',min(duration(meta)-a,total-start)),.01,total-start,'audio.duration')
        loop=t.setdefault('loop',False)
        if not isinstance(loop,bool): raise ValueError('loop must be boolean')
        if not loop and a+d > duration(meta)+.05: raise ValueError('Audio exceeds source duration; enable loop or shorten it')
        for k,default,lo,hi in [('volume',.2 if t['role']=='music' else 1,0,4),('fade_in',0,0,d/2),('fade_out',0,0,d/2)]:number(t.setdefault(k,default),lo,hi,k)
    for o in p.get('overlays',[]):
        keys(o,'source start end x y width opacity','overlay')
        src=file_path(o['source'],base);inputs.append(src);o['_source']=src
        if src.suffix.lower() not in {'.png','.jpg','.jpeg','.webp'}: raise ValueError('Overlays support still images only')
        check_interval(o,total,'overlay')
        for k,default,lo,hi in [('x',.05,0,1),('y',.05,0,1),('width',.2,.01,1),('opacity',1,0,1)]:number(o.setdefault(k,default),lo,hi,k)
        if o['x']+o['width']>1: raise ValueError('Overlay extends beyond right edge')
        from PIL import Image
        with Image.open(src) as im: ratio=im.height/im.width
        if o['y']+o['width']*v['width']*ratio/v['height'] > 1.001: raise ValueError('Overlay extends beyond bottom edge')
    if p['_output'] in inputs: raise ValueError('Output cannot overwrite any input')
    return p

def check_interval(t,total,label):
    a=number(t['start'],0,total,label+'.start');b=number(t['end'],0,total+.001,label+'.end')
    if b-a < .02: raise ValueError(label+' must have a positive duration of at least .02 seconds')

def read_srt(path,style='caption',position='bottom'):
    content=Path(path).read_text(encoding='utf-8-sig').replace('\r','')
    import re
    cues=[]
    def seconds(s):
        h,m,sec=re.split('[:,.]',s)[:3];ms=re.split('[:,.]',s)[3]
        return int(h)*3600+int(m)*60+int(sec)+int(ms)/1000
    for block in re.split(r'\n\s*\n',content.strip()):
        rows=block.splitlines()
        if not rows: continue
        idx=1 if rows[0].strip().isdigit() else 0
        match=re.fullmatch(r'(\d+:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d+:\d{2}:\d{2}[,.]\d{3})',rows[idx].strip())
        if not match: raise ValueError('Invalid SRT cue timing: '+rows[idx])
        body='\n'.join(rows[idx+1:])
        if not body.strip(): raise ValueError('Empty SRT cue')
        cues.append(dict(start=seconds(match[1]),end=seconds(match[2]),text=body,style=style,position=position))
    return cues

def tempo(speed):
    parts=[]
    while speed>2: parts.append('atempo=2');speed/=2
    while speed<.5: parts.append('atempo=0.5');speed/=.5
    return ','.join(parts+[f'atempo={speed:.8f}'])

def encode(v):
    return ['-c:v','libx264','-preset',v['preset'],'-crf',str(v['crf']),'-pix_fmt','yuv420p','-threads','2']

def normalize_clip(c,v,dest):
    w,h,fps=v['width'],v['height'],v['fps'];d=c['_duration']
    inp=['-ss',str(c['in']),'-t',str(c['out']-c['in']),'-i',str(c['_source'])]
    if not has(c['_meta'],'audio'):inp+=['-f','lavfi','-i','anullsrc=r=48000:cl=stereo']
    vf=[f'setpts=(PTS-STARTPTS)/{c["speed"]}',f'fps={fps}']
    if c['fit']=='contain':
        vf += [f'scale={w}:{h}:force_original_aspect_ratio=decrease:force_divisible_by=2',f'pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black']
    else:
        vf += [f'scale={w}:{h}:force_original_aspect_ratio=increase:force_divisible_by=2',f'crop={w}:{h}:(iw-ow)*{c["crop_x"]}:(ih-oh)*{c["crop_y"]}']
    if c['zoom']>1:
        zw=math.ceil(w*c['zoom']/2)*2;zh=math.ceil(h*c['zoom']/2)*2
        vf += [f'scale={zw}:{zh}',f'crop={w}:{h}:(iw-ow)*{c["crop_x"]}:(ih-oh)*{c["crop_y"]}']
    vf+=['setsar=1','format=yuv420p',f'settb=1/{fps}',f'tpad=stop_mode=clone:stop_duration=1',f'trim=duration={d}']
    if GRADES[c['grade']]:vf.append(GRADES[c['grade']])
    af=['asetpts=PTS-STARTPTS','aresample=48000', 'aformat=sample_fmts=fltp:channel_layouts=stereo',tempo(c['speed']),f'volume={c["volume"]}']
    if c.get('denoise'):af+=['highpass=f=70','afftdn=nf=-25']
    for kind in ['in','out']:
        fade=c['fade_'+kind]
        if fade:
            st=0 if kind=='in' else d-fade
            vf.append(f'fade=t={kind}:st={st}:d={fade}')
            af.append(f'afade=t={kind}:st={st}:d={fade}')
    af += ['apad',f'atrim=duration={d}','asetpts=PTS-STARTPTS']
    ai=0 if has(c['_meta'],'audio') else 1
    graph=f'[0:v:0]{",".join(vf)}[v];[{ai}:a:0]{",".join(af)}[a]'
    ff([*inp,'-filter_complex',graph,'-map','[v]','-map','[a]',*encode(v),'-c:a','pcm_s16le','-t',str(d),str(dest)])

def assemble(p,work):
    v=p['video'];clips=p['clips'];inputs=[];g=[]
    for i,c in enumerate(clips):
        dest=work/f'clip-{i:04}.mkv'
        print(f'Prepare clip {i+1}/{len(clips)}',flush=True)
        normalize_clip(c,v,dest);inputs+=['-i',str(dest)]
        g += [f'[{i}:v]settb=1/{v["fps"]},setpts=PTS-STARTPTS[v{i}]',f'[{i}:a]asetpts=PTS-STARTPTS[a{i}]']
    vl,al='v0','a0';elapsed=clips[0]['_duration']
    for i,c in enumerate(clips[1:],1):
        nv,na=f'joinedv{i}',f'joineda{i}';t=c['transition'];d=t['duration']
        if t['type']=='cut':
            g += [f'[{vl}][{al}][v{i}][a{i}]concat=n=2:v=1:a=1[{nv}][{na}]']
        else:
            # concat outputs AVTB; normalize both inputs for mixed cut/xfade plans.
            g += [f'[{vl}]settb=1/{v["fps"]}[tb{i}]',f'[tb{i}][v{i}]xfade=transition={t["type"]}:duration={d}:offset={elapsed-d}[{nv}]',f'[{al}][a{i}]acrossfade=d={d}:c1=tri:c2=tri[{na}]']
        elapsed+=c['_duration']-d;vl,al=nv,na
    dest=work/'assembly.mkv'
    ff([*inputs,'-filter_complex',';'.join(g),'-map',f'[{vl}]','-map',f'[{al}]',*encode(v),'-c:a','pcm_s16le','-t',str(p['_duration']),str(dest)])
    return dest

def finish(p,work,assembly,no_text=False):
    v=p['video'];total=p['_duration'];inputs=['-i',str(assembly)];g=[];index=1
    groups={'voice':['base'],'music':[],'sfx':[]}
    g+=['[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[base]']
    for j,t in enumerate(p['audio'].get('tracks',[])):
        if t['loop']:inputs+=['-stream_loop','-1']
        inputs+=['-ss',str(t['in']),'-t',str(t['duration']),'-i',str(t['_source'])]
        filters=['asetpts=PTS-STARTPTS','aresample=48000','aformat=sample_fmts=fltp:channel_layouts=stereo',f'volume={t["volume"]}']
        for k in ['in','out']:
            if t['fade_'+k]:filters.append(f'afade=t={k}:st={0 if k=="in" else t["duration"]-t["fade_"+k]}:d={t["fade_"+k]}')
        filters += [f'adelay={round(t["start"]*1000)}:all=1','apad',f'atrim=duration={total}']
        label=f'track{j}';g.append(f'[{index}:a]{",".join(filters)}[{label}]');groups[t['role']].append(label);index+=1
    def mix(labels,label):
        if len(labels)==1:g.append(f'[{labels[0]}]anull[{label}]')
        else:g.append(''.join(f'[{x}]' for x in labels)+f'amix=inputs={len(labels)}:duration=longest:normalize=0[{label}]')
    mix(groups['voice'],'voice');mixes=['voice']
    if groups['music']:
        mix(groups['music'],'music')
        if p['audio'].get('duck_music',True):
            g+=['[voice]asplit=2[voiceout][side]','[music][side]sidechaincompress=threshold=0.03:ratio=8:attack=25:release=300:makeup=1[ducked]']
            mixes=['voiceout','ducked']
        else:mixes.append('music')
    mixes+=groups['sfx'];mix(mixes,'mix')
    filters=[]
    if p['audio'].get('normalize_lufs') is not None:
        filters.append(f'loudnorm=I={p["audio"]["normalize_lufs"]}:TP=-1.5:LRA=11')
    filters+=['alimiter=limit=0.84:level=false:latency=true','aresample=48000',f'atrim=duration={total}']
    g.append('[mix]'+','.join(filters)+'[audio]')
    vl='0:v'
    for j,o in enumerate(p.get('overlays',[])):
        inputs+=['-loop','1','-i',str(o['_source'])]
        g.append(f'[{index}:v]format=rgba,scale={round(v["width"]*o["width"])}:-1,colorchannelmixer=aa={o["opacity"]}[img{j}]')
        out=f'overlay{j}'
        g.append(f'[{vl}][img{j}]overlay=x={v["width"]*o["x"]}:y={v["height"]*o["y"]}:enable=\'between(t,{o["start"]},{o["end"]})\':shortest=1[{out}]');vl=out;index+=1
    if p['texts'] and not no_text:
        write_ass(p['texts'],v['width'],v['height'],work/'titles.ass')
        shutil.copytree(FONTS,work/'fonts')
        # Relative generated names avoid filter syntax problems in user paths.
        g.append(f'[{vl}]ass=filename=titles.ass:fontsdir=fonts[video]');vl='video'
    else:g.append(f'[{vl}]null[video]');vl='video'
    (work/'final-filter.txt').write_text(';'.join(g),encoding='utf-8')
    dest=work/'render.mp4'
    result=ff([*inputs,'-filter_complex_script','final-filter.txt','-map',f'[{vl}]','-map','[audio]',*encode(v),'-c:a','aac','-b:a','192k','-ar','48000','-r',str(v['fps']),'-t',str(total),'-movflags','+faststart',str(dest)],work)
    (work/'render.log').write_text(result.stderr,encoding='utf-8')
    if 'Glyph 0x' in result.stderr and 'not found' in result.stderr: raise ValueError('Missing font glyph during render; inspect render.log')
    return dest

def verify(path,expected=None):
    m=probe(path)
    if not has(m,'video') or not has(m,'audio'):raise ValueError('Output missing video/audio')
    v=next(s for s in m['streams'] if s['codec_type']=='video')
    if expected:
        spec=expected['video']
        if (v['width'],v['height'])!=(spec['width'],spec['height']):raise ValueError('Wrong output dimensions')
        if abs(duration(m)-expected['_duration'])>max(.15,2/spec['fps']):raise ValueError('Wrong output duration')
        from fractions import Fraction
        if abs(float(Fraction(v['avg_frame_rate']))-spec['fps'])>.001:raise ValueError('Wrong output frame rate')
    decoded=run(['ffmpeg','-v','error','-nostdin','-i',str(path),'-f','null','-'])
    if decoded.stderr.strip():raise ValueError('Decode reported errors: '+decoded.stderr[-2000:])
    return {'duration':duration(m),'width':v['width'],'height':v['height'],'fps':v.get('avg_frame_rate'),'video_codec':v['codec_name'],'audio_codec':next(s['codec_name'] for s in m['streams'] if s['codec_type']=='audio'),'full_decode':'passed','visual_review':'required','listening_review':'required'}

def render(p,overwrite=False,no_text=False):
    out=p['_output'];out.parent.mkdir(parents=True,exist_ok=True)
    # Use a separate directory for all intermediate files; never overwrite sources.
    if out.exists() and not overwrite:raise FileExistsError(f'{out} exists; choose a new name or use --overwrite')
    sidecars=[out.with_suffix('.report.json'),out.with_suffix('.timeline.csv'),out.with_suffix('.ass')]
    if not overwrite and any(s.exists() for s in sidecars):raise FileExistsError('A sidecar exists; choose a new output name or use --overwrite')
    with tempfile.TemporaryDirectory(prefix='video-director-',dir=out.parent) as temp:
        work=Path(temp);assembly=assemble(p,work);dest=finish(p,work,assembly,no_text)
        report=verify(dest,p)
        # ffprobe loudness statistics are measurements, not a claim of listening.
        stats=run(['ffmpeg','-hide_banner','-nostdin','-i',str(dest),'-af','loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json','-vn','-f','null','-']).stderr
        import re
        found=re.search(r'\{\s*"input_i".*?\}',stats,re.S)
        if found:
            measured=json.loads(found[0])
            report['audio_measurement']={'integrated_lufs':measured['input_i'],'true_peak_dbtp':measured['input_tp'],'loudness_range_lu':measured['input_lra']}
        target=p['audio'].get('normalize_lufs')
        report['normalization_target_lufs']=target
        report['loudness_mode']='single-pass normalization; inspect measurement, not guaranteed broadcast compliance' if target is not None else 'normalization disabled; peak limiter only'
        report['text_cues']=len(p['texts']) if not no_text else 0
        if out.exists() and not overwrite:raise FileExistsError(str(out))
        os.replace(dest,out)
        if (work/'titles.ass').exists():shutil.copy2(work/'titles.ass',out.with_suffix('.ass'))
        with out.with_suffix('.timeline.csv').open('w',newline='',encoding='utf-8-sig') as f:
            writer=csv.writer(f);writer.writerow(['clip','source','source_in','source_out','speed','timeline_start','timeline_end','transition'])
            for i,c in enumerate(p['clips']):writer.writerow([i+1,str(c['_source']),c['in'],c['out'],c['speed'],c['_start'],c['_start']+c['_duration'],c['transition']['type']])
        out.with_suffix('.report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'output':str(out),'report':report},ensure_ascii=False,indent=2))
    return report
