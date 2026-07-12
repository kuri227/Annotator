# Annotator

画像分類と音声分類の教師データを作る PySide6 デスクトップアプリです。1ファイルに複数のラベルを付けるマルチラベル分類に対応しています。

## 起動

```powershell
.venv\Scripts\python.exe app.py
```

## 開発環境

Python 3.10〜3.12を推奨します。

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m unittest discover -v
```

## Windows EXEの作成

```powershell
.\build.ps1
```

テスト成功後、コンソールを表示しない単体実行ファイル`dist\Annotator.exe`が生成されます。`dist`はGit管理対象外です。GitHub Releasesにはソースではなく、このEXEをリリース成果物として添付してください。

## 障害時の動作

- UIイベント内の予期しないPython例外はアプリ全体を終了させず、操作を継続します。
- アノテーションファイルは一時ファイルへ書き出してから置換するため、保存失敗時も直前の正常なファイルを保護します。
- 学習用ファイルのコピー失敗はファイル単位で隔離され、ラベル保存は継続します。
- 音声の破損・非対応形式は再生領域に表示され、別ファイルへ移動できます。
- 診断ログは`%LOCALAPPDATA%\Annotator\logs\annotator.log`へ最大1MB、バックアップ2世代で保存されます。通常の操作ログやアノテーション内容は記録しません。

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
