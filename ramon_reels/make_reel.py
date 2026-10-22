#!/usr/bin/env python3
"""カイザー羅門 Instagramリール作成ツール

使い方:
    python3 make_reel.py reels/001_furimawasarenai/reel.json
    python3 make_reel.py reels/001_furimawasarenai/reel.json --bgm assets/bgm/曲.mp3

reel.json の文章・背景・BGMを書き換えると、同じデザインで別のリールが作れる。
出力先: output/<id>/  (MP4・カバーPNG・確認用画像)
"""
import argparse
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
W, H = 1080, 1920
BG_SCALE = 1.1  # 背景はゆっくりズームする分だけ大きめに作る

FONT_REGULAR = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc"
FONT_BOLD = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"

# ブランドカラー
CRIMSON = (142, 27, 32)        # 深紅（カバー用）
CRIMSON_ON_DARK = (214, 74, 64)  # 暗い帯の上で読める赤（本編の数字・罫線）
KINARI = (240, 232, 216)       # 生成り
SUMI = (24, 20, 18)            # 墨

# Instagramの画面に重なる部分（本編の文字はこの内側に置く）
SAFE_TOP = 290
SAFE_BOTTOM = 1480   # 下はキャプション・ユーザー名が乗る
SAFE_RIGHT = 900     # 右下に「いいね」などのボタンが乗る
SAFE_LEFT = 90

KANJI_NUM = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]


def font(path, size):
    return ImageFont.truetype(path, int(round(size)), index=0)


# ---------------------------------------------------------------- 背景

