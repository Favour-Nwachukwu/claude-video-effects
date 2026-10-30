#!/usr/bin/env python3
"""20 free video effects for Claude, by @favoritetechgal

One effect:    python fx.py orbit in.mp4 out.mp4 --start 3.2 --end 6
Many effects:  python fx.py --plan plan.json in.mp4 out.mp4
Quick check:   python fx.py --plan plan.json in.mp4 check.png --still 4.5
List them:     python fx.py --list
"""
import argparse, json, math, os, random, subprocess, sys
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = {k: os.path.join(ROOT, 'fonts', v) for k, v in {
    'bold': 'ArchivoBlack-Regular.ttf', 'serif': 'InstrumentSerif-Italic.ttf', 'mono': 'SpaceMono-Bold.ttf',
    'hand': 'PermanentMarker-Regular.ttf', 'ui': 'Inter.ttf', 'uim': 'Inter.ttf', 'uib': 'Inter.ttf',
    'anton': 'Anton-Regular.ttf', 'mont': 'Montserrat.ttf', 'monts': 'Montserrat.ttf', 'montb': 'Montserrat.ttf',
    'didone': 'PlayfairDisplay.ttf', 'didoneb': 'PlayfairDisplay.ttf', 'didonei': 'PlayfairDisplay-Italic.ttf'}.items()}
WGHT = {'ui': (24, 640), 'uim': (24, 540), 'uib': (32, 860), 'mont': (700,), 'monts': (600,), 'montb': (800,), 'didone': (500,), 'didoneb': (800,), 'didonei': (500,)}  # Inter variable: (optical size, weight)
CREAM, INK, PEACH, YELLOW = (244, 233, 216), (22, 22, 24), (255, 183, 165), (255, 214, 10)
NAMES = ['The Noise', 'The Lineup', 'Locked On', 'Orbit', 'Lean-In', 'Backdrop Word', 'Spotlight', 'The Bill',
         'Moody', 'Swipe', 'The To-Do', 'Comment Box', 'The Tap', 'Pause & Point', 'Uninstall', 'Reel Frame',
         'Shortcut Rain', 'Reject Stamp', 'Countdown Flip', 'Rabbit Hole', 'Cover Star', 'Scribble']
EFFECTS = {}
ALIASES = {'the-noise': 'noise', 'the-lineup': 'lineup', 'bill': 'the-bill', 'to-do': 'todo', 'the-todo': 'todo', 'the-to-do': 'todo', 'the-tap': 'tap', 'follow': 'tap', 'comment': 'comment-box', 'pause': 'pause-point', 'pause-and-point': 'pause-point', 'backdrop': 'backdrop-word', 'stamp': 'reject-stamp', 'countdown': 'countdown-flip', 'split': 'split-headline', 'headline': 'headline-box', 'imessage': 'messages', 'texts': 'messages', 'notifications': 'messages'}
LOOK_NAMES = {'glitter-spotlight': ('spotlight', 'sparkle'), 'glitter': ('spotlight', 'sparkle')}  # a named look of another effect
CARD_FX = ('noise', 'orbit')


def effect(name, desc):
    def deco(fn):
        EFFECTS[name] = (fn, desc)
        return fn
    return deco


# ---------- small helpers ----------
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease_out(x): x = clamp(x); return 1 - (1 - x) ** 3
def ease_inout(x): x = clamp(x); return 3 * x * x - 2 * x * x * x
def ease_back(x): x = clamp(x); s = 1.7; x -= 1; return x * x * ((s + 1) * x + s) + 1
def ramp(c, e, t_in=0.25, t_out=0.2): return clamp(c.lt / t_in) * clamp((e.d - c.lt) / t_out) if t_out else clamp(c.lt / t_in)
def rgb(v, default):
    if v is None: return default
    if isinstance(v, (list, tuple)): return tuple(int(x) for x in v[:3])
    v = str(v).lstrip('#'); return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))


_fc = {}
def font(kind, size):
    k = (kind, int(size))
    if k not in _fc:
        f = ImageFont.truetype(FONT[kind], max(6, int(size)))
        if kind in WGHT:
            try: f.set_variation_by_axes(list(WGHT[kind]))
            except Exception: pass
        _fc[k] = f
    return _fc[k]


def text_img(s, size, kind='bold', fill=(255, 255, 255), stroke=0, stroke_fill=INK, shadow=0, glow=None):
    f = font(kind, size)
    bb = f.getbbox(s, stroke_width=stroke)
    pad = int(size * 0.2 + shadow * 2.5 + (glow[1] * 2.5 if glow else 0)) + 4
    w, h = bb[2] - bb[0] + 2 * pad, bb[3] - bb[1] + 2 * pad
    pos = (pad - bb[0], pad - bb[1])
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    if shadow:
        sh = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((pos[0], pos[1] + shadow * 0.5), s, font=f, fill=(0, 0, 0, 160), stroke_width=stroke)
        im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(shadow)))
    if glow:
        g = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(g).text(pos, s, font=f, fill=tuple(glow[0]) + (255,), stroke_width=int(size * 0.04))
        g = g.filter(ImageFilter.GaussianBlur(glow[1]))
        im = Image.alpha_composite(Image.alpha_composite(im, g), g)
    ImageDraw.Draw(im).text(pos, s, font=f, fill=tuple(fill) + (255,), stroke_width=stroke, stroke_fill=tuple(stroke_fill) + (255,))
    return im


def fit_text(s, max_w, kind='bold', start=400, **kw):
    size = start
    while size > 10 and font(kind, size).getlength(s) > max_w: size = int(size * 0.92)
    return text_img(s, size, kind, **kw)


