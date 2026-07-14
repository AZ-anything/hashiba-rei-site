# ReiVox (reivox.jp) — Claude作業ガイド

## プロジェクト概要

声優 **羽柴礼（Hashiba Rei）** のポートフォリオサイト。DLsite / らぶカルの作品カタログとYouTube動画一覧を提供する。

- **本番URL**: https://reivox.jp
- **ホスティング**: Netlify（site ID: `fefe75f4-7e86-4817-8ab3-621a19e04f56`）— GitHub連携で main への push を自動デプロイ
- **リポジトリ**: GitHub `AZ-anything/hashiba-rei-site`（**公開リポジトリ**）
- **ローカル作業場所**: `E:\Projects\ReiVox`
- **ドメイン**: reivox.jp（お名前.com → Netlify DNS）

### ⚠️ リポジトリを同期フォルダに置かないこと

OneDrive / Box / Dropbox 等の同期フォルダ配下に clone してはいけない。同期クライアントが
書き込み途中のファイルを掴み、gitの `config.lock` → `config` のリネームが飛ぶ。

2026-04-14 に実際にこれが起き、`.git/config` がスタブに、`config.lock` が座礁して、
以降すべての `git config` 書き込みが失敗する状態が **3ヶ月間** 続いた。その間 git が
使えなかったため GitHub API 経由でファイルを1個ずつ PUT する運用に迂回しており、
ローカルの作業ツリーは GitHub から135コミット遅れた化石になっていた（2026-07-15に解消）。

**バックアップは GitHub が担当する。** 同期クライアントを重ねる必要はない。

### ⚠️ 公開リポジトリである

認証情報を **絶対にコミットしない**。API ID・トークン・シークレットは GitHub Secrets に置き、
このファイルには「Secrets名」だけを書くこと。値そのものを書かない。
（2026-07-15まで、このファイルにDMM API IDが平文で書かれていた。除去済み。）

## ファイル構成

| ファイル | 役割 |
|---|---|
| `index.html` | サイト全体（HTML/CSS/JS一体、約700行） |
| `bl.html` | BL作品ページ（HTML/CSS/JS一体） |
| `works.json` | 乙女向け作品データ（170件、DLsite 169 / らぶカル 1） |
| `bl_works.json` | BL作品データ |
| `youtube.json` | YouTube動画データ（129件） |
| `request.html` | リクエストページ |
| `ogp.png` | OGP画像 |
| `check_releases.py` | 発売チェック＋発売時期・価格・レビュー更新（DLsite＋らぶカル） |
| `add_work.py` | 作品追加スクリプト（DLsite / らぶカル両対応） |
| `fetch_youtube.py` | YouTube動画取得（マージ方式・既存データ保持。2026-05-25改修済み） |
| `netlify.toml` | Netlifyリダイレクト＋セキュリティヘッダー設定 |
| `.github/workflows/check.yml` | 定時実行（毎日 0:10 JST） |
| `.github/workflows/add-work.yml` | 作品追加（workflow_dispatch, input: url） |

## 作業フロー共通ルール

### HTML/CSS変更時（**必ず守ること**）
1. Netlifyドラフトデプロイ作成
2. ドラフトURLをブラウザで開いて目視確認（スクリーンショット取得）
3. **ドラフトURLをAzに提示し、OKをもらう**（Netlifyクレジット消費を伴うため必須）
4. 承認後にGitHubへプッシュ
5. 本番デプロイ

**⚠️ 確認なしで本番デプロイは絶対禁止。** 過去にJS欠損のまま本番に出しかけた事故あり。
**⚠️ Azの承認なしの本番デプロイも禁止**（2026-06-05ルール化）。

### works.json / bl_works.json 更新時
- GitHubに直接プッシュ（ドラフト確認不要）
- Netlifyが自動デプロイする

### 新作追加フロー（DLsite / らぶカル共通）
1. AzからURLを受け取る（DLsite または らぶカル lovecul.dmm.co.jp）
2. 次のどちらか:
   - **ローカル実行**: `python add_work.py "<URL>"` → 差分を確認して commit → push
     （らぶカルの場合は環境変数 `DMM_API_ID` / `DMM_AFFILIATE_ID` が必要）
   - **GitHub Actions**: `add-work.yml` を workflow_dispatch でトリガー（input: url）
     → Secrets が自動注入され、works.json / bl_works.json 更新 → 自動コミット・プッシュ
3. URL中の `?dmmref=...` 等のトラッキングパラメータは `add_work.py` が除去し、
   canonical URL に正規化して保存する。そのまま渡してよい。