def smooth_noise(h, w, cell, rng, octaves=4):
    """なめらかなノイズ（霧や木の葉の形に使う）。0〜1"""
    out = np.zeros((h, w), np.float32)
    amp, total = 1.0, 0.0
    for _ in range(octaves):
        sh, sw = max(2, h // cell + 2), max(2, w // cell + 2)
        small = Image.fromarray(rng.random((sh, sw)).astype(np.float32), "F")
        out += amp * np.asarray(small.resize((w, h), Image.BICUBIC))
        total += amp
        amp *= 0.5
        cell = max(2, cell // 2)
    return np.clip(out / total, 0, 1)


def procedural_sando(seed):
    """寺の参道（杉並木・石畳・灯籠・遠くの鳥居・朝霧・木漏れ日）を描く。

    写真素材が使えない時の仮の背景。AI生成ではなくプログラムで描いた図形。
    戻り値: (背景RGB画像, 動かす霧のRGBA画像)
    """
    rng = np.random.default_rng(seed)
    bw, bh = int(W * BG_SCALE), int(H * BG_SCALE)
    vx, vy = bw * 0.5, bh * 0.40      # 消失点
    f, hc = 1100.0, 1.6               # 焦点距離(px)・目の高さ(m)
    fog_col = np.array([0.87, 0.88, 0.84], np.float32)

    def fogf(z):
        return 1.0 - np.exp(-np.asarray(z, np.float32) / 14.0)

    def mix(c, z):
        k = float(fogf(z))
        return tuple(int(255 * ((1 - k) * c[i] + k * fog_col[i])) for i in range(3))

    ys, xs = np.mgrid[0:bh, 0:bw].astype(np.float32)

    # 空と霧（上は少し暖かい光）
    t = ys / bh
    img = np.zeros((bh, bw, 3), np.float32)
    top = np.array([0.80, 0.83, 0.79], np.float32)
    hor = np.array([0.95, 0.92, 0.84], np.float32)
    k = np.clip(t / 0.40, 0, 1)[..., None]
    img[:] = top * (1 - k) + hor * k

    # 地面：石畳と苔
    ground = ys > vy + 1
    Z = np.where(ground, f * hc / np.maximum(ys - vy, 1), 1e4)
    X = (xs - vx) * Z / f
    on_path = ground & (np.abs(X) < 1.5)
    row = np.floor(Z / 0.55)
    col = np.floor((X + (row % 2) * 0.3) / 0.6)
    hsh = np.sin(row * 12.9898 + col * 78.233) * 43758.5453
    var = (hsh - np.floor(hsh)) * 0.08 - 0.04 + (smooth_noise(bh, bw, 6, rng, 2) - 0.5) * 0.08
    joint = (np.mod(Z / 0.55, 1) < 0.07) | (np.mod((X + (row % 2) * 0.3) / 0.6, 1) < 0.05)
    stone = np.stack([0.40 + var, 0.39 + var, 0.36 + var], -1)
    stone[joint] *= 0.82
    moss = np.array([0.15, 0.19, 0.11], np.float32) + smooth_noise(bh, bw, 40, rng)[..., None] * 0.06
    gcol = np.where(on_path[..., None], stone, moss)
    fz = fogf(Z)[..., None]
    gcol = gcol * (1 - fz) + fog_col * fz
    img = np.where(ground[..., None], gcol, img)

    base = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8), "RGB")
    d = ImageDraw.Draw(base)

    def sx(Xw, z):
        return vx + f * Xw / z

    def sy(Yw, z):
        return vy + f * (hc - Yw) / z

    # 遠い鳥居（ブランドの赤をかすかに）
    zt = 30.0
    tc = mix((0.55, 0.16, 0.12), zt)
    for side in (-1, 1):
        x = sx(side * 1.7, zt)
        w2 = f * 0.16 / zt
        d.rectangle([x - w2, sy(5.0, zt), x + w2, sy(0, zt)], fill=tc)
    d.rectangle([sx(-2.4, zt), sy(5.25, zt), sx(2.4, zt), sy(4.95, zt)], fill=tc)  # 笠木
    d.rectangle([sx(-2.0, zt), sy(4.35, zt), sx(2.0, zt), sy(4.15, zt)], fill=tc)  # 貫

    # 杉並木と灯籠（遠い順に描く）
    objs = []
    for side in (-1, 1):
        z = 2.0
        while z < 60:
            objs.append(("tree", side * (2.0 + rng.random() * 0.9), z, 0.6 + rng.random() * 0.5))
            if rng.random() < 0.7:
                objs.append(("tree", side * (3.4 + rng.random() * 3), z + rng.random() * 2, 0.5 + rng.random() * 0.5))
            z += 2.0 + rng.random() * 2.4
        z = 4.0
        while z < 40:
            objs.append(("lantern", side * 1.75, z, 0))
            z += 6.0
    objs.sort(key=lambda o: -o[2])

    for kind, Xw, z, wd in objs:
        if kind == "tree":
            dark, lit = mix((0.09, 0.08, 0.07), z), mix((0.20, 0.16, 0.12), z)
            x, half = sx(Xw, z), f * wd / 2 / z
            yb = sy(0, z)
            d.polygon([(x - half, yb), (x - half * 0.8, -10), (x + half * 0.8, -10), (x + half, yb)], fill=dark)
            d.polygon([(x + half * 0.25, yb), (x + half * 0.2, -10), (x + half * 0.8, -10), (x + half, yb)], fill=lit)
        else:
            c = mix((0.30, 0.29, 0.27), z)
            x = sx(Xw, z)

            def box(wm, y0, y1):
                d.rectangle([x - f * wm / 2 / z, sy(y1, z), x + f * wm / 2 / z, sy(y0, z)], fill=c)
            box(0.60, 0.0, 0.18)
            box(0.22, 0.18, 1.05)
            box(0.50, 1.05, 1.15)
            box(0.40, 1.15, 1.55)
            d.polygon([(x - f * 0.42 / z, sy(1.55, z)), (x + f * 0.42 / z, sy(1.55, z)),
                       (x + f * 0.12 / z, sy(1.80, z)), (x - f * 0.12 / z, sy(1.80, z))], fill=c)
            d.ellipse([x - f * 0.07 / z, sy(1.95, z), x + f * 0.07 / z, sy(1.80, z)], fill=c)

    img = np.asarray(base).astype(np.float32) / 255

    # 木の葉（上部）。すき間から光がもれる
    n = smooth_noise(bh, bw, 220, rng, 6)
    dens = np.clip((0.36 * bh - ys) / (0.36 * bh), 0, 1) ** 0.7
    canopy = np.clip((n * 0.8 + dens * 0.75 - 0.75) * 5, 0, 1)[..., None]
    leaf = np.array([0.06, 0.10, 0.06], np.float32) + (smooth_noise(bh, bw, 30, rng, 3)[..., None] - 0.5) * 0.05
    img = img * (1 - canopy * 0.92) + leaf * canopy * 0.92

    # 地平線の朝霧
    band = np.exp(-((ys - vy - 0.03 * bh) / (0.16 * bh)) ** 2) * (0.55 + 0.45 * smooth_noise(bh, bw, 120, rng))
    img = img * (1 - band[..., None] * 0.42) + fog_col * band[..., None] * 0.42

    # 光の筋（右上から）
    lx, ly = bw * 0.80, -bh * 0.06
    ang = np.arctan2(ys - ly, xs - lx)
    a_n = (ang - ang.min()) / (ang.max() - ang.min() + 1e-6)
    ray1d = smooth_noise(1, 2048, 40, rng, 3)[0]
    rays = ray1d[(a_n * 2047).astype(int)] ** 4
    dist = np.hypot(xs - lx, ys - ly)
    rays = rays * np.exp(-dist / (1.0 * bh)) * (1 - canopy[..., 0] * 0.85)
    rays8 = Image.fromarray((np.clip(rays, 0, 1) * 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(10))
    rays = np.asarray(rays8).astype(np.float32) / 255 * 1.1
    warm = np.array([1.0, 0.93, 0.78], np.float32)
    img = 1 - (1 - img) * (1 - np.clip(rays, 0, 1)[..., None] * warm * 0.45)

    # 石畳の木漏れ日
    spots = Image.new("L", (bw, bh), 0)
    sd = ImageDraw.Draw(spots)
    for _ in range(90):
        Xw, z = rng.uniform(-2.5, 2.5), rng.uniform(1.6, 14)
        x, y = sx(Xw, z), sy(0, z)
        rx = f * rng.uniform(0.12, 0.35) / z
        ry = rx * hc / z * 0.9
        sd.ellipse([x - rx, y - ry, x + rx, y + ry], fill=int(rng.uniform(90, 200)))
    spots = np.asarray(spots.filter(ImageFilter.GaussianBlur(14))).astype(np.float32) / 255
    spots *= ground * (1 - fogf(Z) * 0.8)
    img = img + spots[..., None] * warm * 0.16

    # 仕上げ：やわらかさ・周辺減光・粒子
    vig = 1 - 0.35 * (((xs - bw / 2) / (bw / 2)) ** 2 * 0.5 + ((ys - bh / 2) / (bh / 2)) ** 2 * 0.5)
    img = img * vig[..., None]
    lum = img.mean(-1, keepdims=True)
    img = img + (1 - lum) * np.array([-0.01, 0.01, -0.005], np.float32) + lum * np.array([0.02, 0.01, -0.02], np.float32)
    img = np.clip((img - 0.5) * 1.08 + 0.5, 0, 1) * 0.94 + 0.03
    img += rng.normal(0, 0.012, img.shape).astype(np.float32)
    base = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8), "RGB")
    base = base.filter(ImageFilter.GaussianBlur(1.6))

    # 流れる霧（横長に作って、ゆっくり横に動かす）
    fw = bw * 2
    fn = smooth_noise(bh, fw, 160, rng, 4)
    fy = np.mgrid[0:bh, 0:fw][0].astype(np.float32)
    prof = np.exp(-((fy - vy - 0.10 * bh) / (0.28 * bh)) ** 2) + 0.5 * np.exp(-((fy - bh) / (0.18 * bh)) ** 2)
    alpha = np.clip((fn - 0.35) * 1.6, 0, 1) * prof * 0.55
    fog = np.zeros((bh, fw, 4), np.uint8)
    fog[..., :3] = (fog_col * 255).astype(np.uint8)
    fog[..., 3] = (np.clip(alpha, 0, 1) * 255).astype(np.uint8)
    fog_img = Image.fromarray(fog, "RGBA").filter(ImageFilter.GaussianBlur(8))
    return base, fog_img


