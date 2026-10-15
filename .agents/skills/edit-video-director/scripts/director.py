#!/usr/bin/env python3
"""Command-line entry point for edit-video-director. Python 3.10+."""
import argparse
import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path
from engine import ff, run, probe, duration, has, load_plan, render, verify
from typography import FONTS, STYLES

def write_json(path,obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2)

def doctor():
    deps={k:bool(importlib.util.find_spec(k)) for k in ['PIL','fontTools','faster_whisper']}
    tools={k:shutil.which(k) for k in ['ffmpeg','ffprobe']}
    filters={};encoders={}
    if tools['ffmpeg']:
        available=run(['ffmpeg','-hide_banner','-filters']).stdout
        filters={k:bool(re.search(r'\s'+k+r'\s',available)) for k in ['ass','xfade','acrossfade','sidechaincompress','loudnorm','afftdn','alimiter']}
        enc=run(['ffmpeg','-hide_banner','-encoders']).stdout
        encoders={k:bool(re.search(r'\s'+k+r'\s',enc)) for k in ['libx264','aac','pcm_s16le']}
    fonts=all((FONTS/f'NotoSansThai-{w}.ttf').is_file() for w in ['Regular','Bold'])
    ready=all(tools.values()) and deps['PIL'] and deps['fontTools'] and fonts and all(filters.values()) and all(encoders.values())
    result={'ready_for_render':ready,'python':sys.version.split()[0],'tools':tools,'packages':deps,'filters':filters,'encoders':encoders,'bundled_fonts':fonts,'styles':list(STYLES),'transcription':'optional: requires faster-whisper and model weights; no automatic model download during render'}
    print(json.dumps(result,indent=2));return 0 if ready else 1

def analyze(source,out,threshold=-35,min_silence=.4,scene=.3):
    source=Path(source).resolve();m=probe(source)
    result={'source':str(source),'duration':duration(m),'silences':[],'scene_candidates':[],'note':'Candidates only. Silence is not proof that a moment should be cut. Review speech and picture before editing.'}
    if has(m,'audio'):
        log=run(['ffmpeg','-hide_banner','-nostdin','-i',str(source),'-af',f'silencedetect=noise={threshold}dB:d={min_silence}','-vn','-f','null','-']).stderr
        pending=None
        for line in log.splitlines():
            a=re.search(r'silence_start: ([\d.]+)',line);b=re.search(r'silence_end: ([\d.]+)',line)
            if a:pending=float(a[1])
            if b and pending is not None:result['silences'].append({'start':pending,'end':min(float(b[1]),duration(m))});pending=None
        if pending is not None:result['silences'].append({'start':pending,'end':duration(m)})
    if has(m,'video'):
        log=run(['ffmpeg','-hide_banner','-nostdin','-i',str(source),'-vf',f"select='gt(scene,{scene})',showinfo",'-an','-f','null','-']).stderr
        result['scene_candidates']=[float(x) for x in re.findall(r'pts_time:([\d.]+)',log)]
    write_json(out,result);print(str(Path(out).resolve()))

def srt_time(sec):
    ms=max(0,round(sec*1000));h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);s,ms=divmod(ms,1000)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'

def save_srt(cues,path):
    with Path(path).open('x',encoding='utf-8-sig') as f:
        for i,c in enumerate(cues,1):f.write(f'{i}\n{srt_time(c["start"])} --> {srt_time(c["end"])}\n{c["text"].strip()}\n\n')

def transcribe(args):
    try:from faster_whisper import WhisperModel
    except ImportError:raise ValueError('Install optional faster-whisper first: python -m pip install faster-whisper')
    target=Path(args.output).resolve();srt=target.with_suffix('.srt')
    if target.suffix!='.json':raise ValueError('Transcript output must end in .json')
    if target.exists() or srt.exists():raise FileExistsError('Transcript or SRT exists; choose a new output name')
    source=Path(args.source).resolve()
    if not has(probe(source),'audio'):raise ValueError('Source has no audio to transcribe')
    print('Loading transcription model. A model name may download weights; a local model path works offline.',flush=True)
    model=WhisperModel(args.model,device=args.device,compute_type='int8' if args.device=='cpu' else 'float16')
    segments,info=model.transcribe(str(source),language=None if args.language=='auto' else args.language,word_timestamps=True,vad_filter=args.vad,beam_size=5,condition_on_previous_text=False)
    cues=[]
    for s in segments:
        cues.append({'start':s.start,'end':s.end,'text':s.text.strip(),'words':[{'start':w.start,'end':w.end,'text':w.word,'probability':w.probability} for w in (s.words or [])]})
    result={'source':str(source),'language':info.language,'language_probability':info.language_probability,'segments':cues,'review_required':True,'note':'ASR is fallible. Verify Thai names, mixed languages, negatives and timestamps against audio. No translation or speaker diarization is performed.'}
    write_json(target,result);save_srt(cues,srt);print(str(target))

