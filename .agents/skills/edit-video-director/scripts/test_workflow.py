"""Integration checks with synthetic media; no external assets or model downloads."""
import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from engine import ff, validate, render, probe, read_srt
from typography import write_ass
from director import analyze, remap
from types import SimpleNamespace


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix="director-test ' ไทย ")
        cls.root=Path(cls.tmp.name)
        ff(['-f','lavfi','-i','testsrc2=s=256x144:r=24:d=2','-f','lavfi','-i','sine=frequency=330:sample_rate=48000:duration=2','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(cls.root/'sound.mp4')])
        ff(['-f','lavfi','-i','color=c=0x223344:s=256x144:r=30:d=2','-c:v','libx264','-pix_fmt','yuv420p',str(cls.root/'silent.mp4')])
        ff(['-f','lavfi','-i','sine=frequency=110:sample_rate=48000:duration=1','-c:a','pcm_s16le',str(cls.root/'music.wav')])
        Image.new('RGBA',(60,30),(255,40,40,160)).save(cls.root/'logo.png')

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def base(self,name):
        return {'version':1,'output':name+'.mp4','video':{'width':256,'height':144,'fps':24,'preset':'ultrafast','crf':26},'clips':[{'source':'sound.mp4','in':0,'out':1},{'source':'silent.mp4','in':0,'out':1}]}

    def execute(self,p):
        with contextlib.redirect_stdout(io.StringIO()):return render(validate(p,self.root))

    def test_all_transitions_with_mixed_fps_and_silent_source(self):
        for typ in ['fade','dissolve','wipeleft','wiperight','slideleft','slideright','circleopen']:
            with self.subTest(transition=typ):
                p=self.base(typ);p['clips'][1]['transition']={'type':typ,'duration':.25}
                result=self.execute(p);self.assertAlmostEqual(result['duration'],1.75,delta=.1)

    def test_speed_grades_ducking_overlay_and_subtitles(self):
        p=self.base('complete');p['clips'][0].update(speed=.5,fit='cover',zoom=1.1,grade='horror',denoise=True,fade_in=.1)
        p['clips'][1].update(speed=2,transition={'type':'fade','duration':.125},fade_out=.1)
        p['audio']={'normalize_lufs':-16,'duck_music':True,'tracks':[{'source':'music.wav','role':'music','duration':2,'loop':True,'volume':.15},{'source':'music.wav','role':'voice','start':.2,'duration':.5},{'source':'music.wav','role':'sfx','start':1,'duration':.3}]}
        p['overlays']=[{'source':'logo.png','start':.1,'end':2,'width':.15,'opacity':.5}]
        (self.root/'captions.srt').write_text('1\n00:00:00,100 --> 00:00:01,500\nทดสอบเสียง\nEnglish caption\n',encoding='utf-8')
        p['subtitles']={'source':'captions.srt'}
        p['texts']=[{'text':'ทดสอบ','start':.1,'end':1.4,'style':'horror','position':'top','size':14}]
        result=self.execute(p);self.assertEqual(result['full_decode'],'passed');self.assertEqual(result['text_cues'],2)

    def test_cut_then_transition_then_cut(self):
        p=self.base('mixed');p['clips'] += [{'source':'sound.mp4','out':1,'transition':{'type':'dissolve','duration':.25}},{'source':'silent.mp4','out':.5}]
        result=self.execute(p);self.assertAlmostEqual(result['duration'],3.25,delta=.1)

    def test_invalid_plans_and_source_protection(self):
        variants=[]
        p=self.base('bad');p['clips'][0]['speed']=0;variants.append(p)
        p=self.base('bad');p['clips'][0]['in']=1.5;p['clips'][0]['out']=1;variants.append(p)
        p=self.base('bad');p['video']['width']=255;variants.append(p)
        p=self.base('bad');p['clips'][0]['arbitrary_filter']='movie=x';variants.append(p)
        p=self.base('bad');p['output']='sound.mp4';variants.append(p)
        p=self.base('bad');p['texts']=[{'text':'late','start':0,'end':20}];variants.append(p)
        p=self.base('bad');p['clips'][1]['transition']={'type':'fade','duration':1};variants.append(p)
        p=self.base('bad');p['clips'][1]['speed']=float('nan');variants.append(p)
        for p in variants:
            with self.subTest(plan=p):
                with self.assertRaises(ValueError):validate(p,self.root)

    def test_no_overwrite(self):
        p=self.base('existing');(self.root/'existing.mp4').write_bytes(b'preserve')
        with self.assertRaises(FileExistsError):self.execute(p)
        self.assertEqual((self.root/'existing.mp4').read_bytes(),b'preserve')

    def test_no_text_export(self):
        p=self.base('clean-export');p['texts']=[{'text':'Test','start':0,'end':1}]
        with contextlib.redirect_stdout(io.StringIO()):r=render(validate(p,self.root),no_text=True)
        self.assertEqual(r['text_cues'],0);self.assertFalse((self.root/'clean-export.ass').exists())
        self.assertIsNone(r['normalization_target_lufs'])
        self.assertIn('disabled',r['loudness_mode'])
        self.assertIn('integrated_lufs',r['audio_measurement'])

    def test_caption_remap_speed_transition(self):
        p=self.base('remap');p['clips'][0]['speed']=2;p['clips'][1]['transition']={'type':'fade','duration':.125}
        (self.root/'remap.json').write_text(json.dumps(p))
        for name in ['sound','silent']:
            (self.root/f'{name}.json').write_text(json.dumps({'source':str(self.root/f'{name}.mp4'),'segments':[{'start':0,'end':1,'text':name}]}))
        args=SimpleNamespace(plan=str(self.root/'remap.json'),output=str(self.root/'mapped.srt'),transcripts=[str(self.root/'sound.json'),str(self.root/'silent.json')])
        with contextlib.redirect_stdout(io.StringIO()):remap(args)
        cues=read_srt(self.root/'mapped.srt');self.assertAlmostEqual(cues[0]['end'],.375,places=3);self.assertAlmostEqual(cues[1]['start'],.375,places=3)

    def test_silence_analysis_and_text_escape(self):
        with contextlib.redirect_stdout(io.StringIO()):analyze(self.root/'sound.mp4',self.root/'analysis.json')
        self.assertEqual(json.loads((self.root/'analysis.json').read_text())['silences'],[])
        dest=self.root/'text.ass'
        write_ass([{'text':'ไทย {test} \\pos(1,1)','start':0,'end':2,'animation':'typewriter'}],1280,720,dest)
        self.assertIn('｛',dest.read_text(encoding='utf-8-sig'))


if __name__=='__main__':unittest.main(verbosity=2)