def cover_fit(im, w, h):
    s = max(w / im.width, h / im.height)
    im = im.resize((math.ceil(im.width * s), math.ceil(im.height * s)), Image.LANCZOS)
    x, y = (im.width - w) // 2, (im.height - h) // 2
    return im.crop((x, y, x + w, y + h))


def camera(t, motion):
    """t=0〜1 のときの、背景の切り出し倍率と中心の位置"""
    e = t * t * (3 - 2 * t) * 0.35 + t * 0.65  # 端だけ少しなめらかに
    if motion == "zoom_out":
        return 1.07 - 0.07 * e, 0.5, 0.5
    if motion == "pan_up":
        return 1.0, 0.5, 0.52 - 0.04 * e
    if motion == "pan_down":
        return 1.0, 0.5, 0.48 + 0.04 * e
    return 1.0 + 0.07 * e, 0.5, 0.5 - 0.02 * e  # zoom_in（少し奥へ進む）


def crop_box(size, zoom, cx, cy):
    """背景のどこを切り出すか（幅・高さ・左上）"""
    bw, bh = size
    cw, ch = bw / zoom, bh / zoom
    x0 = min(max(cx * bw - cw / 2, 0), bw - cw)
    y0 = min(max(cy * bh - ch / 2, 0), bh - ch)
    return cw, ch, x0, y0


