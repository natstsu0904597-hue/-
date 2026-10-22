"""カイザー羅門 リール用サムネイル生成（1080×1920 PNG）

デザインの決まり
- 背景：明るく上品な黄金色の単色（グラデーション・質感なし）
- 中央：白の帯を上から下まで縦に通す（直角・影なし）。左右に黄金色が見える
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
import json, os, sys
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
GOLD = (233, 184, 74)        # 背景の黄金色
PAPER = (253, 251, 245)      # 長方形の白（真っ白より少しだけ温かい）
INK = (30, 26, 24)           # 黒
CRIMSON = (150, 22, 34)      # 深紅
FONT = '/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc'
CARD = (130, 340, 950, 1580)  # 文字を置く範囲。3:4 の一覧表示（y 240〜1680）に収まる
PAD_TOP, PAD_BOTTOM = 140, 230   # 下は角印のぶん空ける
GAP = 1.02                   # 縦方向の字間
PITCH = 1.28                 # 行の間隔（文字サイズに対する倍率）

SMALL = set('ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮ')
PUNCT = set('、。')
ROTATE = set('ー〜…')


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
    img = Image.new('RGB', (W, H), GOLD)
    d = ImageDraw.Draw(img)
    d.rectangle([CARD[0], 0, CARD[2], H], fill=PAPER)
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
    d.text((W / 2, CARD[3] + 70), 'カイザー羅門', font=font(34), fill=INK, anchor='mm')
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    img.save(out)
    return out


if __name__ == '__main__':
    spec = json.load(open(sys.argv[1], encoding='utf-8'))
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join('covers', spec['name'] + '.png')
    print(make_cover(spec['columns'], out))
