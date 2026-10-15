"""ASS motion typography. All user text is literal; no raw ASS injection."""
import math
import re
import unicodedata
from pathlib import Path

FONTS = Path(__file__).resolve().parents[1] / 'assets' / 'fonts'
STYLES = {
    'clean': dict(color='FFFFFF', outline='111827', size=.048, bold=False, border=2, shadow=1, animation='fade'),
    'bold': dict(color='FDE047', outline='101018', size=.066, bold=True, border=3, shadow=2, animation='pop'),
    'smooth': dict(color='FFF7ED', outline='20202B', size=.052, bold=False, border=1.4, shadow=1, animation='slide'),
    'horror': dict(color='F1E9DF', outline='460C17', size=.062, bold=True, border=2.6, shadow=3, animation='ghost'),
    'neon': dict(color='69F5FF', outline='264466', size=.058, bold=True, border=2, shadow=0, animation='fade'),
    'caption': dict(color='FFFFFF', outline='101010', size=.044, bold=True, border=2.8, shadow=0, animation='none'),
}
ANIMATIONS = {'none', 'fade', 'slide', 'pop', 'ghost', 'typewriter'}

def color(value):
    value = str(value).lstrip('#')
    if not re.fullmatch('[0-9A-Fa-f]{6}', value):
        raise ValueError('Color must be a six-digit RGB hex value')
    return '&H' + value[4:6] + value[2:4] + value[:2] + '&'

def timestamp(sec):
    cs = round(float(sec) * 100)
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f'{h}:{m:02}:{s:02}.{cs:02}'

def literal(text):
    # Fullwidth substitutions prevent override or newline-tag injection.
    return str(text).replace('\\', '＼').replace('{', '｛').replace('}', '｝').replace('\r', '').replace('\n', r'\N')

def clusters(text):
    """Conservative combining-mark clusters; never split Thai tone marks."""
    out = []
    for c in text:
        if out and (unicodedata.combining(c) or unicodedata.category(c).startswith('M') or c == '\u0e33'):
            out[-1] += c
        else:
            out.append(c)
    return out

def measure(text, size, bold):
    from PIL import ImageFont
    font = ImageFont.truetype(str(FONTS / ('NotoSansThai-Bold.ttf' if bold else 'NotoSansThai-Regular.ttf')), max(1, round(size)))
    return font.getlength(text)

def layout(text, size, width, bold, max_lines=3):
    """Wrap by measured width; retain manually supplied line breaks."""
    for trial in range(10):
        lines = []
        for para in str(text).split('\n'):
            line = ''
            # Preserve English words; Thai fallback uses combining-safe clusters.
            tokens = re.findall(r'[A-Za-z0-9]+(?:[\x27’-][A-Za-z0-9]+)*|\s+|[^A-Za-z0-9\s]+', para)
            for token in tokens:
                pieces = [token] if measure(token, size, bold) <= width else clusters(token)
                for piece in pieces:
                    if line and measure(line + piece, size, bold) > width:
                        lines.append(line.rstrip())
                        line = piece.lstrip()
                    else:
                        line += piece
            lines.append(line.rstrip())
        if len(lines) <= max_lines and max((measure(x, size, bold) for x in lines), default=0) <= width:
            return '\n'.join(lines), size
        size *= .9
    raise ValueError('Text is too long: split into several timed cues')

def check_glyphs(text):
    from fontTools.ttLib import TTFont
    with TTFont(FONTS / 'NotoSansThai-Regular.ttf') as font:
        cmap = font.getBestCmap()
    missing = {c for c in text if not c.isspace() and ord(c) not in cmap}
    if missing:
        raise ValueError('Bundled font lacks glyphs: ' + ''.join(sorted(missing)) + '. Use a supplied image overlay for symbols/emoji.')

def write_ass(cues, width, height, dest):
    check_glyphs(''.join(str(x['text']) for x in cues))
    lines = ['[Script Info]', 'ScriptType: v4.00+', f'PlayResX: {width}', f'PlayResY: {height}',
             'ScaledBorderAndShadow: yes', 'WrapStyle: 2', '', '[V4+ Styles]',
             'Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding',
             'Style: Default,Noto Sans Thai,48,&H00FFFFFF,&H00FFFFFF,&H00111111,&H80000000,0,0,0,0,100,100,0,0,1,2,0,5,0,0,0,1',
             '', '[Events]', 'Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text']
    scale = min(width, height) / 1080

    def event(start, end, tags, body, layer=1):
        if end - start >= .01:
            lines.append(f'Dialogue: {layer},{timestamp(start)},{timestamp(end)},Default,,0,0,0,,{{{tags}}}{literal(body)}')

    for cue in cues:
        s = STYLES[cue.get('style', 'clean')].copy()
        start, end = float(cue['start']), float(cue['end'])
        duration = end - start
        size = float(cue.get('size', min(width, height) * s['size']))
        body, size = layout(cue['text'], size, width * float(cue.get('max_width', .82)), s['bold'], int(cue.get('max_lines', 3)))
        position = cue.get('position', 'center')
        x = width * float(cue.get('x', .5))
        y_default = {'top': .18, 'center': .5, 'bottom': .78}[position]
        y = height * float(cue.get('y', y_default))
        base = fr'\an5\fnNoto Sans Thai\fs{size:.2f}\b{1 if s["bold"] else 0}\bord{s["border"]*scale:.2f}\shad{s["shadow"]*scale:.2f}\1c{color(cue.get("color",s["color"]))}\3c{color(s["outline"])}'
        animation = cue.get('animation', s['animation'])
        fade = min(300, round(duration * 220))
        pos = fr'\pos({x:.1f},{y:.1f})'
        motion = ''
        if animation == 'fade':
            motion = fr'\fad({fade},{fade})'
        elif animation == 'slide':
            pos = fr'\move({x:.1f},{y+32*scale:.1f},{x:.1f},{y:.1f},0,{min(450,round(duration*300))})'
            motion = fr'\fad({fade},{fade})'
        elif animation == 'pop':
            motion = fr'\fscx86\fscy86\t(0,{min(200,round(duration*180))},\fscx100\fscy100)\fad(50,{fade})'
        elif animation == 'ghost':
            # Slow blur reveal, no strobe flashes or rapid full-screen flicker.
            motion = fr'\blur{7*scale:.2f}\t(0,{min(800,round(duration*400))},\blur0.4)\fad({min(650,round(duration*300))},{fade})'
        if s is not None and cue.get('style') == 'neon':
            glow = base + pos + fr'\bord{6*scale:.2f}\blur{9*scale:.2f}\alpha&H80&' + motion
            event(start, end, glow, body, 0)
        if animation == 'typewriter':
            # Keep a fixed ASS layout using invisible unrevealed glyphs.
            cs = clusters(body)
            reveal = min(float(cue.get('reveal', 1)), duration * .7)
            for i in range(1, len(cs)+1):
                t0 = start + reveal * (i-1)/max(1,len(cs))
                t1 = start + reveal * i/max(1,len(cs)) if i < len(cs) else end
                payload = literal(''.join(cs[:i])) + r'{\alpha&HFF&}' + literal(''.join(cs[i:]))
                lines.append(f'Dialogue: 1,{timestamp(t0)},{timestamp(t1)},Default,,0,0,0,,{{{base+pos}}}{payload}')
        else:
            event(start, end, base + pos + motion, body)
    Path(dest).write_text('\n'.join(lines)+'\n', encoding='utf-8-sig')