def view(im, box, dx=0.0):
    cw, ch, x0, y0 = box
    return im.transform((W, H), Image.AFFINE, (cw / W, 0, x0 + dx, 0, ch / H, y0), Image.BICUBIC)


# ---------------------------------------------------------------- 文字

def soft_shadow(layer, radius=6, strength=0.65):
    a = layer.getchannel("A").filter(ImageFilter.GaussianBlur(radius))
    a = a.point(lambda v: int(v * strength))
    sh = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    sh.putalpha(a)
    return sh


def text_overlay(cfg):
    """本編の文字・半透明の帯を1枚の透明PNGにする"""
    items = cfg["items"]
    titles = cfg["title_lines"]
    closing = cfg.get("closing_lines", [])
    sig = cfg.get("signature")
    if not 1 <= len(items) <= 10:
        sys.exit("items は1〜10個にしてください")

    scale = 1.0
    while True:
        S = {"title": 68 * scale, "item": 50 * scale, "close": 46 * scale, "close_last": 58 * scale, "sig": 28 * scale}
        ft = font(FONT_BOLD, S["title"])
        fi = font(FONT_REGULAR, S["item"])
        fn = font(FONT_BOLD, S["item"])
        fc = font(FONT_BOLD, S["close"])
        fcl = font(FONT_BOLD, S["close_last"])
        fs = font(FONT_REGULAR, S["sig"])
        num_w = max(fn.getlength(KANJI_NUM[i] + "、") for i in range(len(items)))
        block_w = num_w + max(fi.getlength(s) for s in items)
        widest = max([block_w] + [ft.getlength(s) for s in titles] + [fc.getlength(s) for s in closing])
        step = S["item"] * 1.72
        hgt = (60 + len(titles) * S["title"] * 1.38 + 30 + 52 + len(items) * step + 34 + 50
               + sum((S["close_last"] if i == len(closing) - 1 else S["close"]) * 1.62 for i in range(len(closing)))
               + (30 + S["sig"] * 1.4 if sig else 0) + 54)
        if hgt <= SAFE_BOTTOM - SAFE_TOP and widest <= 2 * (SAFE_RIGHT - W / 2) - 20:
            break
        scale *= 0.96

    top = SAFE_TOP + (SAFE_BOTTOM - SAFE_TOP - hgt) * 0.45
    px0, px1 = 96, 984

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).rounded_rectangle([px0, top, px1, top + hgt], radius=28, fill=150)
    mask = mask.filter(ImageFilter.GaussianBlur(14))
    panel = Image.new("RGBA", (W, H), (8, 8, 10, 255))
    panel.putalpha(mask)
    layer = Image.alpha_composite(layer, panel)

    txt = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(txt)
    white = (250, 248, 242, 255)
    y = top + 60
    for s in titles:
        y += S["title"] * 1.38
        d.text((W / 2, y), s, font=ft, fill=white, anchor="ms")
    y += 30
    d.line([(W / 2 - 60, y), (W / 2 + 60, y)], fill=CRIMSON_ON_DARK + (255,), width=3)
    y += 52
    x0 = W / 2 - block_w / 2
    for i, s in enumerate(items):
        y += step
        d.text((x0, y - step * 0.22), KANJI_NUM[i] + "、", font=fn, fill=CRIMSON_ON_DARK + (255,), anchor="ls")
        d.text((x0 + num_w, y - step * 0.22), s, font=fi, fill=white, anchor="ls", stroke_width=1, stroke_fill=white)
    y += 34
    # 区切り：細い線と小さな菱形
    d.line([(W / 2 - 150, y), (W / 2 - 16, y)], fill=(255, 255, 255, 110), width=1)
    d.line([(W / 2 + 16, y), (W / 2 + 150, y)], fill=(255, 255, 255, 110), width=1)
    d.polygon([(W / 2, y - 7), (W / 2 + 7, y), (W / 2, y + 7), (W / 2 - 7, y)], fill=CRIMSON_ON_DARK + (255,))
    y += 50 - S["close"] * 0.3
    for i, s in enumerate(closing):
        last = i == len(closing) - 1
        y += (S["close_last"] if last else S["close"]) * 1.62
        d.text((W / 2, y), s, font=fcl if last else fc, fill=white, anchor="ms")
    if sig:
        y += 30 + S["sig"] * 1.4
        d.text((W / 2, y), "— " + sig, font=fs, fill=(240, 232, 216, 200), anchor="ms")

    layer = Image.alpha_composite(layer, soft_shadow(txt))
    return Image.alpha_composite(layer, txt)


