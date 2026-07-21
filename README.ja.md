# CORE FIGHTER — バックエンド

中古買取ビジネス向けの、AI記事下書き生成・確認・承認・WordPress公開システムです。

本リポジトリは計画どおり **バックエンド一式** を実装しています。配信段階は次のとおりです。

- **第1段階（AI生成基盤）:** FastAPIバックエンド、PostgreSQL + pgvector スキーマ、画像アップロード、商品情報入力、AI画像解析、商品情報抽出、記事下書き生成、プロンプト組み立て、生成履歴。
- **第2段階（運用フロー）:** ダッシュボードデータ、買取／記事一覧、公開待機リスト、軽微編集、再生成、類似率チェック、検索・絞り込み、ジョブ／エラー履歴、WordPress REST連携（下書き・更新・公開）、承認ワークフロー。

フロントエンド（本格運用UI）は別アプリとしてこのAPIを利用します。  
簡易テスト用UIは `frontend/` に含まれます。

**言語:** [English README](./README.md) · 日本語（本ファイル）

---

## アーキテクチャ

```
フロントエンド（別アプリ / テストUI）
      │  HTTPS / JSON
      ▼
FastAPI メインバックエンド ─────────┐  同期・短時間の処理
  （認証、CRUD、検証、承認）         │  （認証、店舗、ペルソナ、買取、
      │ Job 行を作成                  │   記事編集、承認、ダッシュボード）
      ▼
Redis（ARQ）ジョブキュー
      │
      ▼
バックグラウンドワーカー ───────────┐  遅い／外部API処理
  （画像解析、記事生成、検証、       │  （OpenAI + WordPress）
   類似度、WP同期）                  │
      ▼
PostgreSQL + pgvector   OpenAI API    WordPress REST API   S3 / MinIO
```

長時間処理はすべて同じ契約（ワークフロー16）に従います。  
FastAPIがリクエストを検証 → `Job` 行を作成（正本）→ Redisにエンキュー → `job_id` を返す。  
ワーカーが受け取り、ジョブ状態を `PENDING → QUEUED → RUNNING → COMPLETED` に遷移（失敗時は `RETRYING` / `FAILED`）、結果を保存しエンティティ状態を更新。  
フロントは `GET /api/v1/jobs/{id}` でポーリングします。

### このスタックを選んだ理由

- **PostgreSQL + pgvector** — リレーショナルデータとベクトル類似検索を同一DBで運用（専用ベクトルDB不要）。OpenAI埋め込みのコサイン距離で「類似率50%未満」要件（ワークフロー7）を実現。
- **Redis + ARQ** — FastAPIのasync構成に合うジョブキュー。DB上の状態／リトライで監査可能。
- **S3 / MinIO** — 商品画像はDBではなくオブジェクトストレージに保存。

---

## プロジェクト構成

```
cw1/
├── docker-compose.yml         # db (pgvector) + redis + minio + api + worker
├── Dockerfile
├── requirements.txt
├── alembic.ini
├── .env.example
│
├── migrations/                # Alembic（async）移行環境
│   ├── env.py
│   └── versions/
│
├── scripts/
│   ├── init_db.py             # pgvector拡張・テーブル・ベクトル索引の作成
│   └── seed.py                # 初期管理者、店舗、ペルソナ、コンテンツルール
│
├── frontend/                  # 簡易テスト用 React UI（Vite）
│
└── app/
    ├── main.py                # FastAPIアプリ + lifespan
    ├── enums.py               # 状態／種別の列挙（単一ソース）
    │
    ├── core/                  # インフラ
    │   ├── config.py          # 環境変数設定（pydantic-settings）
    │   ├── database.py        # async SQLAlchemy
    │   ├── redis.py           # ARQプール
    │   ├── storage.py         # S3/MinIO
    │   ├── security.py        # JWT、パスワード、資格情報暗号化
    │   ├── logging.py
    │   └── deps.py            # 認証・RBAC
    │
    ├── models/                # SQLAlchemy ORM
    │   ├── user.py  store.py  persona.py  content_rule.py
    │   ├── purchase.py        # Purchase + PurchaseImage
    │   ├── article.py         # Article + ArticleVersion（履歴）
    │   ├── embedding.py       # PublishedCorpus + CorpusEmbedding
    │   ├── similarity.py  job.py  log.py
    │
    ├── schemas/               # Pydantic 入出力
    │
    ├── integrations/
    │   ├── openai_client.py   # 画像解析、記事生成、埋め込み
    │   └── wordpress_client.py# WP REST（メディア、投稿、タクソノミ、YARPP関連）
    │
    ├── services/
    │   ├── job_service.py
    │   ├── article_service.py
    │   ├── article_template.py# buyersbox形式のタイトル／見出し／フッター組立
    │   ├── prompt_builder.py  # ペルソナ＋ルール → プロンプト
    │   ├── validation.py
    │   └── text_utils.py
    │
    ├── api/
    │   ├── router.py
    │   └── v1/
    │       ├── auth.py  users.py  stores.py  personas.py
    │       ├── content_rules.py  purchases.py  articles.py
    │       ├── approval.py  wordpress.py  jobs.py  dashboard.py  media.py
    │
    └── workers/
        ├── settings.py
        ├── base.py
        └── handlers/
            ├── image_analysis.py     # wf 4
            ├── generation.py         # wf 5, 6, 8
            ├── similarity.py         # wf 7
            └── wordpress.py          # wf 11-15
```