**振り分け**: URLに `/bl/` が含まれれば `bl_works.json`、それ以外は `works.json`。
`add-work.yml` は両方をステージする（2026-07-15までは `works.json` しかステージしておらず、
BL作品を追加してもワークフローが「変更なし」と判定して静かに消えるバグがあった。修正済み）。

**重複チェック**: `add_work.py` は RJ番号 / BJ番号 / cid をキーに既存エントリを検索し、
登録済みならスキップして正常終了する。「成功したのにコミットされない」場合はこれを疑う。

### らぶカル（lovecul.dmm.co.jp）

- **取得は DMMアフィリエイトAPI 経由**: `https://api.dmm.com/affiliate/v3/ItemList`
  `?site=FANZA&service=doujin&floor={floor}&cid={cid}&output=json`
- 認証: GitHub Secrets `DMM_API_ID` / `DMM_AFFILIATE_ID`
  （**2026-06-15 登録済み・2026-07-15 に実データ取得を確認**。承認待ちではない）
- floor: TL（乙女向け）= `digital_doujin_tl` / BL = `digital_doujin_bl`
  FloorList APIでフロアコード確認可能
- 検索: `keyword=羽柴礼` + floor指定で出演作を列挙。cid指定で個別取得
- 発売チェック（check_releases.py）もlovecul URLの作品はAPIで判定（毎日0:10 JSTに同乗）

#### ページ直接取得について（誤情報の訂正）

**「DMM系は日本国外IPをログインページにリダイレクトするので取得不可能」という記述が
以前このファイルにあったが、誤りだった。** 実際のリダイレクト先はログインページではなく
**年齢認証ページ**（`https://www.dmm.co.jp/age_check/...`）で、IPではなく Cookie の問題。

`age_check_done=1` を付ければページ本体が普通に取得できる（2026-07-15 実測、日本IPで確認）。

```bash
curl -sL -b "age_check_done=1" -A "<通常のUA>" "https://lovecul.dmm.co.jp/tl/-/detail/=/cid={cid}/"
# → 200 / リダイレクトなし / og:title・og:image・サークル名すべて取得可
```

現状はAPI経路が正常に動いているため**スクレイピングは不要**だが、API未掲載（発売前の
予告段階）の作品にはフォールバックとして使える。なお国外IP＋Cookieの組み合わせは未検証のため、
GitHub Actions から通るかは不明。ローカル（日本IP）では確実に通る。

- カバー画像: API は `{cid}pl.jpg`（large）を返す。手動構成する場合のパターンは
  `https://doujin-assets.dmm.co.jp/digital/voice/{cid}/{cid}pr.jpg`
  → **API経路のほうが良い画像を返すので、API取得を優先すること**

## Git / デプロイ

通常の git を使う。`git add` → `git commit` → `git push origin main` → Netlifyが自動デプロイ。

- 認証: Git Credential Manager（Windows資格情報マネージャー）に保管済み
  **リモートURLにトークンを埋め込まないこと**（コマンド出力やエラーに漏れる）

### Netlifyデプロイ API（HTML/CSS変更のドラフト確認用）

- ドラフト: `POST /api/v1/sites/{SITE_ID}/deploys` with `{"files": {"/filename": sha1}, "draft": true}`
- 本番: `draft: false`
- ファイルアップロード: `PUT /api/v1/deploys/{deploy_id}/files/{filename}`

## GitHub Actions

| ワークフロー | トリガー | 内容 |
|---|---|---|
| 発売チェック・自動更新 | cron `10 15 * * *`（0:10 JST）+ 手動 | YouTube取得 → 発売/価格/レビュー更新 → コミット |
| 作品追加 | workflow_dispatch（input: url） | add_work.py 実行 → コミット |

**⚠️ 定時実行の実際の開始時刻は 01:06〜02:24 JST。** GitHubは定時実行を低優先で捌くため
1〜2時間遅れるのが常態。0:10ちょうどに走らないのは異常ではない。

登録済み Secrets: `DMM_API_ID` / `DMM_AFFILIATE_ID`（2026-06-15）/ `YOUTUBE_API_KEY`（2026-04-04）

## DLsiteスクレイピング注意点

