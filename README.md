# Annotator

画像分類と音声分類の教師データを作る PySide6 デスクトップアプリです。1ファイルに複数のラベルを付けるマルチラベル分類に対応しています。

## 起動

```powershell
.venv\Scripts\python.exe app.py
```

## 推奨プロジェクト構成

```text
project/
├─ raw_data/       # 未加工の画像・音声（サブフォルダも検出）
├─ input_data/     # ラベル済みファイルの学習用コピー
└─ annotations/
   ├─ image_labels.csv
   └─ audio_labels.csv
```

音声は WAV / MP3 / FLAC / OGG / M4A / AAC を検出・再生します。波形の抽出表示は、追加依存なしで確実に扱える PCM WAV に対応しています。

## アノテーションの操作

- `Space`: 再生 / 一時停止
- `J` / `L`: 5秒戻る / 進む
- 波形またはシークバーをクリック: 任意位置へ移動
- `1`〜`9`, `0`: ラベルの選択・解除（複数選択可）
- `Enter`: 選択中のラベルを確定して次へ
- `S`: 保留して次へ
- `←` / `→`: 前後のファイル
- `Ctrl+S`: 保存

CSV/JSONのキーには `raw_data` からの相対パスを保存するため、同名ファイルをサブフォルダで管理できます。

## アノテーション形式

CSVは`filename,labels`の2列です。`labels`にはJSON配列を格納するため、カンマや日本語を含むラベルも安全に保存できます。

```csv
filename,labels
animals/sample.wav,"[""Dog"", ""Cat""]"
```

以前の`filename,label`形式の単一ラベルCSVと、値が文字列になっているJSONも引き続き読み込めます。
