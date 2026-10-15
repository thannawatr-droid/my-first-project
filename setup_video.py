#!/usr/bin/env python3
"""Install Video Director in a project-local virtual environment."""
import argparse
import json
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKILL = ROOT / '.agents' / 'skills' / 'edit-video-director'

def run(*args):
    subprocess.run([str(a) for a in args], check=True, cwd=ROOT)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--transcribe',action='store_true',help='Install optional faster-whisper speech support')
    parser.add_argument('--download-model',choices=['tiny','base','small','medium','large-v3'],help='Download multilingual model weights (can be large)')
    args=parser.parse_args()
    if sys.version_info < (3,10):parser.error('Python 3.10+ is required')
    if args.download_model and not args.transcribe:parser.error('--download-model requires --transcribe')
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        print('FFmpeg/ffprobe must be installed on this machine first.')
        print('macOS with Homebrew: brew install ffmpeg')
        print('Ubuntu/Debian: sudo apt-get install ffmpeg')
        print('Windows: install a build with libass and libx264, then add its bin folder to PATH.')
        return 2
    env=ROOT/'.venv'
    py=env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not py.exists():venv.EnvBuilder(with_pip=True).create(env)
    run(py,'-m','pip','install','-r',SKILL/'scripts/requirements.txt')
    if args.transcribe:
        run(py,'-m','pip','install','-r',SKILL/'scripts/requirements-transcribe.txt')
    run(py,SKILL/'scripts/director.py','doctor')
    if args.download_model:
        target=ROOT/'models'/('faster-whisper-'+args.download_model)
        # Values are positional arguments, never shell or Python interpolation.
        code='from faster_whisper.utils import download_model; import sys; print(download_model(sys.argv[1], output_dir=sys.argv[2]))'
        run(py,'-c',code,args.download_model,target)
        run(py,'-c','from faster_whisper import WhisperModel; import sys; m=WhisperModel(sys.argv[1],device="cpu",compute_type="int8"); print("Multilingual model loaded:",m.model.is_multilingual)',target)
    print('Ready. Run:',str(py),str(SKILL/'scripts/director.py'),'--help')
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except subprocess.CalledProcessError as e:sys.exit(e.returncode)