- 販売ページ: `<table id="work_outline">` から `販売日` / `ジャンル` を取得
- 告知ページ: `発売予定時期` / `発売予定日` のth/dtを探索
- 古い作品（RJ416376等）はJS描画で構造データなし → 手動入力
- ドメインは `girls`, `girls-drama`, `girls-touch`, `girls-drama-touch`, `maniax` を横断チェック
- APIエンドポイント `product_id/{ID}.json` は404になる（使えない）
- DLsiteは海外IPからでも取得可（らぶカルと違い年齢認証Cookieも不要）

## 作品カードのリンク仕様

- カード全体リンクは廃止。各カードに販売サイトボタンを表示（`storeButtons()`）
- works.jsonの `url` に加え、**重複販売作品は `url2` を設定すると両サイトのボタンが並ぶ**
- ボタン表記は `siteName(url)` でURL判定（dlsite.com→DLsite / lovecul.dmm.co.jp→らぶカル / 他→ストア）

## アフィリエイトリンク（2026-07-15追加）

**works.json / bl_works.json は正規URLのまま保持し、表示時に `affiliate()` が組み立てる。**
データを書き換えないので、check_releases.py / add_work.py の日次処理に影響しない。
実装は `index.html` と `bl.html` の両方（同一内容）。

| 対象 | 生成されるURL |
|---|---|
| DLsite 発売済み | `https://dlaf.jp/{区分}/dlaf/=/t/s/link/work/aid/reivox/id/{RJ|BJ}.html` |
| らぶカル | `https://al.fanza.co.jp/?lurl={URLエンコードした正規URL}&af_id=hashibarei-990&ch=api` |
| DLsite 予告(`/announce/`) | 変換しない（正規URLのまま） |

- DLsiteのアフィリエイトIDは `reivox`、ドメインは **`dlaf.jp`**（`dlsite.com` ではない）
- らぶカルのドメインは **`al.fanza.co.jp`**（`al.dmm.co.jp` ではない）
- 区分は正規URLから引き継ぐ（`girls` / `girls-drama` / `bl` で動作確認済み）

### ⚠️ 予告ページ(`/announce/`)をアフィリエイト化してはいけない

変換すると DLsite は **200 を返しながら作品ページではなくカテゴリのトップへ飛ばす**。
エラーにならないため気づけず、リンクが黙って壊れて成果も付かない。
発売時に check_releases.py が url を `/work/` に書き換えるので、**自動でアフィリエイト化される**。
（実績: 令和ちんぽ RJ01420614 が 2026-06-21 に announced→released で切り替わり、
アフィリエイトリンクが正しく作品ページに着地することを確認済み）

### らぶカルのアフィリエイトURLについて

DMMアフィリエイトの管理画面にらぶカル用のリンク作成UIは無いが、**API が `affiliateURL` を返す**。
`encodeURIComponent` で組み立てた文字列が API の返り値とバイト単位で一致することを確認済みのため、
クライアント側で生成してよい（TL / BL 両方で検証済み）。

### ⚠️ DMM Webサービスのクレジット表記

DMM Webサービス提供のAPIを利用して作成したサイトにはクレジット表記が必要。
**アフィリエイトリンクの有無に関わらず、API を使っている時点で該当する**
（check_releases.py が毎日 API から価格・レビュー・ジャンルを取得し、サイトに表示している）。

`index.html` / `bl.html` のフッター最下部に `.ft-credit` として設置済み:
`Powered by <a href="https://affiliate.dmm.com/api/">DMM.com Webサービス</a>`

`request.html` は API 由来のデータを表示していないため不要。

## サークル判定

- はねしば（羽柴礼自身のサークル）の作品はサークル名で自動判定
- `is_own` フィールドは廃止済み

## 価格・レビュー・ソート（2026-06-15追加）

- works.jsonの各作品に `price`(現価格) / `list_price`(定価) / `on_sale` / `review_count` を保持
- 取得元: DLsite単独=fsr検索結果（`.work_price`現価格 / `.strike`定価 / `.work_review`件数）、
  らぶカル・両サイト=DMM API（`prices.price` / `prices.list_price` / `review.count`）
- **DLsiteの星評価(平均)は取得不可**（検索結果は star_50 固定、個別ページはJS描画）。評価平均はDMM分のみ
- ジャンルはAPIの「専売」「独占配信」を除外（DLsite表記との一貫性）
- index.htmlのソートは `sortBySite`(タブごと独立) / SALEバッジ・価格は `makeWorkCard`
- check_releases.py の `update_prices_reviews()` が毎日0:10に価格・レビューを再取得

## キャッシュ

- GitHub raw CDN: 最大5分遅延あり
- `cache: 'no-store'` でfetchしているが、CDN側は制御不可
