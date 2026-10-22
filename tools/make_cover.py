"""カイザー羅門 リール用サムネイル生成（1080×1920 PNG）

デザインの決まり
- 背景：和紙の質感の赤。左上と右下に金の筆の線
- 中央：生成りの白の長方形（直角・影なし）
- 文字：縦書きの明朝体。基本は黒、強調は深紅
- 羅門らしさ：文字の左下に深紅の角印「羅門」、その下にアカウント名
- 重要な文字は、プロフィール一覧の表示範囲（3:4 / 9:16）に収める

使い方
    python3 tools/make_cover.py covers/senwohiku.json
JSON の例
    {"name": "senwohiku",
     "columns": [{"text": "やさしい人が"},
                 {"text": "損をしない", "accent": true},
                 {"text": "七つの線引き"}]}
columns は右の行から順に並べる。accent: true の行が深紅で一回り大きくなる。
"""
import json, math, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
RED_PAPER = (176, 20, 26)    # 背景の赤（和紙）
GOLD = (214, 168, 72)        # 金の筆の線
PAPER = (250, 245, 232)      # 長方形の生成り
INK = (30, 26, 24)           # 黒
CRIMSON = (176, 18, 28)      # 深紅
FONT = '/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc'
CARD = (130, 340, 950, 1580)  # 文字を置く範囲。3:4 の一覧表示（y 240〜1680）に収まる
PAD_TOP, PAD_BOTTOM = 140, 230   # 下は角印のぶん空ける
GAP = 1.02                   # 縦方向の字間
PITCH = 1.28                 # 行の間隔（文字サイズに対する倍率）

SMALL = set('ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮ')
PUNCT = set('、。')
ROTATE = set('ー〜…')