def remap(args):
    """Map reviewed source transcripts through cuts, speed and overlaps."""
    p=load_plan(args.plan);transcripts={}
    for file in args.transcripts:
        data=json.loads(Path(file).read_text(encoding='utf-8-sig'))
        src=Path(data['source'])
        if not src.is_absolute():src=Path(file).resolve().parent/src
        transcripts[str(src.resolve())]=data['segments']
    cues=[];warnings=[]
    for i,c in enumerate(p['clips']):
        segments=transcripts.get(str(c['_source']))
        if segments is None:raise ValueError('Missing source transcript: '+str(c['_source']))
        cap_end=p['clips'][i+1]['_start'] if i+1<len(p['clips']) else p['_duration']
        for s in segments:
            a=max(float(s['start']),c['in']);b=min(float(s['end']),c['out'])
            if b<=a:continue
            clipped=a>float(s['start'])+.01 or b<float(s['end'])-.01
            body=s['text']
            if clipped:
                words=[w for w in s.get('words',[]) if float(w['start'])>=a-.01 and float(w['end'])<=b+.01]
                if not words:
                    warnings.append(f'Clip {i+1}: omitted partial segment without usable word timings at {a:.2f}');continue
                body=''.join(w['text'] for w in words).strip()
                a=float(words[0]['start']);b=float(words[-1]['end'])
                warnings.append(f'Clip {i+1}: partial phrase trimmed using ASR word timings; review at {a:.2f}')
            start=c['_start']+(a-c['in'])/c['speed'];end=min(cap_end,c['_start']+(b-c['in'])/c['speed'])
            if end-start>=.08:cues.append({'start':start,'end':end,'text':body})
    cues.sort(key=lambda c:c['start']);save_srt(cues,args.output)
    print(json.dumps({'output':str(Path(args.output).resolve()),'cues':len(cues),'warnings':warnings,'review_required':True},ensure_ascii=False,indent=2))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor')
    q=sub.add_parser('inspect');q.add_argument('source')
    q=sub.add_parser('validate');q.add_argument('plan')
    q=sub.add_parser('render');q.add_argument('plan');q.add_argument('--overwrite',action='store_true');q.add_argument('--no-text',action='store_true')
    q=sub.add_parser('verify');q.add_argument('source')
    q=sub.add_parser('analyze');q.add_argument('source');q.add_argument('output');q.add_argument('--threshold',type=float,default=-35);q.add_argument('--min-silence',type=float,default=.4);q.add_argument('--scene',type=float,default=.3)
    q=sub.add_parser('proxy');q.add_argument('source');q.add_argument('output');q.add_argument('--width',type=int,default=960)
    q=sub.add_parser('frames');q.add_argument('source');q.add_argument('directory');q.add_argument('--times',type=float,nargs='+',required=True)
    q=sub.add_parser('transcribe');q.add_argument('source');q.add_argument('output');q.add_argument('--model',default='small');q.add_argument('--language',default='auto',choices=['auto','th','en']);q.add_argument('--device',default='cpu',choices=['cpu','cuda']);q.add_argument('--vad',action='store_true')
    q=sub.add_parser('remap-captions');q.add_argument('plan');q.add_argument('output');q.add_argument('transcripts',nargs='+')
    args=parser.parse_args()
    if args.command=='doctor':return doctor()
    if args.command=='inspect':print(json.dumps(probe(args.source),ensure_ascii=False,indent=2))
    elif args.command=='validate':
        p=load_plan(args.plan)
        from typography import write_ass
        import tempfile
        with tempfile.TemporaryDirectory() as d:write_ass(p['texts'],p['video']['width'],p['video']['height'],Path(d)/'test.ass')
        print(json.dumps({'valid':True,'duration':p['_duration'],'clips':len(p['clips']),'text_cues':len(p['texts'])},indent=2))
    elif args.command=='render':render(load_plan(args.plan),args.overwrite,args.no_text)
    elif args.command=='verify':print(json.dumps(verify(args.source),indent=2))
    elif args.command=='analyze':
        if not -90<=args.threshold<=0 or not .05<=args.min_silence<=60 or not 0<args.scene<1:raise ValueError('Invalid analysis thresholds')
        analyze(args.source,args.output,args.threshold,args.min_silence,args.scene)
    elif args.command=='proxy':
        out=Path(args.output).resolve()
        if out.exists():raise FileExistsError(str(out))
        if args.width<128 or args.width>3840 or args.width%2:raise ValueError('Proxy width must be even, 128–3840')
        out.parent.mkdir(parents=True,exist_ok=True)
        ff(['-i',str(Path(args.source).resolve()),'-map','0:v:0','-map','0:a:0?', '-vf',f'scale={args.width}:-2,setsar=1','-c:v','libx264','-crf','26','-preset','veryfast','-c:a','aac','-b:a','128k','-movflags','+faststart',str(out)])
    elif args.command=='frames':
        d=Path(args.directory);d.mkdir(parents=True,exist_ok=True);m=probe(args.source)
        for i,t in enumerate(args.times):
            if not 0<=t<duration(m):raise ValueError('Frame time outside source duration')
            out=d/f'frame-{i+1:03}-{t:.2f}.jpg'
            if out.exists():raise FileExistsError(str(out))
            ff(['-ss',str(t),'-i',str(Path(args.source).resolve()),'-frames:v','1','-update','1','-q:v','2',str(out)])
    elif args.command=='transcribe':transcribe(args)
    elif args.command=='remap-captions':remap(args)
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except (ValueError,RuntimeError,FileExistsError,KeyError,TypeError,OSError) as e:
        print(f'ERROR: {e}',file=sys.stderr);sys.exit(2)