def rrect(w, h, r, fill, outline=None, width=0):
    im = Image.new('RGBA', (int(w), int(h)), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle([0, 0, int(w) - 1, int(h) - 1], int(r), fill=fill, outline=outline, width=width)
    return im


def shadowed(im, blur=18, dy=10, alpha=120):
    pad = blur * 2 + abs(dy)
    out = Image.new('RGBA', (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))
    a = im.split()[3].point(lambda v: v * alpha // 255)
    sh = Image.new('RGBA', im.size, (0, 0, 0, 255)); sh.putalpha(a)
    out.paste(sh, (pad, pad + dy), sh)
    out = out.filter(ImageFilter.GaussianBlur(blur))
    out.alpha_composite(im, (pad, pad))
    return out


def to_np(im): return np.asarray(im.convert('RGBA'), dtype=np.float32) / 255.0


def comp(c, layer, x, y, alpha=1.0, behind=False, guard=False):
    """Alpha-composite an RGBA layer with its top-left at (x, y).
    behind=True hides it wherever the person is (so it sits behind you).
    guard=True only hides it where it would cover your face."""
    L = to_np(layer) if isinstance(layer, Image.Image) else layer
    h, w = L.shape[:2]; x, y = int(round(x)), int(round(y))
    x0, y0, x1, y1 = max(0, x), max(0, y), min(c.W, x + w), min(c.H, y + h)
    if x1 <= x0 or y1 <= y0 or alpha <= 0: return
    L = L[y0 - y:y1 - y, x0 - x:x1 - x]
    a = L[..., 3:4] * alpha
    m = c.m[y0:y1, x0:x1, None]
    if behind: a = a * (1 - m)
    elif guard:
        yy, xx = np.ogrid[y0:y1, x0:x1]
        e = ((xx - c.fx) / (c.fw * 0.95)) ** 2 + ((yy - c.fy) / (c.fw * 1.35)) ** 2
        a = a * (1 - np.clip((1.2 - e) / 0.3, 0, 1)[..., None] * m)
    dst = c.img[y0:y1, x0:x1]
    dst[:] = dst * (1 - a) + L[..., :3] * a


def place(c, im, cx, cy, scale=1.0, rot=0.0, alpha=1.0, behind=False, guard=False):
    """Draw a PIL image centred on (cx, cy), scaled and rotated (degrees, counter-clockwise)."""
    if scale <= 0.01 or alpha <= 0: return
    if abs(scale - 1) > 0.005:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BILINEAR)
    if abs(rot) > 0.05: im = im.rotate(rot, Image.BICUBIC, expand=True)
    comp(c, im, cx - im.width / 2, cy - im.height / 2, alpha, behind, guard)


def camera(c, zoom, cx, cy):
    """Zoom the whole frame (and the person mask) towards (cx, cy). Capped at 2x so it stays sharp."""
    zoom = min(zoom, 2.0)
    if zoom <= 1.002: return
    cw, ch = c.W / zoom, c.H / zoom
    x0 = clamp(cx - cw / 2, 0, c.W - cw); y0 = clamp(cy - ch / 2, 0, c.H - ch)
    M = np.float32([[zoom, 0, -x0 * zoom], [0, zoom, -y0 * zoom]])
    c.img = cv2.warpAffine(c.img, M, (c.W, c.H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
    c.m = cv2.warpAffine(c.m, M, (c.W, c.H), flags=cv2.INTER_LINEAR)
    c.fx, c.fy, c.fw = (c.fx - x0) * zoom, (c.fy - y0) * zoom, c.fw * zoom


def face_cam(c, zoom, head_at=0.40):
    """Zoom on the face, keeping it at `head_at` of the frame height."""
    z = min(zoom, 2.0)
    camera(c, z, c.fx, c.fy + (c.H / z) * (0.5 - head_at))


def grade(img, kind='moody'):
    lum = (img @ np.float32([0.299, 0.587, 0.114]))[..., None]
    if kind == 'bw':
        g = np.clip((lum - 0.5) * 1.25 + 0.5, 0, 1); return np.repeat(g, 3, axis=2)
    if kind == 'warm': return np.clip(img * np.float32([1.08, 1.0, 0.86]) + 0.02, 0, 1)
    if kind == 'cool': return np.clip(img * np.float32([0.9, 1.0, 1.1]), 0, 1)
    if kind == 'pop':
        o = lum + (img - lum) * 1.35; return np.clip((o - 0.5) * 1.12 + 0.5, 0, 1)
    # moody: a little darker, softer colour, teal shadows, warm highlights, gentle contrast
    o = lum + (img - lum) * 0.6
    o = np.power(np.clip(o, 0, 1), 1.3) * 0.88
    o = o + (1 - lum) * np.float32([-0.03, 0.035, 0.065]) + lum * np.float32([0.05, 0.015, -0.04])
    o = np.clip((o - 0.42) * 1.12 + 0.42, 0, 1)
    return o


_vig = {}
def vignette(c, strength=0.35):
    k = (c.W, c.H)
    if k not in _vig:
        yy, xx = np.ogrid[0:c.H, 0:c.W]
        d = ((xx - c.W / 2) / (c.W * 0.75)) ** 2 + ((yy - c.H / 2) / (c.H * 0.7)) ** 2
        _vig[k] = np.clip(d, 0, 1).astype(np.float32)
    c.img *= (1 - strength * _vig[k])[..., None]


def card(im, w, radius=0.07):
    """A reel-shaped (9:16) rounded card with a soft shadow."""
    h = int(w * 16 / 9)
    src = im.convert('RGB'); sw, sh = src.size
    s = max(w / sw, h / sh)
    src = src.resize((max(w, int(sw * s)), max(h, int(sh * s))), Image.LANCZOS)
    l, t = (src.width - w) // 2, (src.height - h) // 2
    src = src.crop((l, t, l + w, t + h)).convert('RGBA')
    m = Image.new('L', (w, h), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], int(w * radius), fill=255)
    src.putalpha(m)
    ImageDraw.Draw(src).rounded_rectangle([0, 0, w - 1, h - 1], int(w * radius), outline=(0, 0, 0, 70), width=2)
    return shadowed(src, blur=max(6, w // 16), dy=w // 22, alpha=150)


def vary(im, i):
    """Give each card its own look, so a pile of frames reads as different reels."""
    kind = ('pop', 'bw', 'warm', 'cool', 'moody')[i % 5]
    a = np.asarray(im.convert('RGB'), np.float32) / 255
    return Image.fromarray((grade(a, kind) * 255).astype(np.uint8))


def cached(e, key, fn):
    if key not in e.state: e.state[key] = fn()
    return e.state[key]


# ---------- the effects ----------
@effect('noise', 'reels pile up behind your head, one every quarter second')
def fx_noise(c, e):
    cw = int(c.W * float(e.o.get('size', 0.34)))
    def setup():
        rnd = random.Random(7); n = min(16, max(4, int(e.d / 0.22)))
        return [(rnd.uniform(0.14, 0.86), rnd.uniform(0.12, 0.52), rnd.uniform(-7, 7)) for _ in range(n)]
    pos = cached(e, 'pos', setup)
    cards = cached(e, 'cards', lambda: [card(vary(im, i) if e.o.get('images') is None else im, cw) for i, im in enumerate(e.cards)])
    out = clamp((e.d - c.lt) / 0.2)
    for i, (x, y, r) in enumerate(pos):
        t0 = i * 0.22
        if c.lt < t0: break
        k = ease_back((c.lt - t0) / 0.25)
        place(c, cards[i % len(cards)], x * c.W, y * c.H, 0.6 + 0.4 * k, r, clamp((c.lt - t0) / 0.08) * out, behind=True)


@effect('lineup', 'numbered tiles fan out in an arc above your head')
def fx_lineup(c, e):
    names = e.o.get('text', '|'.join(NAMES)).split('|')
    tw = int(c.W * 0.105)
    def tile(i, name):
        im = rrect(tw, int(tw * 1.25), tw * 0.16, (24, 24, 28, 225), (255, 255, 255, 60), 2)
        d = ImageDraw.Draw(im)
        num = text_img(f'{i + 1:02d}', tw * 0.42, 'serif', CREAM)
        im.alpha_composite(num, ((tw - num.width) // 2, int(tw * 0.04)))
        words = name.split(' ')
        lines = [' '.join(words[:len(words) // 2 or 1]), ' '.join(words[len(words) // 2 or 1:])] if len(name) > 10 else [name]
        f = font('ui', tw * 0.15)
        for j, ln in enumerate([l for l in lines if l]):
            d.text((tw / 2, tw * (0.78 + 0.19 * j)), ln, font=f, fill=(255, 255, 255, 235), anchor='mm')
        return shadowed(im, 8, 5, 90)
    tiles = cached(e, 'tiles', lambda: [tile(i, n) for i, n in enumerate(names)])
    n = len(tiles); outer = math.ceil(n / 2 + 0.5); inner = n - outer
    cx, cy = c.W / 2 * 0.6 + c.fx * 0.4, c.fy + c.fw * 0.3
    slots = []
    for row, cnt, R in ((0, outer, c.W * 0.47), (1, inner, c.W * 0.33)):
        for k in range(cnt):
            a = math.pi * (0.94 - 0.88 * k / max(1, cnt - 1))
            slots.append((cx + R * math.cos(a), cy - R * math.sin(a) * 1.05, math.degrees(a - math.pi / 2) * 0.3))
    out = clamp((e.d - c.lt) / 0.2)
    for i, (x, y, r) in enumerate(slots[:n]):
        t0 = 0.035 * i
        if c.lt < t0: continue
        k = ease_back((c.lt - t0) / 0.3)
        place(c, tiles[i], x, y + (1 - k) * 40, 0.5 + 0.5 * k, r, clamp((c.lt - t0) / 0.1) * out, behind=True)


@effect('locked-on', 'corner brackets snap onto your face and the camera follows you')
def fx_locked_on(c, e):
    face_cam(c, 1 + (float(e.o.get('zoom', 1.35)) - 1) * ease_out(c.lt / 0.6))
    snap = ease_out(c.lt / 0.22); s = c.fw * 0.85 * (1 + 0.6 * (1 - snap))
    al = clamp(c.lt / 0.12) * clamp((e.d - c.lt) / 0.2)
    size = int(2 * s + 40); im = Image.new('RGBA', (size, int(size * 1.25)), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = 20, 20, size - 20, im.height - 20; L = int(s * 0.32); wd = max(4, int(c.W / 200))
    for (px, py, dx, dy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        d.line([(px, py + dy * L), (px, py), (px + dx * L, py)], fill=(255, 255, 255, 255), width=wd, joint='curve')
    place(c, shadowed(im, 6, 2, 120), c.fx, c.fy, alpha=al)
    tag = text_img(e.o.get('text', 'LOCKED ON').upper(), c.W * 0.022, 'mono', INK)
    pill = rrect(tag.width + 10, tag.height, tag.height / 2, (255, 255, 255, 235)); pill.alpha_composite(tag, (5, 0))
    place(c, pill, c.fx, c.fy + s * 1.25 + pill.height, alpha=clamp((c.lt - 0.15) / 0.15) * al, guard=True)


@effect('orbit', 'your reels circle your head: in front at the bottom, behind you at the top')
def fx_orbit(c, e):
    K = int(e.o.get('count', 6)); cw = int(c.W * float(e.o.get('size', 0.2)))
    cards = cached(e, 'cards', lambda: [card(vary(im, i) if e.o.get('images') is None else im, cw) for i, im in enumerate(e.cards)])
    intro, out = ease_out(c.lt / 0.4), clamp((e.d - c.lt) / 0.25)
    rx, ry = c.W * 0.38 * intro, max(c.fw * 1.5, c.H * 0.1)
    oy = c.fy + c.fw * 0.9
    items = []
    for i in range(K):
        th = i * 2 * math.pi / K + c.lt * float(e.o.get('speed', 1.9))
        items.append((math.sin(th), th, i))
    for depth, th, i in sorted(items):
        place(c, cards[i % len(cards)], c.fx + rx * math.cos(th), oy + ry * math.sin(th), (0.78 + 0.24 * (depth + 1) / 2) * (0.5 + 0.5 * intro),
              -6 * math.cos(th), out * clamp(c.lt / 0.15), behind=depth < 0, guard=depth >= 0)


@effect('lean-in', 'a fast punch-in on one word')
def fx_lean_in(c, e):
    z = float(e.o.get('zoom', 1.45))
    face_cam(c, 1 + (z - 1) * ease_out(c.lt / float(e.o.get('speed', 0.18))), 0.42)


@effect('backdrop-word', 'a giant word drops in behind you')
def fx_backdrop_word(c, e):
    word = e.o.get('text', 'CLAUDE')
    im = cached(e, 'w', lambda: fit_text(word, c.W * 0.94, e.o.get('font', 'bold'), fill=rgb(e.o.get('color'), CREAM), shadow=10))
    k = ease_back(c.lt / 0.42)
    y_end = c.fy - c.fw * 1.05
    y = -im.height + (y_end + im.height) * k
    place(c, im, c.W / 2 * 0.6 + c.fx * 0.4, y, alpha=clamp((e.d - c.lt) / 0.2), behind=True)


_grid = {}
def grid(c):
    if (c.W, c.H) not in _grid:
        yy, xx = np.mgrid[0:c.H, 0:c.W].astype(np.float32); _grid[(c.W, c.H)] = (xx, yy)
    return _grid[(c.W, c.H)]


@effect('spotlight', 'kill the lights, keep you lit')
def fx_spotlight(c, e):
    if e.o.get('look') == 'sparkle': return spotlight_sparkle(c, e)
    face_cam(c, 1 + (float(e.o.get('push', 1.1)) - 1) * ease_inout(c.lt / e.d))
    k = ramp(c, e, 0.3, 0.25)
    xx, yy = grid(c)
    d = ((xx - c.fx) / (c.W * 0.5)) ** 2 + ((yy - (c.fy + c.H * 0.2)) / (c.H * 0.46)) ** 2
    pool = np.clip(1 - d, 0, 1) ** 1.6
    bright = 1 - k * (1 - (0.2 + 0.45 * pool))
    f = bright * (1 - c.m) + c.m * (1 + 0.04 * k)
    if e.o.get('text'):
        word = e.o['text']; col = rgb(e.o.get('color'), PEACH)
        im = cached(e, 'w', lambda: fit_text(word, c.W * 0.9, e.o.get('font', 'serif'), fill=col, glow=(col, 26)))
        c.img *= f[..., None]
        place(c, im, c.W / 2, c.fy - c.fw * 1.1, alpha=k, behind=True)
    else:
        c.img *= f[..., None]


@effect('the-bill', 'prints every instruction like a ticket, into the wall above your head')
def fx_bill(c, e):
    lines = e.o.get('text', 'ORDER #1021|1x orbit|1x spotlight|1x lean-in|cut the dead air|TOTAL: 1 prompt').split('|')
    def build():
        pw = int(c.W * 0.5); lh = int(pw * 0.085); pad = int(pw * 0.08)
        h = pad * 2 + lh * (len(lines) + 1)
        im = Image.new('RGBA', (pw, h), CREAM + (255,)); d = ImageDraw.Draw(im)
        f = font('mono', lh * 0.62)
        for i, ln in enumerate(lines):
            y = pad + lh * i + (lh if i == len(lines) - 1 else 0)
            if i == len(lines) - 1:
                for x in range(pad, pw - pad, 14): d.line([(x, y - lh * 0.45), (x + 7, y - lh * 0.45)], fill=INK + (140,), width=2)
            d.text((pad, y), ln, font=f, fill=INK + (255,))
        return im
    rec = cached(e, 'r', build)
    slot_y, sw = c.H * 0.075, c.W * 0.62
    max_h = max(80, c.fy - c.fw * 1.3 - slot_y)
    s = min(1.0, max_h / rec.height)
    pr = ease_inout(c.lt / (e.d * 0.75)); L = int(rec.height * pr)
    al = clamp((e.d - c.lt) / 0.25)
    cx = c.W / 2
    if L > 2:
        paper = rec.crop((0, 0, rec.width, L))
        z = 14; jag = Image.new('RGBA', (rec.width, L + z), (0, 0, 0, 0)); jag.paste(paper, (0, 0))
        ImageDraw.Draw(jag).polygon([(x, L) for x in range(0, rec.width + 1, 2 * z)] + [(rec.width, L)] +
                                    [(x + z, L + z) for x in range(rec.width - 2 * z, -1, -2 * z)], fill=CREAM + (255,))
        paper = shadowed(jag, 10, 6, 90)
        if s < 1: paper = paper.resize((int(paper.width * s), int(paper.height * s)), Image.BILINEAR)
        comp(c, paper, cx - paper.width / 2, slot_y - 10 * s, al, behind=True)
    slot = rrect(sw, c.H * 0.03, c.H * 0.015, (30, 30, 34, 255), (90, 90, 96, 255), 3)
    place(c, shadowed(slot, 10, 6, 140), cx, slot_y, alpha=al * clamp(c.lt / 0.15), behind=True)


@effect('moody', 'a moody colour grade: darker, softer, teal shadows')
def fx_moody(c, e):
    k = ramp(c, e, 0.35, 0)
    c.img = c.img * (1 - k) + grade(c.img, e.o.get('grade', 'moody')) * k
    vignette(c, 0.4 * k)


@effect('swipe', 'a before and after slider that sweeps across you')
def fx_swipe(c, e):
    after = grade(c.img, e.o.get('grade', 'moody'))
    p = c.lt / e.d
    sp = 1.05 - 0.95 * ease_inout(p / 0.5) if p < 0.5 else 0.1 + 0.4 * ease_inout((p - 0.5) / 0.4)
    xx, yy = grid(c)
    line = sp * c.W + 0.22 * (yy - c.H / 2)
    a = np.clip((xx - line) / 3 + 0.5, 0, 1)[..., None]
    c.img = c.img * (1 - a) + after * a
    hy = c.H * 0.62; hx = sp * c.W + 0.22 * (hy - c.H / 2)
    edge = np.clip(1 - np.abs(xx - line) / 3.5, 0, 1)[..., None]
    c.img = c.img * (1 - edge) + edge
    r = int(c.W * 0.035); h = Image.new('RGBA', (2 * r + 4, 2 * r + 4), (0, 0, 0, 0)); d = ImageDraw.Draw(h)
    d.ellipse([2, 2, 2 * r + 2, 2 * r + 2], fill=(255, 255, 255, 255))
    d.text((r + 2, r + 2), '< >', font=font('mono', r * 0.7), fill=INK + (255,), anchor='mm')
    place(c, shadowed(h, 8, 4, 110), hx, hy)
    for lab, x in (('before', 0.14), ('after', 0.86)):
        t = text_img(lab, c.W * 0.03, 'serif', INK); pill = rrect(t.width + 16, t.height, t.height / 2, (255, 255, 255, 225))
        pill.alpha_composite(t, (8, 0)); place(c, pill, c.W * x, c.H * 0.88)


@effect('todo', 'a checklist card beside your head that ticks off as you talk')
def fx_todo(c, e):
    items = e.o.get('text', 'drop your video into Claude|install the skill|type /effects').split('|')
    # ticks = video seconds when each item gets ticked (e.g. when you say it); default is evenly spaced
    ticks = [float(t) - e.start for t in str(e.o['ticks']).split('|')] if e.o.get('ticks') else [e.d * (i + 1) / (len(items) + 1) for i in range(len(items))]
    cw = int(c.W * 0.5); lh = int(cw * 0.13); pad = int(cw * 0.07)
    im = rrect(cw, pad * 2 + lh * (len(items) + 1), cw * 0.07, (250, 248, 242, 235)); d = ImageDraw.Draw(im)
    done = sum(c.lt >= t for t in ticks)
    d.text((pad, pad), e.o.get('title', 'TO DO').upper(), font=font('ui', lh * 0.42), fill=(200, 140, 20, 255))
    d.text((cw - pad, pad), f'{done} of {len(items)}', font=font('ui', lh * 0.36), fill=(120, 120, 120, 255), anchor='ra')
    f = font('ui', lh * 0.4)
    for i, it in enumerate(items):
        y = pad + lh * (i + 1); bx = lh * 0.42
        d.rounded_rectangle([pad, y + lh * 0.12, pad + bx, y + lh * 0.12 + bx], 6, outline=(160, 160, 160, 255), width=3)
        d.text((pad + bx * 1.5, y + lh * 0.1), it, font=f, fill=INK + (255,))
        if c.lt >= ticks[i]:
            k = ease_out((c.lt - ticks[i]) / 0.25)
            d.rounded_rectangle([pad, y + lh * 0.12, pad + bx, y + lh * 0.12 + bx], 6, fill=(52, 199, 89, 255))
            d.line([(pad + bx * .22, y + lh * .12 + bx * .52), (pad + bx * .42, y + lh * .12 + bx * .74), (pad + bx * .8, y + lh * .12 + bx * .28)], fill=(255, 255, 255, 255), width=4)
            tw = f.getlength(it) * k
            d.line([(pad + bx * 1.5, y + lh * 0.36), (pad + bx * 1.5 + tw, y + lh * 0.36)], fill=INK + (255,), width=3)
    left = c.fx > c.W / 2
    x = c.W * 0.05 + cw / 2 if left else c.W * 0.95 - cw / 2
    pop = ease_back(c.lt / 0.3)
    place(c, shadowed(im, 14, 8, 90), x, max(im.height / 2 + c.H * 0.06, c.fy - c.fw * 1.4), 0.8 + 0.2 * pop, 0, clamp(c.lt / 0.12) * clamp((e.d - c.lt) / 0.2), behind=True)


def heart(size, color=(255, 48, 64)):
    s = int(size); im = Image.new('RGBA', (s, s), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    pts = [(s / 2 + s * 0.48 * (16 * math.sin(t) ** 3) / 16, s * 0.46 - s * 0.46 * (13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)) / 16)
           for t in np.linspace(0, 2 * math.pi, 60)]
    d.polygon(pts, fill=color + (255,)); return im


def comment_bar(c, e):
    word = e.o.get('text', 'EFFECTS')
    bw, bh = int(c.W * 0.9), int(c.W * 0.11)
    slide = ease_out(c.lt / 0.3); y = c.H * 0.8 + (1 - slide) * c.H * 0.25
    type_t, post_t = 0.35, 0.35 + 0.08 * len(word) + 0.25
    typed = word[:int(clamp((c.lt - type_t) / (0.08 * len(word))) * len(word) + 0.001)] if c.lt < post_t else ''
    im = rrect(bw, bh, bh / 2, (255, 255, 255, 245)); d = ImageDraw.Draw(im)
    r = bh * 0.32; d.ellipse([bh * 0.2, bh / 2 - r, bh * 0.2 + 2 * r, bh / 2 + r], fill=(214, 41, 118, 255))
    f = font('ui', bh * 0.3)
    if typed: d.text((bh * 0.95, bh / 2), typed + ('|' if int(c.lt * 4) % 2 else ''), font=f, fill=INK + (255,), anchor='lm')
    elif c.lt < post_t: d.text((bh * 0.95, bh / 2), 'Add a comment...', font=f, fill=(150, 150, 150, 255), anchor='lm')
    d.text((bw - bh * 0.4, bh / 2), 'Post', font=f, fill=((0, 149, 246, 255) if typed else (180, 210, 240, 255)), anchor='rm')
    al = clamp((e.d - c.lt) / 0.2)
    place(c, shadowed(im, 14, 6, 100), c.W / 2, y, alpha=al, guard=True)
    if c.lt >= post_t:
        k = ease_back((c.lt - post_t) / 0.3)
        b = rrect(int(c.W * 0.52), int(bh * 0.85), bh * 0.3, (255, 255, 255, 240)); bd = ImageDraw.Draw(b)
        bd.text((bh * 0.3, b.height * 0.32), 'you', font=font('ui', bh * 0.2), fill=(120, 120, 120, 255), anchor='lm')
        bd.text((bh * 0.3, b.height * 0.66), word, font=font('ui', bh * 0.3), fill=INK + (255,), anchor='lm')
        hk = ease_back((c.lt - post_t - 0.3) / 0.3)
        if hk > 0:
            hh = heart(bh * 0.4 * hk); b.alpha_composite(hh, (int(b.width - bh * 0.3 - hh.width), int(b.height / 2 - hh.height / 2)))
        place(c, shadowed(b, 12, 5, 90), c.W * 0.07 + b.width / 2, y - bh * 1.05, 0.7 + 0.3 * k, 0, al * clamp((c.lt - post_t) / 0.1), guard=True)


@effect('tap', 'a Follow button pops up and flips to Following')
def fx_tap(c, e):
    at = float(e.o['at']) - e.start if 'at' in e.o else e.d * 0.45  # 'at' = video second of the tap
    bw, bh = int(c.W * 0.3), int(c.W * 0.09)
    x = clamp(float(e.o['x']) * c.W if 'x' in e.o else c.fx + c.fw * 1.9, bw / 2 + 30, c.W - bw / 2 - 30)
    y = clamp(float(e.o['y']) * c.H if 'y' in e.o else c.fy + c.fw * 1.6, bh + 30, c.H - bh - 30)
    on = c.lt >= at
    col = rgb(e.o.get('color'), (124, 92, 255)) if on else (0, 149, 246)
    im = rrect(bw, bh, bh * 0.28, col + (255,)); d = ImageDraw.Draw(im)
    d.text((bw / 2, bh / 2), 'Following' if on else '+ Follow', font=font('ui', bh * 0.4), fill=(255, 255, 255, 255), anchor='mm')
    pop = ease_back(c.lt / 0.3)
    sq = 1.0
    if on: q = (c.lt - at) / 0.3; sq = 1 - 0.12 * math.sin(math.pi * clamp(q)) if q < 1 else 1
    place(c, shadowed(im, 12, 6, 110), x, y, (0.6 + 0.4 * pop) * sq, 0, clamp(c.lt / 0.1) * clamp((e.d - c.lt) / 0.2), guard=True)
    if on and c.lt - at < 0.4:
        q = (c.lt - at) / 0.4; r = int(bh * (0.3 + 0.9 * q)); ring = Image.new('RGBA', (2 * r + 8, 2 * r + 8), (0, 0, 0, 0))
        ImageDraw.Draw(ring).ellipse([4, 4, 2 * r + 4, 2 * r + 4], outline=(255, 255, 255, int(220 * (1 - q))), width=5)
        place(c, ring, x, y, guard=True)


def hand_path(d, pts, color, width, frac):
    n = max(2, int(len(pts) * clamp(frac)))
    if frac > 0: d.line(pts[:n], fill=color, width=width, joint='curve')
    return pts[n - 1]


def arrow_pts(x0, y0, x1, y1, bend=0.25, n=40):
    mx, my = (x0 + x1) / 2 - (y1 - y0) * bend, (y0 + y1) / 2 + (x1 - x0) * bend
    return [((1 - t) ** 2 * x0 + 2 * (1 - t) * t * mx + t * t * x1, (1 - t) ** 2 * y0 + 2 * (1 - t) * t * my + t * t * y1) for t in np.linspace(0, 1, n)]


def arrow_head(d, pts, color, width, size):
    (xa, ya), (xb, yb) = pts[-4], pts[-1]; a = math.atan2(yb - ya, xb - xa)
    for s in (2.6, -2.6):
        d.line([(xb, yb), (xb + size * math.cos(a + s), yb + size * math.sin(a + s))], fill=color, width=width)


@effect('pause-point', 'freeze the frame and point at something with a hand-drawn arrow')
def fx_pause_point(c, e):
    if 'f' not in e.state: e.state['f'] = (c.img.copy(), c.m.copy(), c.fx, c.fy, c.fw)
    img, m, c.fx, c.fy, c.fw = e.state['f']; c.img, c.m = img.copy(), m
    face_cam(c, 1 + 0.06 * ease_out(c.lt / e.d), 0.4)
    c.img = c.img * 0.92 + grade(c.img, 'bw') * 0.08
    col = rgb(e.o.get('color'), YELLOW) + (255,)
    lay = Image.new('RGBA', (c.W, c.H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    d.rounded_rectangle([c.W * 0.05, c.H * 0.06, c.W * 0.05 + c.W * 0.1, c.H * 0.06 + c.W * 0.1], 16, fill=(0, 0, 0, 150))
    for bx in (0.075, 0.11): d.rectangle([c.W * bx, c.H * 0.06 + c.W * 0.025, c.W * (bx + 0.017), c.H * 0.06 + c.W * 0.075], fill=(255, 255, 255, 230))
    tx, ty = c.W * float(e.o.get('label_x', 0.72)), c.fy - c.fw * 2.2
    pts = arrow_pts(tx - c.W * 0.05, ty + c.W * 0.06, c.fx + c.fw * 0.75, c.fy - c.fw * 0.35, 0.3)
    k = ease_out((c.lt - 0.15) / 0.4)
    hand_path(d, pts, col, max(6, c.W // 140), k)
    if k >= 0.99: arrow_head(d, pts, col, max(6, c.W // 140), c.W * 0.04)
    comp(c, to_np(lay), 0, 0)
    lab = text_img(e.o.get('text', 'look here'), c.W * 0.07, 'hand', col[:3], shadow=6)
    place(c, lab, tx, ty - lab.height * 0.2, 0.7 + 0.3 * ease_back(c.lt / 0.3), -6, clamp(c.lt / 0.1), guard=True)


@effect('reject-stamp', 'a big red stamp slams onto the screen')
def fx_reject_stamp(c, e):
    word = e.o.get('text', 'REJECTED').upper(); col = rgb(e.o.get('color'), (214, 40, 40))
    def build():
        t = fit_text(word, c.W * 0.62, 'bold', 200, fill=col); pad = int(t.height * 0.12)
        im = Image.new('RGBA', (t.width + 4 * pad, t.height + 2 * pad), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        d.rounded_rectangle([3, 3, im.width - 4, im.height - 4], 18, outline=col + (255,), width=max(6, pad // 2))
        im.alpha_composite(t, (2 * pad, pad))
        a = np.asarray(im.split()[3], np.float32) * np.clip(np.random.default_rng(3).uniform(0.55, 1.6, (im.height, im.width)), 0, 1)
        im.putalpha(Image.fromarray(a.astype(np.uint8)))
        return im
    st = cached(e, 's', build)
    k = clamp(c.lt / 0.16); sc = 2.3 - 1.3 * k * k
    if 0.16 < c.lt < 0.45:
        a = (0.45 - c.lt) / 0.29 * c.W * 0.012; rnd = np.random.default_rng(int(c.t * 30))
        M = np.float32([[1, 0, rnd.uniform(-a, a)], [0, 1, rnd.uniform(-a, a)]])
        c.img = cv2.warpAffine(c.img, M, (c.W, c.H), borderMode=cv2.BORDER_REFLECT)
    y = clamp(float(e.o['y']) * c.H if 'y' in e.o else c.fy + c.fw * 2.7, 0, c.H * 0.85)
    place(c, st, c.W / 2, y, sc, float(e.o.get('angle', 12)), k * clamp((e.d - c.lt) / 0.2), guard=True)


@effect('countdown-flip', 'a 3, 2, 1 flip clock above your head')
def fx_countdown(c, e):
    n0 = int(e.o.get('from', 3)); seg = e.d / n0
    i = min(n0 - 1, int(c.lt / seg)); cur, prev = n0 - i, n0 - i + 1
    f = clamp((c.lt - i * seg) / 0.3) if i > 0 else 1.0
    tw, th = int(c.W * 0.3), int(c.W * 0.38)
    def half(num, top):
        im = rrect(tw, th, tw * 0.1, (30, 30, 34, 255)); d = ImageDraw.Draw(im)
        d.text((tw / 2, th / 2), str(num), font=font('bold', th * 0.62), fill=CREAM + (255,), anchor='mm')
        return im.crop((0, 0, tw, th // 2)) if top else im.crop((0, th // 2, tw, th))
    hv = cached(e, 'h', lambda: {(n, t): half(n, t) for n in range(0, n0 + 2) for t in (True, False)})
    im = Image.new('RGBA', (tw, th), (0, 0, 0, 0))
    im.paste(hv[(cur, True)], (0, 0)); im.paste(hv[(prev if f < 1 else cur, False)], (0, th // 2))
    if f < 0.5:
        h = max(1, int(th / 2 * (1 - 2 * f))); fl = hv[(prev, True)].resize((tw, h)); im.paste(fl, (0, th // 2 - h))
    elif f < 1:
        h = max(1, int(th / 2 * (2 * f - 1))); fl = hv[(cur, False)].resize((tw, h)); im.paste(fl, (0, th // 2))
    ImageDraw.Draw(im).line([(0, th // 2), (tw, th // 2)], fill=(0, 0, 0, 255), width=4)
    y = max(th / 2 + c.H * 0.05, c.fy - c.fw * 2.3)
    place(c, shadowed(im, 16, 10, 120), c.W / 2 * 0.6 + c.fx * 0.4, y, 0.7 + 0.3 * ease_back(c.lt / 0.3), 0, clamp((e.d - c.lt) / 0.2), behind=True)


_rect = {}


@effect('scribble', 'marker doodles draw themselves around you')
def fx_scribble(c, e):
    col = rgb(e.o.get('color'), YELLOW) + (255,); wd = max(6, c.W // 130)
    lay = Image.new('RGBA', (c.W, c.H), (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    rx, ry = c.fw * 1.0, c.fw * 1.3
    angs = np.linspace(-1.9, -1.9 + 2 * math.pi * 1.08, 70)
    ring = [(c.fx + rx * (1 + 0.04 * math.sin(3 * a)) * math.cos(a), c.fy + ry * (1 + 0.04 * math.cos(2 * a)) * math.sin(a)) for a in angs]
    hand_path(d, ring, col, wd, ease_inout(c.lt / 0.5))
    lx, ly = clamp(c.fx + c.fw * 2.3, c.W * 0.2, c.W * 0.8), max(c.H * 0.08, c.fy - c.fw * 2.4)
    pts = arrow_pts(lx - c.fw * 0.3, ly + c.fw * 0.5, c.fx + rx * 0.85, c.fy - ry * 0.75, -0.3)
    k2 = ease_out((c.lt - 0.45) / 0.35)
    if k2 > 0: hand_path(d, pts, col, wd, k2)
    if k2 >= 0.99: arrow_head(d, pts, col, wd, c.W * 0.035)
    for j, (sx, sy) in enumerate(((c.fx - c.fw * 1.9, c.fy - c.fw * 1.2), (c.fx - c.fw * 1.5, c.fy + c.fw * 0.6), (c.fx + c.fw * 1.6, c.fy + c.fw * 0.3))):
        ks = ease_back((c.lt - 0.8 - 0.1 * j) / 0.25) * c.fw * 0.28
        if ks > 0:
            d.line([(sx - ks, sy), (sx + ks, sy)], fill=col, width=wd); d.line([(sx, sy - ks), (sx, sy + ks)], fill=col, width=wd)
    al = clamp((e.d - c.lt) / 0.2)
    comp(c, to_np(lay), 0, 0, al)
    if c.lt > 0.7:
        lab = text_img(e.o.get('text', 'me!'), c.W * 0.075, 'hand', col[:3], shadow=6)
        place(c, lab, lx, ly - lab.height * 0.15, 0.7 + 0.3 * ease_back((c.lt - 0.7) / 0.3), 8, al)


# ---------- pack 2: app-style effects (added 21 Oct 2026) ----------
def pop(c, t0, dur=0.3): return ease_back((c.lt - t0) / dur) if c.lt > t0 else 0.0
def fade(c, e, t=0.2): return clamp((e.d - c.lt) / t)
GREEN, BLUE, PURPLE, ORANGE, RED = (34, 197, 94), (10, 132, 255), (124, 92, 255), (217, 119, 87), (238, 34, 34)


def glass(c, w, h, r, cx, cy, amt=0.22, tint=(255, 255, 255), blur=None, alpha=240, dark=0.0, liquid=True):
    """A glass panel made from whatever sits behind it. liquid=True (default since 27 Oct 2026) is see-through liquid
    glass after liquid-glass-js (MIT, dashersw): light blur, refraction bending the room at the rim, a red/blue fringe
    (after React Bits' GlassSurface) and a specular edge lit from the top-left. liquid=False is the old frosted card."""
    w, h = int(w), int(h); blur = blur or max(8, c.W // 40); x0, y0 = int(cx - w / 2), int(cy - h / 2)
    if not liquid:
        pad = blur * 2
        xs = np.clip(np.arange(x0 - pad, x0 + w + pad), 0, c.W - 1); ys = np.clip(np.arange(y0 - pad, y0 + h + pad), 0, c.H - 1)
        reg = cv2.GaussianBlur(np.ascontiguousarray(c.img[np.ix_(ys, xs)]), (0, 0), blur)[pad:pad + h, pad:pad + w]
        reg = reg * (1 - dark) * (1 - amt) + np.float32(tint) / 255 * amt
        im = Image.fromarray((np.clip(reg, 0, 1) * 255).astype(np.uint8)).convert('RGBA')
        m = Image.new('L', (w, h), 0); ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], int(r), fill=alpha); im.putalpha(m)
        ImageDraw.Draw(im).rounded_rectangle([1, 1, w - 2, h - 2], int(r), outline=(255, 255, 255, 120), width=max(2, c.W // 540))
        return im
    u = c.W / 2160; pad = int(140 * u) + 4
    xs = np.clip(np.arange(x0 - pad, x0 + w + pad), 0, c.W - 1); ys = np.clip(np.arange(y0 - pad, y0 + h + pad), 0, c.H - 1)
    tex = cv2.GaussianBlur(np.ascontiguousarray(c.img[np.ix_(ys, xs)]), (0, 0), max(3.0, blur * 0.3))
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32); r = max(2.0, float(r))
    q = np.stack([np.abs(xx - w / 2) - (w / 2 - r), np.abs(yy - h / 2) - (h / 2 - r)], -1)
    sdf = np.linalg.norm(np.maximum(q, 0), axis=-1) + np.minimum(np.maximum(q[..., 0], q[..., 1]), 0) - r
    d = np.maximum(-sdf, 0) / u
    nx, ny = xx - w / 2, yy - h / 2; nl = np.sqrt(nx * nx + ny * ny) + 1e-3; nx, ny = nx / nl, ny / nl
    k = (70 * np.exp(-d / 14) + 34 * np.exp(-d / 70) + 10 * np.exp(-d / 260)) * u
    out = np.zeros((h, w, 3), np.float32)
    for ch, fr in enumerate((1.10, 1.0, 0.90)):
        out[..., ch] = cv2.remap(tex[..., ch], (xx + pad + nx * k * fr).astype(np.float32), (yy + pad + ny * k * fr).astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    out = out * (1 - dark * 0.3) * 0.9 + np.float32(tint) / 255 * amt * 0.25 + 0.05 * (1.0 - 0.30 * (yy / h))[..., None] - 0.04
    spec = np.exp(-d / 5) * np.clip(0.55 - 0.45 * (nx * 0.6 + ny * 0.8), 0, 1)
    out = np.clip(out + (spec * 0.85 + np.exp(-d / 30) * 0.10)[..., None], 0, 1)
    a = (np.clip(0.5 - sdf, 0, 1) * alpha).astype(np.uint8)
    im = Image.fromarray((out * 255).astype(np.uint8)).convert('RGBA'); im.putalpha(Image.fromarray(a))
    return im


def face_chip(c, e, size):
    """A round avatar cut from your own face (grabbed once, at the start of the effect)."""
    def grab():
        r = c.fw * 0.9; x0, y0 = int(max(0, c.fx - r)), int(max(0, c.fy - r * 1.05))
        crop = c.img[y0:int(y0 + 2 * r), x0:int(x0 + 2 * r)]
        im = Image.fromarray((np.clip(crop, 0, 1) * 255).astype(np.uint8)).convert('RGBA')
        return im
    src = cached(e, 'face', grab).resize((int(size), int(size)), Image.LANCZOS)
    m = Image.new('L', src.size, 0); ImageDraw.Draw(m).ellipse([0, 0, src.width - 1, src.height - 1], fill=255); src.putalpha(m)
    return src


def lines_fit(lines, max_w, kind, start):
    size = start
    while size > 10 and max(font(kind, size).getlength(l) for l in lines) > max_w: size = int(size * 0.94)
    return size


def shift(c, dy):
    """Slide the whole picture (and you) down by dy pixels."""
    if abs(dy) < 0.5: return
    M = np.float32([[1, 0, 0], [0, 1, dy]])
    c.img = cv2.warpAffine(c.img, M, (c.W, c.H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    c.m = cv2.warpAffine(c.m, M, (c.W, c.H), flags=cv2.INTER_LINEAR); c.fy += dy


@effect('split-headline', 'a clean headline card slides down and pushes you into the bottom of the frame')
def fx_split_headline(c, e):
    k = ease_out(c.lt / 0.38) * clamp((e.d - c.lt) / 0.25)
    ch = c.H * float(e.o.get('height', 0.36))
    shift(c, ch * float(e.o.get('push', 0.72)) * k)
    top = ch * k; W = c.W; col = rgb(e.o.get('color'), GREEN)
    lay = Image.new('RGBA', (W, int(ch)), (244, 242, 236, 255)); d = ImageDraw.Draw(lay)
    lines = e.o.get('text', 'Claude|edits my|reels.').split('|'); hl = e.o.get('hl', 'edits')
    S = cached(e, 'sz', lambda: lines_fit(lines, W * 0.84, 'uib', int(W * 0.135))); f = font('uib', S)
    x0, y0 = W * 0.07, ch * 0.13
    for j, ln in enumerate(lines):
        kj = clamp((c.lt - 0.12 - 0.08 * j) / 0.18)
        if kj <= 0: continue
        y = y0 + j * S * 1.04 + (1 - ease_out(kj)) * S * 0.35; a = int(255 * kj)
        x = x0
        for wi, word in enumerate(ln.split(' ')):
            tail = '.' if word.endswith('.') else ''; core = word[:-1] if tail else word
            wl = f.getlength(core)
            if core == hl:
                hk = ease_out((c.lt - 0.42) / 0.22); pad = S * 0.12
                if hk > 0: d.rounded_rectangle([x - pad, y + S * 0.02, x - pad + (wl + 2 * pad) * hk, y + S * 1.1], S * 0.16, fill=col + (a,))
                d.text((x, y), core, font=f, fill=((255, 255, 255, a) if hk > 0.55 else (20, 20, 22, a)))
            else: d.text((x, y), core, font=f, fill=(20, 20, 22, a))
            x += wl
            if tail: d.text((x, y), tail, font=f, fill=col + (a,)); x += f.getlength(tail)
            x += f.getlength(' ') + (S * 0.12 if core == hl else 0)
    d.rectangle([0, ch - max(5, W // 180), W, ch], fill=col + (255,))
    comp(c, lay, 0, top - ch)
    pt = text_img(e.o.get('pill', 'in seconds ↗'), W * 0.034, 'uib', (255, 255, 255))
    pill = rrect(pt.width + W * 0.02, pt.height * 0.95, pt.height * 0.47, col + (255,)); pill.alpha_composite(pt, (int(W * 0.01), int(-pt.height * 0.025)))
    place(c, shadowed(pill, 10, 4, 80), W * 0.93 - pill.width / 2, top + pill.height * 0.95, 0.6 + 0.4 * pop(c, 0.62), 0, clamp((c.lt - 0.62) / 0.1) * k, guard=True)


_grad = {}


_gp = {}


@effect('headline-box', 'a punch-in with a clean two-line headline, the second line in a white box')
def fx_headline_box(c, e):
    face_cam(c, 1 + (float(e.o.get('zoom', 1.2)) - 1) * ease_out(c.lt / 0.22), 0.45)
    W = c.W; al = fade(c, e); lines = e.o.get('text', 'How I got Claude|to edit my reels.').split('|')
    S = cached(e, 'sz', lambda: lines_fit(lines, W * 0.84, 'uib', int(W * 0.085)))
    y = max(c.H * 0.06, c.fy - c.fw * 1.3 - S * 1.3 * len(lines))
    for j, ln in enumerate(lines):
        kj = clamp((c.lt - 0.1 - 0.12 * j) / 0.18)
        if kj <= 0: y += S * 1.3; continue
        boxed = j == len(lines) - 1
        t = cached(e, ('t', j), lambda: text_img(ln, S, 'uib', (16, 16, 18) if boxed else (255, 255, 255), shadow=0 if boxed else 9))
        if boxed:
            bx = rrect(t.width - S * 0.15, S * 1.22, S * 0.08, (255, 255, 255, 255))
            wk = ease_out(kj); bx = bx.crop((0, 0, max(1, int(bx.width * wk)), bx.height))
            comp(c, bx, W / 2 - (t.width - S * 0.15) / 2, y, al, guard=True)
        place(c, t, W / 2, y + S * 0.6, 0.92 + 0.08 * ease_out(kj), 0, al * kj, guard=True)
        y += S * 1.3


_emoji = {}
def emoji(ch, size):
    """A colour emoji as an RGBA image (Apple Color Emoji on a Mac). Returns None where the font is missing."""
    k = (ch, int(size))
    if k not in _emoji:
        try:
            f = ImageFont.truetype('/System/Library/Fonts/Apple Color Emoji.ttc', 160)
            im = Image.new('RGBA', (200, 200), (0, 0, 0, 0)); ImageDraw.Draw(im).text((20, 10), ch, font=f, embedded_color=True)
            im = im.crop(im.getbbox()); _emoji[k] = im.resize((int(size), int(size * im.height / im.width)), Image.LANCZOS)
        except Exception:
            _emoji[k] = None
    return _emoji[k]


def comment_sheet(c, e):
    """Reels 1021 + VOX look: an Instagram Comments sheet above your head (your hair in front). The word types in, posts,
    gets a heart, then your reply drops in with a link chip."""
    W, H = c.W, c.H; u = W / 1080; al = fade(c, e)
    word = e.o.get('text', 'EFFECTS'); handle = e.o.get('handle', 'favoritetechgal')
    reply = e.o.get('reply', 'Sent you the pack'); chip = e.o.get('chip', '20 effects')
    sw, sh = 740 * u, 450 * u
    t_post = 0.3 + 0.06 * len(word) + 0.1; t_heart, t_rep = t_post + 0.25, t_post + 0.4
    sheet = rrect(sw, sh, 30 * u, (38, 38, 40, 248)); d = ImageDraw.Draw(sheet)
    white, grey, blue = (245, 245, 245, 255), (160, 160, 166, 255), (0, 149, 246, 255)
    d.rounded_rectangle([sw / 2 - 32 * u, 14 * u, sw / 2 + 32 * u, 20 * u], 3 * u, fill=(110, 110, 116, 255))
    d.text((sw / 2, 50 * u), 'Comments', font=font('uib', 26 * u), fill=white, anchor='mm')
    d.line([(0, 80 * u), (sw, 80 * u)], fill=(60, 60, 64, 255), width=max(1, int(2 * u)))
    def avatar(sz):
        a = Image.new('RGBA', (int(sz), int(sz)), (0, 0, 0, 0)); ad = ImageDraw.Draw(a)
        ad.ellipse([0, 0, sz - 1, sz - 1], fill=(233, 90, 140, 255)); ad.text((sz / 2, sz / 2), 'V', font=font('uib', sz * 0.5), fill=(255, 255, 255, 255), anchor='mm')
        return a
    if c.lt < t_post:
        d.text((sw / 2, 190 * u), 'Start the conversation.', font=font('uim', 21 * u), fill=grey, anchor='mm')
    else:
        q = ease_out((c.lt - t_post) / 0.25); oy = (1 - q) * -20 * u; a8 = int(255 * clamp(q * 1.5))
        av = avatar(46 * u); av.putalpha(av.split()[3].point(lambda v: v * a8 // 255)); sheet.alpha_composite(av, (int(26 * u), int(100 * u + oy)))
        d.text((88 * u, 108 * u + oy), 'you', font=font('uib', 19 * u), fill=white[:3] + (a8,), anchor='lm')
        d.text((88 * u + font('uib', 19 * u).getlength('you ') + 4 * u, 108 * u + oy), 'now', font=font('uim', 18 * u), fill=grey[:3] + (a8,), anchor='lm')
        d.text((86 * u, 128 * u + oy), word, font=font('uib', 50 * u), fill=white[:3] + (a8,))
        d.text((88 * u, 196 * u + oy), 'Reply', font=font('uim', 17 * u), fill=grey[:3] + (a8,), anchor='lm')
        hk = ease_back((c.lt - t_heart) / 0.3)
        if hk > 0:
            hh = heart(30 * u * hk, (255, 48, 64)); sheet.alpha_composite(hh, (int(sw - 46 * u - hh.width / 2), int(130 * u - hh.height / 2)))
        rk = ease_out((c.lt - t_rep) / 0.25)
        if rk > 0:
            ra = int(255 * clamp(rk * 1.5)); ry = 226 * u + (1 - rk) * 16 * u; rx = 88 * u
            fc = face_chip(c, e, 34 * u); fc.putalpha(fc.split()[3].point(lambda v: v * ra // 255)); sheet.alpha_composite(fc, (int(rx), int(ry)))
            d.text((rx + 46 * u, ry + 8 * u), handle, font=font('uib', 18 * u), fill=white[:3] + (ra,), anchor='lm')
            d.text((rx + 46 * u + font('uib', 18 * u).getlength(handle) + 10 * u, ry + 8 * u), 'Author', font=font('uim', 16 * u), fill=grey[:3] + (ra,), anchor='lm')
            d.text((rx + 46 * u, ry + 36 * u), reply, font=font('uim', 22 * u), fill=white[:3] + (ra,), anchor='lm')
            gift = emoji('🎁', 24 * u)
            if gift is not None:
                g2 = gift.copy(); g2.putalpha(g2.split()[3].point(lambda v: v * ra // 255))
                sheet.alpha_composite(g2, (int(rx + 52 * u + font('uim', 22 * u).getlength(reply)), int(ry + 36 * u - g2.height / 2)))
            ck = ease_back((c.lt - t_rep - 0.12) / 0.3)
            if ck > 0:
                ct = text_img(chip, 19 * u, 'uib', (20, 20, 22)); lk = emoji('🔗', 20 * u)
                cw_ = ct.width + (lk.width + 4 * u if lk is not None else 0) + 10 * u
                cp = rrect(cw_, ct.height * 0.9, ct.height * 0.45, (255, 214, 10, 255))
                x0 = 6 * u
                if lk is not None: cp.alpha_composite(lk, (int(x0 + 4 * u), int((cp.height - lk.height) / 2))); x0 += lk.width + 4 * u
                cp.alpha_composite(ct, (int(x0), int((cp.height - ct.height) / 2)))
                cp = cp.resize((max(1, int(cp.width * (0.6 + 0.4 * ck))), max(1, int(cp.height * (0.6 + 0.4 * ck)))))
                sheet.alpha_composite(cp, (int(rx + 46 * u), int(ry + 56 * u)))
    ey = sh - 140 * u
    chars = ['❤️', '🙌', '🔥', '👏', '😢', '😍', '😮', '😂']
    for j, ch in enumerate(chars):
        im = emoji(ch, 36 * u)
        if im is not None: sheet.alpha_composite(im, (int(36 * u + j * (sw - 72 * u - 36 * u) / 7), int(ey)))
    iy = sh - 78 * u
    sheet.alpha_composite(avatar(48 * u), (int(22 * u), int(iy)))
    d.rounded_rectangle([82 * u, iy, sw - 22 * u, iy + 48 * u], 24 * u, fill=(54, 54, 58, 255))
    typed = word[:int(clamp((c.lt - 0.3) / (0.06 * len(word))) * len(word) + 1e-3)] if c.lt < t_post else ''
    if typed:
        d.text((104 * u, iy + 24 * u), typed, font=font('uib', 26 * u), fill=white, anchor='lm')
        if int(c.lt * 4) % 2: d.rectangle([104 * u + font('uib', 26 * u).getlength(typed) + 3 * u, iy + 10 * u, 106 * u + font('uib', 26 * u).getlength(typed) + 3 * u, iy + 38 * u], fill=(0, 149, 246, 255))
    else:
        d.text((104 * u, iy + 24 * u), f'Add a comment for {handle}', font=font('uim', 20 * u), fill=grey, anchor='lm')
    pressed = t_post - 0.08 <= c.lt < t_post
    d.text((sw - 44 * u, iy + 24 * u), 'Post', font=font('uib', 23 * u), fill=(blue if typed else (70, 110, 160, 255)) if not pressed else (140, 200, 255, 255), anchor='rm')
    sheet = shadowed(sheet, 22, 10, 120)
    bottom = c.fy - c.fw * 0.5; top = bottom - sheet.height
    s = 1.0
    if top < H * 0.02: s = max(0.6, (bottom - H * 0.02) / sheet.height)
    cy = bottom - sheet.height * s / 2 + 3 * u * math.sin(c.lt * 3.2)
    place(c, sheet, W / 2 * 0.5 + c.fx * 0.5, cy, s * (0.85 + 0.15 * ease_back(c.lt / 0.3)), 1.2, al * clamp(c.lt / 0.1), behind=True)


@effect('comment-box', 'an Instagram comments sheet above your head types your word, posts it, gets a heart and your reply')
def fx_comment_box(c, e):
    (comment_bar if e.o.get('look') == 'bar' else comment_sheet)(c, e)


# ---------- pack 3: showcase effects (added 23 Oct 2026) ----------


# ---------- pack 3 looks: sparkle spotlight, editorial cover, glass bento (added 23 Oct 2026) ----------
def star(size, color=(255, 244, 222)):
    """A 4-point sparkle with a soft glow."""
    s = max(8, int(size)); h = s / 2; t = s * 0.075
    im = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(im).polygon([(h, s * 0.02), (h + t, h - t), (s * 0.98, h), (h + t, h + t), (h, s * 0.98), (h - t, h + t), (s * 0.02, h), (h - t, h - t)], fill=tuple(color) + (255,))
    g = im.filter(ImageFilter.GaussianBlur(s * 0.07)); out = Image.alpha_composite(g, g); out.alpha_composite(im)
    r = s * 0.07; ImageDraw.Draw(out).ellipse([h - r, h - r, h + r, h + r], fill=(255, 255, 255, 255))
    return out


def gradient_text(s, size, kind, top, bot, glow=None):
    """Text filled with a vertical colour gradient (gold, chrome...), with an optional glow."""
    f = font(kind, size); bb = f.getbbox(s); pad = int(size * 0.25 + (glow[1] * 2.5 if glow else 0))
    w, h = bb[2] - bb[0] + 2 * pad, bb[3] - bb[1] + 2 * pad
    m = Image.new('L', (w, h), 0); ImageDraw.Draw(m).text((pad - bb[0], pad - bb[1]), s, font=f, fill=255)
    g = np.linspace(0, 1, h)[:, None, None]; col = np.float32(top) * (1 - g) + np.float32(bot) * g
    im = Image.fromarray(np.dstack([np.broadcast_to(col, (h, w, 3)).astype(np.uint8), np.asarray(m)]), 'RGBA')
    if glow:
        gl = Image.new('RGBA', (w, h), tuple(glow[0]) + (0,)); gl.putalpha(m.filter(ImageFilter.GaussianBlur(glow[1])))
        im = Image.alpha_composite(Image.alpha_composite(gl, gl), im)
    return im


def spotlight_sparkle(c, e):
    k = ramp(c, e, 0.25, 0.2); W, H = c.W, c.H
    face_cam(c, 1 + (float(e.o.get('push', 1.12)) - 1) * ease_inout(c.lt / e.d), 0.46)
    gold = np.float32(rgb(e.o.get('color'), (255, 190, 128))) / 255
    xx, yy = grid(c)
    d = ((xx - c.fx) / (W * 0.55)) ** 2 + ((yy - (c.fy + H * 0.15)) / (H * 0.5)) ** 2
    pool = np.clip(1 - d, 0, 1) ** 1.5
    c.img *= ((1 - k * (0.92 - 0.3 * pool)) * (1 - c.m) + c.m * (1 + 0.06 * k))[..., None]
    ox, oy = c.fx, c.fy - c.fw * 1.1
    q = 4; sy, sx = np.mgrid[0:H // q, 0:W // q].astype(np.float32) * q
    ang = np.arctan2(sy - oy, sx - ox); rad = np.hypot(sx - ox, sy - oy)
    rays = (0.5 + 0.5 * np.cos(16 * ang + c.lt * 0.9)) ** 5 * np.exp(-rad / (H * 0.42)) + 0.9 * np.exp(-(rad / (H * 0.2)) ** 2)
    rays = cv2.resize(rays.astype(np.float32), (W, H), interpolation=cv2.INTER_LINEAR)
    halo = np.clip(cv2.GaussianBlur(c.m, (0, 0), W * 0.012) * 1.6 - c.m, 0, 1)
    c.img += (rays * 0.32 + halo * 0.7)[..., None] * gold * k * (1 - c.m[..., None])
    word = e.o.get('text', 'CLAUDE')
    def wimg():
        size = int(H * 0.2)
        while size > 20 and font('didonei', size).getlength(word) > W * 0.86: size = int(size * 0.94)
        im = gradient_text(word, size, 'didonei', (255, 255, 250), (255, 200, 130), glow=(tuple(int(v * 255) for v in gold), size * 0.06))
        im = shadowed(im, int(size * 0.05), 0, 200)
        return np.asarray(im, np.float32) / 255
    wa = cached(e, 'w', wimg); wh, ww = wa.shape[:2]
    band = np.exp(-(((np.arange(ww)[None, :] + np.arange(wh)[:, None] * 0.5) - (-0.3 + 1.6 * clamp((c.lt - 0.25) / 0.9)) * ww * 1.3) / (ww * 0.07)) ** 2)
    w2 = wa.copy(); w2[..., :3] = np.clip(w2[..., :3] + band[..., None] * 0.9, 0, 1)
    s = 1.08 - 0.08 * ease_out(c.lt / 0.5)
    im = Image.fromarray((w2 * 255).astype(np.uint8), 'RGBA')
    place(c, im, W / 2, max(wh * 0.5 + H * 0.06, c.fy - c.fw * 1.05 - wh * 0.28), s, 0, k, behind=True)
    def spots():
        rnd = random.Random(9)
        return [(rnd.uniform(0.04, 0.96), rnd.uniform(0.07, 0.62), rnd.uniform(0.025, 0.07), rnd.uniform(0, 6.3), rnd.uniform(5, 9), rnd.random() < 0.35) for _ in range(48)]
    spr = cached(e, 'star', lambda: star(W * 0.07))
    for x, y, sz, ph, sp, front in cached(e, 'sp', spots):
        a = max(0.0, math.sin(ph + c.lt * sp)) ** 2 * k
        if a < 0.03: continue
        sc = sz / 0.07 * (0.45 + 0.75 * a)
        place(c, spr, x * W, y * H, sc, c.lt * 40 + ph * 30, a, behind=not front, guard=front)


# ---------- pack 4: over-the-shoulder zoom, messages, place-in-grid (added 27 Oct 2026) ----------
GREEN = (52, 211, 102)


def msg_bubble(c, y, title, body, a):
    """One creamy glass iMessage notification with a soft white halo, centred at height y."""
    u = c.W / 2160; w, h = int(1880 * u), int(330 * u); x0 = (c.W - w) // 2; y0 = int(y - h / 2)
    if a <= 0 or y0 + h < 0 or y0 > c.H: return
    s = 0.82 + 0.18 * ease_back(a); ww, hh = int(w * s), int(h * s); xs, ys = (c.W - ww) // 2, int(y - hh / 2)
    halo = Image.new('RGBA', (ww + int(240 * u), hh + int(240 * u)), (0, 0, 0, 0)); p = int(120 * u)
    ImageDraw.Draw(halo).rounded_rectangle([p - 30 * u, p - 30 * u, p + ww + 30 * u, p + hh + 30 * u], int(100 * u), fill=(255, 250, 240, int(215 * clamp(a * 2))))
    comp(c, halo.filter(ImageFilter.GaussianBlur(56 * u)), xs - p, ys - p)
    gx0, gy0, gx1, gy1 = max(0, xs), max(0, ys), min(c.W, xs + ww), min(c.H, ys + hh)
    if gx1 <= gx0 or gy1 <= gy0: return
    reg = cv2.GaussianBlur(c.img[gy0:gy1, gx0:gx1], (0, 0), 20 * u)
    yy = np.linspace(0, 1, gy1 - gy0, dtype=np.float32)[:, None, None]
    reg = reg * (1 - 0.78) + np.float32([252, 246, 238]) / 255 * 0.78 + (1 - yy) * 0.08
    mk = Image.new('L', (ww, hh), 0); ImageDraw.Draw(mk).rounded_rectangle([0, 0, ww - 1, hh - 1], int(70 * u * s), fill=255)
    mk = np.asarray(mk, np.float32)[gy0 - ys:gy1 - ys, gx0 - xs:gx1 - xs, None] / 255 * clamp(a * 2.5)
    dst = c.img[gy0:gy1, gx0:gx1]; dst[:] = dst * (1 - mk) + np.clip(reg, 0, 1) * mk
    lay = Image.new('RGBA', (ww, hh), (0, 0, 0, 0)); d = ImageDraw.Draw(lay); v = s * u; al = int(255 * clamp(a * 2.5))
    d.rounded_rectangle([1, 1, ww - 2, hh - 2], int(70 * v), outline=(255, 255, 255, int(170 * clamp(a * 2.5))), width=max(1, int(3 * v)))
    ic = np.linspace(0, 1, int(160 * v), dtype=np.float32)[:, None]
    icon = np.dstack([110 - ic * 64, 232 - ic * 51, 120 - ic * 51, np.full_like(ic, 255)]).repeat(int(160 * v), 1).astype(np.uint8)
    icon = Image.fromarray(icon, 'RGBA'); im_ = Image.new('L', icon.size, 0); ImageDraw.Draw(im_).rounded_rectangle([0, 0, icon.width - 1, icon.height - 1], int(40 * v), fill=al); icon.putalpha(im_)
    ImageDraw.Draw(icon).ellipse([30 * v, 34 * v, 130 * v, 114 * v], fill=(255, 255, 255, al)); ImageDraw.Draw(icon).polygon([(44 * v, 102 * v), (36 * v, 130 * v), (72 * v, 110 * v)], fill=(255, 255, 255, al))
    lay.alpha_composite(icon, (int(56 * v), int(70 * v)))
    d.text((262 * v, 76 * v), title, font=font('uib', 72 * v), fill=(28, 28, 30, al)); d.text((262 * v, 170 * v), body, font=font('uim', 76 * v), fill=(44, 44, 46, al))
    comp(c, lay, xs, ys)


@effect('messages', 'iMessage notifications pop in one after another, creamy glass with a soft glow, stacking up above the bottom of the frame')
def fx_messages(c, e):
    msgs = (e.o.get('text') or 'how did you edit this??|wait, which app is this|send me the effects pls|EFFECTS').split('|')
    title = e.o.get('title', 'Messages'); n = len(msgs); u = c.W / 2160
    gap = min(0.4, e.d * 0.75 / max(1, n)); pops = [0.13 + i * gap for i in range(n)]
    bottom = c.H * float(e.o.get('y', 0.61)); out = fade(c, e, 0.2)
    for k in range(n):
        if c.lt < pops[k]: continue
        newer = sum(ease_out(clamp((c.lt - pops[j]) / 0.17)) for j in range(k + 1, n) if c.lt >= pops[j])
        msg_bubble(c, bottom - 165 * u - newer * 365 * u, title, msgs[k], clamp((c.lt - pops[k]) / 0.17) * out)


# The full pack (27 more effects) is available from @favoritetechgal. If fx_private.py sits next to this file, its effects load too.
_PRIV = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fx_private.py')
if os.path.exists(_PRIV): exec(open(_PRIV).read(), globals())


# ---------- video in/out + tracking ----------
def probe(path):
    j = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=r_frame_rate:format=duration',
                                   '-of', 'json', path], capture_output=True, text=True, check=True).stdout)
    fr = j['streams'][0]['r_frame_rate']; num, den = fr.split('/'); fps = float(num) / float(den or 1)
    png = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-frames:v', '1', '-f', 'image2pipe', '-vcodec', 'png', '-'], capture_output=True, check=True).stdout
    h, w = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_COLOR).shape[:2]
    return (fr if fps <= 30.5 else '30'), min(fps, 30.0), float(j['format']['duration']), w, h


def read_frames(path, W, H, fr):
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', path, '-vf', f'fps={fr},scale={W}:{H}:flags=bicubic,format=rgb24', '-f', 'rawvideo', '-'],
                         stdout=subprocess.PIPE, bufsize=10 ** 8)
    n = W * H * 3
    try:
        while True:
            b = p.stdout.read(n)
            if len(b) < n: break
            yield np.frombuffer(b, np.uint8).reshape(H, W, 3)
    finally:
        if p.poll() is None: p.kill()
        p.stdout.close(); p.wait()


# ---------- added by @favoritetechgal ----------


def guided(I, p, r=8, eps=2e-3):
    box = lambda x: cv2.boxFilter(x, -1, (2 * r + 1, 2 * r + 1))
    mI, mp_ = box(I), box(p); a = (box(I * p) - mI * mp_) / (box(I * I) - mI * mI + eps); b = mp_ - a * mI
    return np.clip(box(a) * I + box(b), 0, 1)


class Tracker:
    def __init__(self, aw, ah):
        import mediapipe as mp
        from mediapipe.tasks.python import vision
        from mediapipe.tasks.python.core.base_options import BaseOptions
        self.mp = mp
        self.seg = vision.ImageSegmenter.create_from_options(vision.ImageSegmenterOptions(
            base_options=BaseOptions(model_asset_path=os.path.join(ROOT, 'models', 'selfie_segmenter.tflite')),
            running_mode=vision.RunningMode.VIDEO, output_confidence_masks=True, output_category_mask=False))
        self.fd = cv2.FaceDetectorYN.create(os.path.join(ROOT, 'models', 'yunet.onnx'), '', (aw, ah), 0.6, 0.3, 20)
        self.prev = None

    def __call__(self, rgb, ms):
        img = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        ms_ = self.seg.segment_for_video(img, ms).confidence_masks
        m = ms_[-1].numpy_view().astype(np.float32); m = m.reshape(m.shape[0], m.shape[1])
        if m.shape[:2] != rgb.shape[:2]: m = cv2.resize(m, (rgb.shape[1], rgb.shape[0]))
        m = guided(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255, m)
        m = np.clip((m - 0.5) * 1.6 + 0.5, 0, 1)
        if self.prev is not None: m = 0.65 * m + 0.35 * self.prev
        self.prev = m
        _, f = self.fd.detect(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
        face = None
        if f is not None and len(f):
            r = max(f, key=lambda r: r[2] * r[3] * r[-1]); face = (r[0] + r[2] / 2, r[1] + r[3] / 2, r[2])
        else:
            rows = np.where((m > 0.5).sum(1) > m.shape[1] * 0.01)[0]
            if len(rows):
                top = rows[0]; band = m[top:top + max(4, int(m.shape[0] * 0.06))] > 0.5; xs = np.where(band.any(0))[0]
                fw = max(8.0, (xs.max() - xs.min()) * 0.8); face = (float(xs.mean()), top + fw * 0.7, fw)
        return (m * 255).astype(np.uint8), face


def smooth(vals, fps, tau=0.18):
    idx = [i for i, v in enumerate(vals) if v is not None]
    if not idx: return None
    arr = np.array([vals[i] if vals[i] is not None else (np.nan,) * 3 for i in range(len(vals))], np.float64)
    for k in range(3):
        col = arr[:, k]; good = ~np.isnan(col); col[~good] = np.interp(np.where(~good)[0], np.where(good)[0], col[good]); arr[:, k] = col
    a = 1 - math.exp(-1 / (fps * tau))  # forward then backward pass, so the smoothing has no lag
    for i in range(1, len(arr)): arr[i] = arr[i - 1] + a * (arr[i] - arr[i - 1])
    for i in range(len(arr) - 2, -1, -1): arr[i] = arr[i + 1] + a * (arr[i] - arr[i + 1])
    return arr


class Ctx: pass


class Fx:
    def __init__(self, d, fps):
        self.name = d['fx']; self.start = float(d['start']); self.end = float(d['end']); self.d = max(0.05, self.end - self.start)
        self.o = {k: v for k, v in d.items() if k not in ('fx', 'start', 'end')}; self.state = {}; self.cards = []


def load_cards(folder, thumbs):
    out = []
    if folder and os.path.isdir(folder):
        for n in sorted(os.listdir(folder)):
            p = os.path.join(folder, n); ext = n.lower().rsplit('.', 1)[-1]
            if ext in ('jpg', 'jpeg', 'png', 'webp'): out.append(Image.open(p).convert('RGB'))
            elif ext in ('mp4', 'mov', 'm4v', 'webm'):
                cap = cv2.VideoCapture(p); cap.set(cv2.CAP_PROP_POS_MSEC, 1000); ok, fr = cap.read(); cap.release()
                if ok: out.append(Image.fromarray(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB)))
    return out or thumbs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('args', nargs='*', help='[effect] input.mp4 output.mp4')
    ap.add_argument('--plan'); ap.add_argument('--start', type=float); ap.add_argument('--end', type=float)
    ap.add_argument('--text'); ap.add_argument('--images'); ap.add_argument('--opt', action='append', default=[], help='key=value')
    ap.add_argument('--still', help='comma-separated seconds: save PNG check frames instead of a video')
    ap.add_argument('--width', type=int, default=1080, help='short side of the output (1080 default, 2160 for 4K)')
    ap.add_argument('--list', action='store_true')
    a = ap.parse_args()
    if a.list:
        for i, (k, (_, d)) in enumerate(EFFECTS.items()): print(f'{i + 1:2d}. {k:15s} {d}')
        return
    if a.plan:
        src, dst = a.args[0], a.args[1]; plan = json.load(open(a.plan))
        plan = plan.get('effects', plan) if isinstance(plan, dict) else plan
    else:
        name, src, dst = a.args[0], a.args[1], a.args[2]
        d = {'fx': name, 'start': a.start or 0.0, 'end': a.end if a.end is not None else 1e9}
        if a.text: d['text'] = a.text
        if a.images: d['images'] = a.images
        for kv in a.opt: k, v = kv.split('=', 1); d[k] = v
        plan = [d]
    for d in plan:
        d['fx'] = ALIASES.get(d['fx'].lower().lstrip('/'), d['fx'].lower().lstrip('/'))
        if d['fx'] in LOOK_NAMES: d['fx'], look = LOOK_NAMES[d['fx']]; d.setdefault('look', look)
        if d['fx'] not in EFFECTS: sys.exit(f"Unknown effect '{d['fx']}'. Run --list to see all {len(EFFECTS)}.")
    fr, fps, dur, sw, sh = probe(src)
    for d in plan: d['end'] = min(float(d['end']), dur)
    if sw <= sh: W = a.width; H = int(round(a.width * sh / sw / 2)) * 2
    else: H = a.width; W = int(round(a.width * sw / sh / 2)) * 2
    aw = 540 if sw <= sh else int(round(540 * sw / sh / 2)) * 2; ah = int(round(aw * sh / sw / 2)) * 2
    fxs = [Fx(d, fps) for d in plan]
    inwin = lambda t: any(f.start - 0.5 <= t < f.end + 0.5 for f in fxs)
    print(f'Pass 1: tracking you ({len(fxs)} effect{"s" * (len(fxs) > 1)})...', flush=True)
    trk = Tracker(aw, ah); masks, faces, thumbs = {}, [], []
    n_thumb = 10; thumb_at = {int(dur * fps * (j + 0.5) / n_thumb) for j in range(n_thumb)}
    for i, fr_ in enumerate(read_frames(src, aw, ah, fr)):
        t = i / fps
        if i in thumb_at: thumbs.append(Image.fromarray(fr_.copy()))
        if inwin(t):
            m, f = trk(fr_, int(t * 1000)); masks[i] = m; faces.append(f)
        else:
            faces.append(None); trk.prev = None
    sm = smooth(faces, fps)
    if sm is None: sm = np.tile([aw / 2, ah * 0.33, aw * 0.15], (len(faces), 1))
    for f in fxs:
        if f.name in CARD_FX: f.cards = load_cards(f.o.get('images'), thumbs)
    stills = sorted({int(round(float(s) * fps)) for s in a.still.split(',')}) if a.still else None
    enc = None
    if not stills:
        enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(fr), '-i', '-',
                                '-i', src, '-map', '0:v', '-map', '1:a:0?', '-c:v', 'libx264', '-crf', '17', '-preset', 'medium', '-pix_fmt', 'yuv420p',
                                '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', dst], stdin=subprocess.PIPE)
    print('Pass 2: adding the effects...', flush=True)
    sc = W / aw; total = int(dur * fps)
    for i, frame in enumerate(read_frames(src, W, H, fr)):
        t = i / fps
        act = [f for f in fxs if f.start <= t < f.end]
        if stills is not None and i not in stills:
            if i > stills[-1]: break
            continue
        if act:
            c = Ctx(); c.W, c.H, c.t, c.fps = W, H, t, fps
            c.img = frame.astype(np.float32) / 255.0
            m = masks.get(i)
            c.m = cv2.resize(m, (W, H), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255.0 if m is not None else np.zeros((H, W), np.float32)
            fx_, fy_, fw_ = sm[min(i, len(sm) - 1)]; c.fx, c.fy, c.fw = fx_ * sc, fy_ * sc, max(fw_ * sc, W * 0.05)
            for f in act:
                c.lt = t - f.start; EFFECTS[f.name][0](c, f)
            frame = (np.clip(c.img, 0, 1) * 255 + 0.5).astype(np.uint8)
        if stills is not None:
            out = dst if len(stills) == 1 else dst.replace('.png', f'_{t:.2f}.png')
            cv2.imwrite(out, cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)); print('saved', out)
        else:
            enc.stdin.write(frame.tobytes())
            if i % int(fps * 5) == 0: print(f'  {t:5.1f}s / {dur:.1f}s', flush=True)
    if enc: enc.stdin.close(); enc.wait(); print('Done:', dst)


if __name__ == '__main__':
    main()
