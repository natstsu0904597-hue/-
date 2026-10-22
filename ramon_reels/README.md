# カイザー羅門 Instagramリール作成ツール

文章・背景・音楽を差し替えるだけで、同じデザインのリールを作れます。

## フォルダの中身

| 場所 | 中身 |
|---|---|
| `make_reel.py` | 動画とカバー画像を作るプログラム |
| `reels/<番号_名前>/reel.json` | 1本ごとの設定（文章・背景・音楽） |
| `assets/backgrounds/` | 背景に使う写真・動画を置く場所 |
| `assets/bgm/` | BGMを置く場所（利用条件を確認できた曲だけ） |
| `output/<番号_名前>/` | 完成品（MP4・カバーPNG・確認用画像） |

## 作り方

```
python3 make_reel.py reels/001_furimawasarenai/reel.json
```

できあがるもの（`output/001_furimawasarenai/`）

- `reel_nobgm.mp4` … BGMなしの完成動画（BGMを入れると `reel_bgm.mp4`）
- `cover.png` … リールのカバー画像
- `check_1_start.png` / `check_2_middle.png` / `check_3_end.png` … 冒頭・中盤・終盤の確認用
- `check_4_safezone.png` … Instagramの画面表示が重なる場所を赤で示した確認用

カバーだけ作り直す時は `--cover-only` を付けます。

## 2本目を作る時

1. `reels/001_furimawasarenai` フォルダをコピーして名前を変える（例：`002_gaman`）
2. 中の `reel.json` を書き換える
   - `id` … フォルダ名と同じにする（出力先の名前になります）
   - `title_lines` … タイトル（1行ずつ）
   - `items` … 一覧（1〜10個。番号「一、二、…」は自動で付きます）
   - `closing_lines` … 締めの言葉（最後の行が大きくなります）
   - `cover.columns` … カバーの縦書きタイトル（右の列から順に）
3. 上のコマンドで作る

項目が多い時は、文字の大きさが自動で小さくなります。

## 背景の差し替え

`reel.json` の `background` を書き換えます。

| type | 使い方 |
|---|---|
| `"procedural"` | プログラムで描いた参道（今の仮の背景） |
| `"image"` | 写真1枚をゆっくり動かす。`"file": "assets/backgrounds/写真.jpg"` |
| `"video"` | 撮った動画をそのまま使う。`"file": "assets/backgrounds/動画.mp4"` |

`motion` は `zoom_in`（奥へ進む）・`zoom_out`・`pan_up`・`pan_down` から選べます（写真と描いた背景のみ）。

## BGMの追加

利用条件（商用利用・Instagram投稿が可能か）を確認できた曲だけを使います。

```
python3 make_reel.py reels/001_furimawasarenai/reel.json --bgm assets/bgm/曲.mp3
```

または `reel.json` の `bgm.file` に曲の場所を書きます。音量（`volume`）と、始まり・終わりのフェード秒数も変えられます。

BGMなしの動画をそのまま投稿し、Instagramアプリの「音楽を追加」で曲を付ける方法もあります。

## 使っているもの

- フォント：Noto Serif CJK JP（SIL Open Font License。商用利用可・動画への埋め込み可）
- 必要なソフト：Python 3（Pillow・NumPy）、ffmpeg
- フォントが入っていないパソコンでは `make_reel.py` 上部の `FONT_REGULAR` / `FONT_BOLD` をフォントの場所に書き換えてください
