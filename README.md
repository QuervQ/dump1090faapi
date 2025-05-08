# ✈️ Aircraft Tracker API

これは、ADS-B 受信データを PostgreSQL に保存し、FastAPI を通じてリアルタイムおよび履歴データを提供するアプリケーションです。

## 🚀 機能

* 1秒ごとに指定URLから航空機位置情報を取得しPostgreSQLに保存
* `GET /positions/live`：現在の航空機位置情報を取得
* `GET /positions/history`：履歴データのフィルター検索が可能（時間範囲、hex、flight、高度、範囲など）

## 🧱 使用技術

* Python
* FastAPI
* PostgreSQL
* APScheduler
* httpx
* dotenv

## 📦 セットアップ

### 1. PostgreSQL データベースを作成

```bash
createdb aircraft
```

### 2. `.env` ファイルを作成

プロジェクトルートに `.env` ファイルを作成して、以下を記載：

```env
DBUSER=your_postgres_username
DBPASSWORD=your_postgres_password
ip=http://localhost:8080/data.json  # dump1090-fa などのJSONデータのURL
```

### 3. 依存関係のインストール

```bash
pip install -r requirements.txt
```

`requirements.txt` 例：

```
fastapi
httpx
psycopg2-binary
python-dotenv
apscheduler
uvicorn
```

### 4. 起動

```bash
uvicorn main:app --reload
```

## 📡 APIエンドポイント

### `GET /`

* 簡易ヘルスチェック
* レスポンス: `{"message": "Hello World"}`

---

### `GET /positions/live`

* 現在の航空機位置情報を取得
* 外部ソースからの生データを使用

---

### `GET /positions/history`

過去の航空機位置を柔軟に検索可能。

#### クエリパラメータ例:

* `start` / `end`: データ取得の時間範囲
* `hex`: 機体識別コード
* `flight`: フライト番号
* `altitude_min`, `altitude_max`: 高度範囲
* `lat_min`, `lat_max`, `lon_min`, `lon_max`: 緯度縮彩の範囲
* `category`, `heading`: 分類、方位などの追加フィルタ

例：

```
/positions/history?hex=abc123&altitude_min=10000&altitude_max=20000
```

## 💠 データベース構造

`aircraft` テーブル：

| カラム名      | 型    | 説明                |
| --------- | ---- | ----------------- |
| hex       | TEXT | 機体識別コード (primary) |
| lat       | REAL | 緯度                |
| lon       | REAL | 縮彩                |
| flight    | TEXT | フライト番号            |
| squawk    | TEXT | スコークコード           |
| altitude  | REAL | 高度                |
| timestamp | TEXT | 取得時間 (primary)    |
| category  | TEXT | 機体カテゴリ            |
| heading   | REAL | 方位                |

## 🔄 スケジューリング

`put_positions_live` 関数が 1 秒間隔で実行され、常に最新の位置情報をデータベースに保存します。

## 📋 ライセンス

MIT ライセンス