---

## データモデル（概要）

| テーブル | 用途 |
|----------|------|
| `users` | アカウント＋ロール（ADMIN / STORE_MANAGER / STORE_STAFF） |
| `stores` | 店舗（スタッフ／マネージャーのスコープ）＋ `article_config` |
| `wordpress_sites` | 店舗ごとのWordPress接続（アプリパスワードは暗号化） |
| `personas` | AI文体ペルソナ（全体／店舗単位） |
| `content_rules` | 禁止語・禁止文脈、ブランドルール、構成ルール |
| `purchases` | 買取記録＋商品情報（日付・買取方法・個数など） |
| `purchase_images` | アップロード画像（記事用／詳細） |
| `articles` | ライフサイクル状態＋現行バージョン＋WP対応 |
| `article_versions` | 変更不可の版履歴（生成・再生成・編集）＋ `rendered_html` |
| `published_corpus` | 類似度比較対象の公開記事コーパス |
| `corpus_embeddings` | pgvector埋め込み |
| `similarity_results` | 類似スコア、最類似記事、重複箇所 |
| `jobs` | バックグラウンドジョブの状態／履歴 |
| `activity_logs` | 監査・投稿・エラー履歴 |

---

## ローカル起動（Docker — 推奨、フルスタック）

**PostgreSQL + Redis + MinIO + API + ワーカー + フロントエンド** をまとめて起動します。

```bash
cp .env.example .env
# シークレットを生成:
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(48))"
python -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())"
# 上記2値と OPENAI_API_KEY を .env に設定

docker compose up --build
# フロント: http://localhost:5173
# API docs: http://localhost:8000/docs
# MinIO UI: http://localhost:9001  (minioadmin / minioadmin)

# 初期管理者＋店舗／ペルソナ:
docker compose exec api python -m scripts.seed
```

ログイン: `admin@corefighter.local` / `admin12345`（`.env` の `FIRST_ADMIN_*` で変更可）

フロントコンテナはビルド済みReactをnginxで配信し、`/api` をAPIサービスへプロキシします。
## ローカル起動（Dockerなし）

PostgreSQL 16（`vector`拡張）、Redis、MinIO/S3 が必要です。

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS/Linux
pip install -r requirements.txt

cp .env.example .env              # 値を編集

python -m scripts.init_db         # 拡張・テーブル・ベクトル索引
python -m scripts.seed            # 初期データ

