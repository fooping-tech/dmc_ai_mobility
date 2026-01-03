# OLED アニメーションエディタ（Web）

1枚の画像または `.bin`（SSD1306 mono1）から、簡易タイムラインでアニメを作成できる Web 版エディタです。  
プレビュー確認後に `.bin` フレームを ZIP で書き出せます。

## 依存関係

- ブラウザのみで動作します（Python 依存なし）。

## 起動

ローカルで簡易サーバを起動します。

```bash
python3 -m http.server --directory tools/oled_preview/web_editor 8000
```

ブラウザで `http://localhost:8000` を開きます。

## 使い方（概要）

1) `Load Image` または `Load BIN` で入力を読み込み  
2) OLED サイズ・FPS・プレビュー倍率を設定  
3) Segments でタイムラインを構成（Add/Remove/Up/Down）  
4) Segment Editor で効果とパラメータを調整  
5) `Play` で確認し、`Export ZIP` で書き出し

`Composite` 表示が出ている場合は、複数の効果（例: scale + X/Y）を組み合わせている状態です。

出力先には `frame_000.bin` 形式で連番が生成されます（ZIP でダウンロード）。

## 動きのバリエーション（提案）

- **スクロール + 拡大 + 戻し**（ウェルカム）
  - scroll_up (0.6s) → zoom_in (0.4s) → zoom_out (0.4s) → hold (0.8s)
- **左右パン**
  - pan_left (0.8s) → pan_right (0.8s)
- **上下フロート**
  - pan_up (0.6s) → pan_down (0.6s) をループ
- **ゆっくりズーム**
  - zoom_in (1.5s) → hold (0.5s)
- **フェイク・パララックス**
  - scroll_left (0.7s) → hold (0.3s)

※ `zoom_pulse` は `zoom_in` + `zoom_out` の2セグメントで再現できます。

## Toon系プリセット

Segment Editor の Effect に以下を追加しています。

- `toon_pop`: 少し縮小から弾ける拡大（back_out）
- `toon_bounce_up`: 下からバウンドイン（bounce_out）
- `toon_slide_in`: 左から弾むスライドイン（back_out）
- `toon_squash`: 軽い伸縮のワブル（elastic_out）
- `toon_wobble`: ぷるぷる震える（減衰ワブル）
- `toon_recoil_in`: ぷるっと出てきて反動（弾性 + 減衰）
- `toon_dash_in`: 右から出てきてつんのめり、止まる直前に上だけ左へ跳ねて戻る

## Tips

- `Dither` をONにすると階調がある画像の見え方が改善します。
- `Fit` は `contain` / `cover` / `original` を選択できます。
- `.bin` 入力時は `Width/Height` を正しく設定してください（サイズ不一致だと読み込みエラー）。

## 旧GUIについて

旧 `tkinter` 版は `tools/oled_preview/oled_anim_editor.py` に残していますが、macOS では Tk の互換性問題が出る場合があります。

## 書き出し形式

- `.bin` は SSD1306 mono1 の raw bytes です。  
  サイズは `width * height / 8` bytes（`height` は 8 の倍数）です。