def washi_red(seed=7):
    """赤い和紙：まだらな濃淡と、細い繊維"""
    rng = np.random.default_rng(seed)
    arr = np.zeros((H, W, 3), np.float32) + RED_PAPER
    for cell, amp in ((160, 10), (40, 6)):
        g = rng.normal(0, 1, (H // cell + 2, W // cell + 2)).astype(np.float32)
        up = np.array(Image.fromarray(((g * 40) + 128).clip(0, 255).astype(np.uint8)).resize((W + 2 * cell, H + 2 * cell), Image.BICUBIC), np.float32)[:H, :W] - 128
        arr += (up / 40 * amp)[..., None] * np.array([1, .35, .35])
    arr += rng.normal(0, 2.2, (H, W, 1))
    img = Image.fromarray(arr.clip(0, 255).astype(np.uint8))
    for col, n, lo, hi in (((214, 70, 64), 2600, 40, 110), ((120, 8, 14), 1800, 40, 100)):
        fib = Image.new('L', (W, H), 0)
        d = ImageDraw.Draw(fib)
        for _ in range(n):
            x, y, a = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(0, math.tau)
            pts = [(x, y)]
            for _ in range(int(rng.integers(5, 16))):
                a += rng.normal(0, .4); x += math.cos(a) * 8; y += math.sin(a) * 8; pts.append((x, y))
            d.line(pts, fill=int(rng.integers(lo, hi)), width=1)
        img.paste(col, (0, 0), fib.filter(ImageFilter.GaussianBlur(.7)))
    return img


def paper_card(img, box, seed=8):
    """生成りの紙：ほとんど分からない程度の繊維だけ"""
    rng = np.random.default_rng(seed)
    w, h = box[2] - box[0], box[3] - box[1]
    arr = np.zeros((h, w, 3), np.float32) + PAPER + rng.normal(0, 1.6, (h, w, 1))
    card = Image.fromarray(arr.clip(0, 255).astype(np.uint8))
    fib = Image.new('L', (w, h), 0)
    d = ImageDraw.Draw(fib)
    for _ in range(700):
        x, y, a = rng.uniform(0, w), rng.uniform(0, h), rng.uniform(0, math.tau)
        pts = [(x, y)]
        for _ in range(int(rng.integers(4, 12))):
            a += rng.normal(0, .4); x += math.cos(a) * 7; y += math.sin(a) * 7; pts.append((x, y))
        d.line(pts, fill=int(rng.integers(20, 50)), width=1)
    card.paste((226, 214, 192), (0, 0), fib)
    img.paste(card, box[:2])


def gold_arc(img, cx, cy, r, a0, a1, width, seed):
    """かすれた金の筆の線（円弧）。描き始めが太く、終わりにかすれる"""
    rng = np.random.default_rng(seed)
    k = 2
    m = Image.new('L', (W * k, H * k), 0)
    d = ImageDraw.Draw(m)
    angs = np.linspace(a0, a1, 220)
    for b in range(110):
        o = b / 109 * 2 - 1
        if rng.random() < .25:   # 毛先の抜け
            continue
        end = 1 - abs(rng.normal(0, .18)) * (.3 + abs(o))
        pts = []
        for i, a in enumerate(angs):
            t = i / (len(angs) - 1)
            w = width * (1 - .7 * t)
            if t > end or rng.random() < .012 * (1 + 5 * t):
                if len(pts) > 1:
                    d.line(pts, fill=int(200 + 55 * rng.random()), width=2 * k)
                pts = []
                continue
            rr = r + o * w / 2
            pts.append(((cx + rr * math.cos(a)) * k, (cy + rr * math.sin(a)) * k))
        if len(pts) > 1:
            d.line(pts, fill=int(200 + 55 * rng.random()), width=2 * k)
    m = m.resize((W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(.5))
    img.paste(GOLD, (0, 0), m)


def font(size):
    return ImageFont.truetype(FONT, int(size), index=0)


def draw_column(img, text, cx, top, size, color):
    d = ImageDraw.Draw(img)
    f = font(size)
    for i, ch in enumerate(text):
        cy = top + i * size * GAP + size / 2
        dx = dy = 0
        if ch in SMALL:
            dx, dy = size * .1, -size * .1
        elif ch in PUNCT:
            dx, dy = size * .55, -size * .55
        if ch in ROTATE:
            t = Image.new('L', (size * 2, size * 2), 0)
            ImageDraw.Draw(t).text((size, size), ch, font=f, fill=255, anchor='mm')
            t = t.rotate(-90, resample=Image.BICUBIC)
            img.paste(color, (int(cx - size), int(cy - size)), t)
        else:
            d.text((cx + dx, cy + dy), ch, font=f, fill=color, anchor='mm')


def sizes_for(columns):
    """各行の文字サイズ。長方形の高さと幅に収まる最大値を選ぶ"""
    inner_h = CARD[3] - CARD[1] - PAD_TOP - PAD_BOTTOM
    inner_w = CARD[2] - CARD[0] - 260
    scale = [1.18 if c.get('accent') else 1.0 for c in columns]
    base = 150
    while base > 60:
        sz = [base * s for s in scale]
        tall = max(len(c['text']) * s * GAP for c, s in zip(columns, sz))
        wide = sum(s * PITCH for s in sz)
        if tall <= inner_h and wide <= inner_w:
            return sz
        base -= 2
    return [base * s for s in scale]


def seal(img, x, y, size=104):
    d = ImageDraw.Draw(img)
    d.rectangle([x, y, x + size, y + size], fill=CRIMSON)
    f = font(size * .36)
    d.text((x + size / 2, y + size * .3), '羅', font=f, fill=PAPER, anchor='mm')
    d.text((x + size / 2, y + size * .7), '門', font=f, fill=PAPER, anchor='mm')


def make_cover(columns, out):
    img = washi_red()
    # 左上と右下に、二筋ずつの金の筆
    gold_arc(img, 760, 760, 700, math.pi * 1.0, math.pi * 1.45, 78, seed=1)
    gold_arc(img, 790, 800, 640, math.pi * 1.04, math.pi * 1.38, 34, seed=3)
    gold_arc(img, 320, 1160, 700, math.pi * .0, math.pi * .45, 78, seed=2)
    gold_arc(img, 290, 1120, 640, math.pi * .04, math.pi * .38, 34, seed=4)
    paper_card(img, CARD)
    d = ImageDraw.Draw(img)
    sz = sizes_for(columns)
    pitches = [s * PITCH for s in sz]
    cx = (CARD[0] + CARD[2]) / 2 + sum(pitches) / 2
    for c, s, p in zip(columns, sz, pitches):
        cx -= p / 2
        h = len(c['text']) * s * GAP
        top = CARD[1] + PAD_TOP + (CARD[3] - CARD[1] - PAD_TOP - PAD_BOTTOM - h) / 2
        draw_column(img, c['text'], cx, top, s, CRIMSON if c.get('accent') else INK)
        cx -= p / 2
    seal(img, CARD[0] + 44, CARD[3] - 44 - 104)
    d.text((W / 2, CARD[3] + 70), 'カイザー羅門', font=font(34), fill=PAPER, anchor='mm')
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    img.save(out)
    return out


if __name__ == '__main__':
    spec = json.load(open(sys.argv[1], encoding='utf-8'))
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join('covers', spec['name'] + '.png')
    print(make_cover(spec['columns'], out))