# ---------------------------------------------------------------- カバー

def vertical_text(d, text, cx, y, f, fill, step):
    """縦書き。1文字ずつ中央にそろえて下へ並べる"""
    for ch in text:
        d.text((cx, y + step / 2), ch, font=f, fill=fill, anchor="mm")
        y += step
    return y


def make_cover(cfg, out_path):
    k = 2  # 2倍で描いて縮小（線をなめらかにする）
    cw, ch = W * k, H * k
    rng = np.random.default_rng(3)

    # 生成りの紙
    ys, xs = np.mgrid[0:ch, 0:cw].astype(np.float32)
    n = smooth_noise(ch, cw, 60, rng, 5)
    paper = np.array(KINARI, np.float32)[None, None] + (n[..., None] - 0.5) * 14
    v = (((xs - cw / 2) / (cw / 2)) ** 2 + ((ys - ch / 2) / (ch / 2)) ** 2) / 2
    paper -= v[..., None] * np.array([18, 24, 30], np.float32)
    im = Image.fromarray(np.clip(paper, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    fib = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    fd = ImageDraw.Draw(fib)
    for _ in range(1400):
        x, y = rng.uniform(0, cw), rng.uniform(0, ch)
        a, L = rng.uniform(0, math.pi), rng.uniform(10, 50)
        fd.line([(x, y), (x + L * math.cos(a), y + L * math.sin(a))], fill=(120, 100, 80, 22), width=1)
    im = Image.alpha_composite(im, fib)
    d = ImageDraw.Draw(im)

    # 細い枠（4:5の範囲に収める）
    m = 70 * k
    d.rectangle([m, 300 * k, cw - m, ch - 300 * k], outline=SUMI + (200,), width=2 * k)
    d.rectangle([m + 12 * k, 312 * k, cw - m - 12 * k, ch - 312 * k], outline=CRIMSON + (170,), width=1 * k)

    # 赤い糸（羅＝絡まりのモチーフ）
    pts = []

    def bez(p0, p1, p2, p3, nseg=200):
        for i in range(nseg + 1):
            t = i / nseg
            pts.append(tuple((1 - t) ** 3 * a + 3 * (1 - t) ** 2 * t * b + 3 * (1 - t) * t * t * c + t ** 3 * e
                             for a, b, c, e in zip(p0, p1, p2, p3)))
    lp = (215 * k, 1250 * k)
    bez((110 * k, 430 * k), (330 * k, 560 * k), (60 * k, 950 * k), lp)
    r = 62 * k
    for i in range(121):
        a = -math.pi / 2 + 2 * math.pi * i / 120
        pts.append((lp[0] + r * math.cos(a), lp[1] + r + r * math.sin(a)))
    bez(lp, (420 * k, 1560 * k), (760 * k, 1480 * k), (990 * k, 1600 * k))
    thread = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    td = ImageDraw.Draw(thread)
    td.line(pts, fill=CRIMSON + (235,), width=4 * k, joint="curve")
    im = Image.alpha_composite(im, thread)
    d = ImageDraw.Draw(im)

    # 縦書きタイトル（右の列から読む）
    cols = cfg["cover"]["columns"]
    acc = cfg["cover"].get("accent_column", len(cols) - 1)
    sizes = [112 if i != acc else 132 for i in range(len(cols))]
    widths = [s * 1.5 for s in sizes]
    total_w = sum(widths)
    x = W / 2 + total_w / 2
    y_top = 400
    hanko_at = None
    for i, text in enumerate(cols):
        x -= widths[i] / 2
        f = font(FONT_BOLD, sizes[i] * k)
        start = y_top + (0 if i == 0 else sizes[0] * 1.9)
        end = vertical_text(d, text, x * k, start * k, f, (CRIMSON if i == acc else SUMI) + (255,), sizes[i] * 1.06 * k)
        if i == acc:
            hanko_at = (x, end / k + 40)
        x -= widths[i] / 2

    # 落款（羅門）
    if hanko_at:
        hx, hy = hanko_at
        s = 92
        d.rounded_rectangle([(hx - s / 2) * k, hy * k, (hx + s / 2) * k, (hy + s) * k], radius=8 * k, fill=CRIMSON + (255,))
        fh = font(FONT_BOLD, 36 * k)
        d.text((hx * k, (hy + s * 0.30) * k), "羅", font=fh, fill=KINARI + (255,), anchor="mm")
        d.text((hx * k, (hy + s * 0.72) * k), "門", font=fh, fill=KINARI + (255,), anchor="mm")

    sig = cfg.get("signature")
    if sig:
        fsig = font(FONT_REGULAR, 34 * k)
        d.text((W / 2 * k, 1575 * k), "  ".join(sig), font=fsig, fill=SUMI + (220,), anchor="mm")

    im = im.resize((W, H), Image.LANCZOS).convert("RGB")
    im.save(out_path)
    return im


# ---------------------------------------------------------------- 書き出し

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("ffmpegでエラー:\n" + r.stderr[-2000:])


def encode(cfg, overlay, out_mp4, bgm):
    fps = cfg.get("fps", 30)
    dur = float(cfg.get("duration_sec", 20))
    bg = cfg.get("background", {})
    btype = bg.get("type", "procedural")
    tmp_overlay = out_mp4.parent / "_overlay.png"
    overlay.save(tmp_overlay)

    audio_in, audio_map = [], []
    if bgm:
        b = cfg.get("bgm", {})
        vol, fi, fo = b.get("volume", 0.6), b.get("fade_in_sec", 1.5), b.get("fade_out_sec", 2.0)
        audio_in = ["-stream_loop", "-1", "-i", str(bgm)]
        afilter = f"volume={vol},afade=t=in:d={fi},afade=t=out:st={dur - fo}:d={fo}"
    else:
        audio_in = ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
        afilter = "anull"
    venc = ["-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
            "-profile:v", "high", "-r", str(fps), "-movflags", "+faststart",
            "-c:a", "aac", "-b:a", "192k", "-t", str(dur)]

    if btype == "video":
        cmd = ["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(ROOT / bg["file"]), "-i", str(tmp_overlay), *audio_in,
               "-filter_complex",
               f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps},setsar=1[bg];"
               f"[bg][1:v]overlay=0:0[v];[2:a]{afilter}[a]",
               "-map", "[v]", "-map", "[a]", *venc, str(out_mp4)]
        run(cmd)
        tmp_overlay.unlink()
        return

    if btype == "image":
        base = cover_fit(Image.open(ROOT / bg["file"]).convert("RGB"), int(W * BG_SCALE), int(H * BG_SCALE))
        fog = None
    else:
        print("背景を描いています…")
        base, fog = procedural_sando(bg.get("seed", 7))

    n = int(round(dur * fps))
    cmd = ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
           *audio_in, "-filter_complex", f"[1:a]{afilter}[a]", "-map", "0:v", "-map", "[a]", *venc, str(out_mp4)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    motion = bg.get("motion", "zoom_in")
    for i in range(n):
        t = i / max(1, n - 1)
        z, cx, cy = camera(t, motion)
        box = crop_box(base.size, z, cx, cy)
        frame = view(base, box).convert("RGBA")
        if fog is not None:
            shift = (fog.width - base.width) * (0.20 + 0.12 * t)  # 霧はゆっくり横へ流れる
            frame = Image.alpha_composite(frame, view(fog, box, shift))
        frame = Image.alpha_composite(frame, overlay)
        p.stdin.write(frame.convert("RGB").tobytes())
        if i % 60 == 0:
            print(f"  {i}/{n} コマ")
    p.stdin.close()
    err = p.stderr.read().decode(errors="ignore")
    if p.wait() != 0:
        sys.exit("ffmpegでエラー:\n" + err[-2000:])
    tmp_overlay.unlink()


def check_images(mp4, out_dir, dur):
    for name, t in (("check_1_start", 0.5), ("check_2_middle", dur / 2), ("check_3_end", dur - 0.5)):
        run(["ffmpeg", "-y", "-ss", str(t), "-i", str(mp4), "-frames:v", "1", str(out_dir / f"{name}.png")])
    # Instagramの画面が重なる部分を赤で示した確認画像
    im = Image.open(out_dir / "check_2_middle.png").convert("RGBA")
    z = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(z)
    red = (230, 40, 40, 90)
    d.rectangle([0, 0, W, SAFE_TOP - 70], fill=red)
    d.rectangle([0, SAFE_BOTTOM + 60, W, H], fill=red)
    d.rectangle([SAFE_RIGHT + 60, 1050, W, SAFE_BOTTOM + 60], fill=red)
    f = font(FONT_BOLD, 34)
    d.text((W / 2, 110), "ここは画面上部のUIが重なる", font=f, fill=(255, 255, 255, 255), anchor="mm")
    d.text((W / 2, 1760), "ここはキャプション・名前が重なる", font=f, fill=(255, 255, 255, 255), anchor="mm")
    Image.alpha_composite(im, z).convert("RGB").save(out_dir / "check_4_safezone.png")


def main():
    ap = argparse.ArgumentParser(description="カイザー羅門 リール作成")
    ap.add_argument("config", help="reel.json のパス")
    ap.add_argument("--bgm", help="BGMの音声ファイル（reel.json の bgm.file より優先）")
    ap.add_argument("--cover-only", action="store_true", help="カバー画像だけ作る")
    a = ap.parse_args()

    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg が見つかりません")
    cfg_path = Path(a.config).resolve()
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    out = ROOT / "output" / cfg["id"]
    out.mkdir(parents=True, exist_ok=True)

    make_cover(cfg, out / "cover.png")
    print("カバー画像:", out / "cover.png")
    if a.cover_only:
        return

    bgm = a.bgm or (cfg.get("bgm") or {}).get("file")
    bgm = (ROOT / bgm) if bgm and not Path(bgm).is_absolute() else (Path(bgm) if bgm else None)
    mp4 = out / ("reel_bgm.mp4" if bgm else "reel_nobgm.mp4")
    encode(cfg, text_overlay(cfg), mp4, bgm)
    check_images(mp4, out, float(cfg.get("duration_sec", 20)))
    print("動画:", mp4)


if __name__ == "__main__":
    main()