uvicorn app.main:app --reload                     # API
arq app.workers.settings.WorkerSettings           # ワーカー（別ターミナル）
```

### 簡易テストフロントエンド

画像アップロード → 解析 → 生成 → プレビュー用の最小React UI:

```bash
cd frontend
npm install
npm run dev
```

http://localhost:5173 を開く。シード管理者でログインし、次の流れで操作します:

1. **① 画像を追加**（メイン／記事画像・詳細画像）し、必要最低限の情報（日付・買取方法・買取場所・メーカー・商品・型式・状態など）を入力。空欄でも解析で補完されます。
2. **② 画像を解析** を押すと、買取作成・画像アップロード・AI解析を一括実行します（失敗時は同じボタンが「② 画像を再解析」に切り替わります）。
3. 解析結果を確認・修正し、**記事生成タイミングで表示される任意の追加情報**（カテゴリー・特徴／商品リスト・メモ・記事への追加指示）を入力してから **記事を生成**。
   - 商品が複数種類ある場合は、メーカー／商品名にまとめて記載するか「特徴・商品リスト（複数可）」に1行ずつ入力します。ジャンルが全く別で記事を分けたい場合は「新規テスト」で別買取として作成します。

Viteは `/api` をポート8000のFastAPIへプロキシします。

**初期ログイン:** `admin@corefighter.local` / `admin12345`  
（`.env` の `FIRST_ADMIN_*` で変更可）

シードされる店舗例: 豊平店 / 東苗穂店 / 東米里店  
シードされるペルソナ例: パワトレギャル / パワトレおじさん / 買取速報

### DBマイグレーション（Alembic）

クイックスタートは `scripts/init_db.py`。版管理されたスキーマ変更には:

```bash
alembic revision --autogenerate -m "変更内容"
alembic upgrade head
```

---

## 一連の流れ（仕様ワークフロー対応）

1. `POST /auth/login` → アクセストークン取得  
2. `POST /purchases` → 買取作成（`UNSTARTED`）*(wf 3)*  
3. `POST /purchases/{id}/images` → 記事画像・詳細画像 *(wf 3)*  
4. `POST /purchases/{id}/analyze` → `IMAGE_ANALYSIS`（メーカー／商品／型番など抽出）*(wf 4)*  
5. `PATCH /purchases/{id}` → スタッフが修正 *(wf 4)*  
6. `POST /purchases/{id}/generate` → `ARTICLE_GENERATION` → 検証 *(wf 6)* → 自動 `SIMILARITY_CHECK` *(wf 7)* *(wf 5)*  
7. `GET /articles/waiting-list` → 確認；`POST /articles/{id}/edit` または再生成 *(wf 8)*  
8. `POST /approval/{id}/submit` → `WAITING_APPROVAL` *(wf 9-10)*  
9. `POST /approval/{id}/decision`（管理者）→ 承認で `WORDPRESS_DRAFT` など *(wf 10-11)*  
10. 承認済み下書きの編集 → `WORDPRESS_UPDATE`（同一post id）*(wf 12)*  
11. `POST /wordpress/{id}/publish` → 公開・URL保存・コーパス更新 *(wf 13)*  
12. WP失敗 → `RETRYING` → `FAILED` / `WORDPRESS_ERROR`、手動 `retry` *(wf 14)*  
13. `POST /wordpress/sync` と日次cron → 類似コーパス更新 *(wf 15)*  
14. `GET /jobs/{id}` でジョブ監視、`GET /dashboard/*` でダッシュボード *(wf 16)*  
15. `GET /wordpress/{id}/related` → YARPP関連記事（公開後、YARPP REST有効時）

対話的ドキュメント: `/docs`

---

## ロール

| ロール | 権限 |
|--------|------|
| `ADMIN` | 全操作（全店舗の承認・公開を含む） |
| `STORE_MANAGER` | 自店のペルソナ／ルール管理、承認申請 |
| `STORE_STAFF` | 自店の買取登録、下書き生成・編集 |

---

## 記事生成（buyersbox EXPERIENCE形式）

生成結果は [パワフルトレードセンター EXPERIENCE](https://www.buyersbox.co.jp/experience) の運用記事に合わせます。

- **タイトル**（コードで組立）: `パワトレ{店舗}店から最新の買取情報【メーカー 商品 型式 個数】`
- **固定H2** + 赤太字「お売りいただきありがとうございました」
- **本文**のみAI生成（ペルソナ：ギャル／おじさん／買取速報）
- **定型フッター**（電話・LINE案内・店舗情報など）はテンプレートで付与
- 類似度比較は定型文を含めない本文（`body`）側で実施

OpenAIチューニング（`.env`）: `OPENAI_TEMPERATURE` / `OPENAI_MAX_TOKENS` / penalty 等。

---

## デプロイについての注意

- **フロント（Vite）** → Vercel などに載せやすい  
- **API＋ワーカー＋Postgres(pgvector)＋Redis＋ストレージ** → Vercel単体には不向き（長時間ワーカー／DBが必要）。Railway / Render / Fly.io / VPS などと分離構成が現実的です。
