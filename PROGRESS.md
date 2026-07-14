# ReiVox 作業進捗

最終更新: 2026-06-26

## 2026-06-26セッションで完了した作業

### 新作追加（乙女向け・予告）
- 「【ねこみみ】「だーめ…逃がさないよ。」あざといツンデレ獣人キャストが求めてくる!?寸止めいたずらでイキがまん〈けもみみランド〜発情期の店員さん〜/BELL〉」（RJ01653647, mimimoto）を追加
  - 取得元: DLsite girls/announce ページ（product.jsonは予告段階で空 `[]`、og:title＋work_outlineテーブルから抽出）
  - シナリオ: 阿佐ヶ谷かんろ / イラスト: だお。 / 声優: 羽柴礼（確認済み）
  - ジャンル: 獣人, ラブラブ/あまあま, ツンデレ, 焦らし, 乳首責め, 中出し, 耳舐め, ネコミミ
  - status: announced（予告開始日 2026-06-25。**発売予定時期の記載なし**→date/release_period空。発売後は日次チェックで自動補完）
  - cover: https://img.dlsite.jp/modpub/images2/ana/doujin/RJ01654000/RJ01653647_ana_img_main.jpg
  - works.json を GitHub直プッシュ（commit 69e0023b）、total 169→170。Netlify自動デプロイ

## 2026-06-22セッションで完了した作業

### RJ01420614「令和ちんぽ」(ナイスベルト) を販売中に更新
- announced→released、url を /announce/ → /work/、cover/genres(フタナリ)/price660/date(2026-06-22) を反映
- 取得は DLsite `product.json?workno=RJ...`（girls）で genres まで取得可能と判明（work_outlineがJS描画でも有効）
- works.json を GitHub直プッシュ（commit e42c21b6）

### BL専用ページ bl.html を新規作成（A案=別ページ・完全分離）
- **名義: 羽柴 令（Hashiba Rei、乙女向けの羽柴礼とは別漢字・同読み）**
- **配色: C案 チャコール×エレクトリックブルー**（乙女向けの緑＋ゴールドとパッと見で差別化）
  - :root を青系に、navのみダークチャコール(rgba(23,31,43,.96))＋白ロゴ＋#60A5FAアクセントに上書き
- フォーマットは乙女向け最新版(index.html)を流用：新着・予告ピックアップ／Worksのソート・サイトタブ(DLsite/らぶカル)・両ボタン・価格/SALE・ジャンル絞り込み・検索
  - filterから「はねしば/他サークル」は除去（BLに該当なし）
  - データ取得元を works.json → **bl_works.json** に変更、fallbackは空配列
- 相互導線: index.html のナビ(乙女向け作品/BL作品)・冒頭プロフィール文・フッターにBLリンク追加。bl.htmlからは乙女向けへ
- 手順遵守：Netlifyドラフト→ブラウザ目視→Az承認→本番（reivox.jp/bl.html 確認済み）
  - commit: bl.html 72bc0ef2 / index.html 5925d317、Netlify本番デプロイ済み

### BL作品データ bl_works.json を新規作成（6件、commit d71e9533）
- DLsite6件: RJ01495796(予告/7月下旬,アロイ亭) / RJ01567225(執事長,ヴァント-wand-) / RJ01556715(若社長,K-DRIVE!) /
  RJ01235601(《ノンケ》,アロイ亭) / RJ01081969(あふたーまっちんぐ,vleugel) / RJ412144(まっちんぐ,vleugel)
- らぶカル2件は既存DLsite作品と同一と判明し url2 統合：
  - d_736407 = RJ01567225（執事長） / d_774341 = RJ01235601（《ノンケ》）→ 両ボタン化
- 取得: DLsiteは product.json(genres/price) + 作品ページのJSON-LD(aggregateRating=レビュー件数)、
  らぶカルは DMM API `floor=digital_doujin_bl`（認証は GitHub Secrets `DMM_API_ID` / `DMM_AFFILIATE_ID`）
- スキーマは works.json と同一（title/circle/url/url2/cover/date/status/release_period/genres/price/list_price/on_sale/review_count）

### BL自動化対応（check_releases.py / add_work.py / check.yml）✅
- **check_releases.py を CONFIGS で works.json と bl_works.json の両方を処理するよう拡張**（commit a9f9b01b）
  - 乙女: DLsite girls系 / DMM digital_doujin_tl / 検索キーワード「羽柴礼」
  - BL: DLsite bl / DMM digital_doujin_bl / 検索キーワード「羽柴令」
  - get_actual_release_date を product.json優先（work_outlineフォールバック）に改善。新作でも発売日・ジャンル取得可
  - 価格/レビューはDLsite fsr(.work_review=書込レビュー数) + DMM両取りでmax。乙女と同指標に統一
- **add_work.py をURL自動振り分けに**（commit 6e28e141）: `/bl/` を含むURL→bl_works.json、それ以外→works.json
  - DLsite bl / らぶカルbl(floor=digital_doujin_bl) も判別。**「この作品追加して＋URL」だけで乙女/BL自動判定**
  - 価格(product.json/DMM prices)も追加時に取得。重複チェックはurl/url2両方
- **check.yml の git add に bl_works.json 追加**（commit 8c04b2ea）。毎日0:10 JSTで両ファイル更新
- workflow_dispatch で手動実行し success 確認済み（run 27912172618）
- bl_works.json のレビュー件数を乙女と同指標(書込レビュー数: 6/5/56/26/42)に補正（commit 2570dcdc）

### 年齢確認ゲート（18禁クッション）追加 ✅
- index.html / bl.html / request.html の全3ページに `<div id="age-gate">` オーバーレイ＋inline scriptを `<body>` 直後に挿入
- 仕様: 初回アクセスで全員に表示（来訪元問わず）→「はい」で localStorage `reivox_age_verified=1` を保存し次回以降非表示／「いいえ」で羽柴YouTube(UCn3tBA3UvmDtB_0LyKEG-hA)へ遷移
- ボタン色は `var(--green,#4D7052)` で各ページのテーマに自動追従（乙女=緑 / BL=青）。記憶はドメイン共通
- SEO影響なし（コンテンツはDOMに残しJSオーバーレイのみ）。commit: index ccbcf428 / bl 0a90eeff / request 2ea99c55、本番反映済み
- ※「Xからは一切出さない」要望が出たら、Xリンクに ?from=x を付けてスキップする方式を追加可能（現状は初回全員表示方式）

### ⚠️ 残る注意点
- BL予告 RJ01495796(7月下旬発売)は、発売されれば日次チェックで自動的にreleased化される（手動不要に）
- アバター画像は乙女向けと共用（羽柴令専用アイコンがあれば bl.html の avatar src を差し替え）
- らぶカル予告（DMM API未掲載）作品の手動追加が必要なケースは従来通り（タイトル/カバーをAzから受領）

### ローカルgitクローンの状態
- 作業フォルダ(OneDrive)のローカルcloneは GitHub main より大きく遅れている（last local commit 2c59ad8）。
  真実はGitHub側。編集はRead/Edit/Write＋GitHub APIプッシュで実施。bash側マウントは文字数とバイト数の違いに注意（破損ではない）

## 2026-06-15セッションで完了した作業

### DMM API有効化＆らぶカル統合（前半）
- API認証: GitHub Secrets `DMM_API_ID` / `DMM_AFFILIATE_ID`（アフィリエイトIDは末尾990必須）→ 設定済み
- フロアコード: らぶカルTL = `digital_doujin_tl`（BLは digital_doujin_bl）。add_work.py / check_releases.py 修正済み
- `keyword=羽柴礼`(digital_doujin_tl)で46件取得。HP未掲載8件を新規追加→DLsite版を検索統合
- DLsite既存37件にらぶカルurl2を追加 → **両サイト販売作品45件が両ボタン化**
- 記号(♡/×)差で重複登録された5件を解消（元エントリ優先、今回追加分を削除）。total 169

### 価格・レビュー機能＋ソート・サイトタブUI（後半）
- **全作品に price/list_price/on_sale/review_count を付与**（161件価格、96件セール中、149件レビュー）
  - らぶカル/両サイト: DMM API（prices.price=セール価格, list_price=定価, review.count）
  - DLsite単独: fsr検索結果スクレイピング（.work_price=現価格, .strike=定価, .work_review=レビュー件数）
  - クーポンは除外（ログイン固有のため元々含まれない）。ジャンルから「専売」「独占配信」除外
- **index.html UI実装**（commit 588ab1f6, 本番反映済み）:
  - サイト別タブ（すべて/DLsite/らぶカル、`sortBySite`でタブごとに独立ソート）
  - ソート7種: 新着順/発売日古い順/価格安い・高い順/割引率が高い順/レビューが多い順/サークル順
  - SALEバッジ（赤リボン）＋「○%OFF ¥現価格 ¥定価(打消し)」表示
  - **評価★順は削除**（DLsite作品の星評価が取得不可＝16件しかデータ無く誤解を招くため）
- ピックアップ(予告・新着)カードにも価格・SALE表示を追加（commit 8e38fcc5）。priceBlock()で共通化
- **価格・レビューの日次更新を check_releases.py に組み込み**（commit c24c7e62）
  - fetch_dlsite_prices() / fetch_dmm_prices() / update_prices_reviews() を追加
  - 毎日0:10の発売チェックに相乗り。GitHub Actions手動実行で動作確認済み
- ⚠️ DLsiteの星評価(average)は検索結果で star_50 固定・個別ページはJS描画で取得不可。
  レビューは「件数」のみ両サイト取得可能（評価平均はDMM分のみ）

### 残課題・次の候補
- **アフィリエイトリンク化**: reivox（reivox.jp）のDLsiteアフィリエイト審査が「掲載可」になれば、
  works.jsonのDLsite URLをID `reivox` 付きリンクに一括変換でHP全体が収益化（リンク経由の全購入が報酬対象）。
  らぶカルも DMM affiliateURL(al.fanza.co.jp経由)で収益化可能。リンク形式は要確認(guide/affiliate/link)

## 過去セッション履歴

## 2026-06-05セッションで完了した作業

### らぶカル（lovecul.dmm.co.jp）対応 🆕
- 新作追加先としてDLsiteに加え**らぶカル**をサポート
- **重要な技術的制約**: らぶカルはDMM系のため**日本国外IPを全てログインページにリダイレクト**する。
  Claudeのfetch環境・GitHub Actions・ブラウザ自動操作のいずれも取得不可（DLsiteは海外IP可なので従来通り）
- 解決策: **DMMアフィリエイトAPI**（api.dmm.com、海外IPから疎通確認済み）
  - `site=FANZA&service=doujin&floor=digital_doujin&cid={cid}` でタイトル・サークル・発売日・ジャンル・カバーを取得
- **⏳ AzがDMMアフィリエイト登録済み、承認待ち。承認後にAPI ID/アフィリエイトIDをもらい、
  GitHub Secretsに `DMM_API_ID` / `DMM_AFFILIATE_ID` を設定して動作確認すること**（次セッションの最優先タスク）

### add_work.py + add-work.yml 新規作成
- 「作品追加して＋URL」共通フロー用スクリプト（DLsite/らぶカル両対応）
- GitHub Actions `add-work.yml`（workflow_dispatch, input: url）で実行
  - トリガー: `POST /repos/.../actions/workflows/add-work.yml/dispatches` with `{"ref":"main","inputs":{"url":...}}`
- DLsite: 販売ページ→告知ページの順で探索しスクレイピング
- らぶカル: DMM API（Secrets未設定時はエラーで案内表示）
- works.json更新規則はcheck_releases.pyと同一（announced先頭・released日付降順、total/updated_at更新）

### check_releases.py らぶカル対応
- pending作品のうち `lovecul.dmm.co.jp` URLはDMM APIで発売チェック（毎日0:10 JSTの既存cronに同乗）
- 発売検知時: status→released、date・release_period・genres・cover をAPI値で更新
- Secrets未設定の間はスキップ（ログに警告表示、他作品のチェックには影響なし）

### 新作追加
- 「嘘つきワンナイト 俺、最初からお姉さんしか狙ってないよ」（d_775012, parasite garden, らぶカル）を追加
  - status: announced（予告開始 2026-06-05、発売日未定）、ジャンル12件
  - API承認待ちのため、Azのスクショ＋カバーURL提供から手動構成（commit: 99d639c4）
  - カバー: https://doujin-assets.dmm.co.jp/digital/voice/d_775012/d_775012pr.jpg
  - 発売日・正式データはAPI設定後の毎日チェックで自動補完される

### 作品カードを「販売サイトボタン」形式に変更
- pickup/Works両方のカードを「カード全体リンク」→「販売サイトボタンで遷移」に変更（Azの要望）
- `storeButtons(w)` 関数: `w.url` と `w.url2`（任意・新フィールド）からボタンを生成
  - 1サイト→「DLsiteで見る」等のフル表記、2サイト→「DLsite」「らぶカル」の短縮表記で横並び
- **DLsite/らぶカル重複販売作品は works.json に `url2` を追加すれば両ボタンが自動表示される**
- ドラフト→目視確認→本番の手順遵守（commit: 3f353d7c）、reivox.jp確認済み

### 作品カードのボタンをサイト別表記に変更
- pickupカードの「DLsiteで見る」固定 → `siteName(url)` 関数でURL判定（dlsite.com→DLsite /
  lovecul.dmm.co.jp→らぶカル / その他→ストア）して「○○で見る」を動的表示
- 手順遵守: Netlifyドラフト→ブラウザ目視確認→GitHubプッシュ（commit: 67c19933）→本番デプロイ
- reivox.jp本番で表示確認済み

### 既知の注意点（今回判明）
- **Linuxサンドボックスのマウント同期遅延**: OneDrive上の作業フォルダはbash側から見ると
  編集直後のファイルが破損して見えることがある（null埋め/切り詰め）。
  ファイル編集はRead/Edit/Writeツール、GitHubプッシュは/tmpにクリーンコピーを作って行うこと

## 過去セッション履歴

## 2026-05-31セッション完了作業

### 新作追加

### 新作追加
- 「初恋・初体験のカレに囲われ逃げられない。～地元で再会した憧れの先輩に全てを見抜かれ堕とされえっち～」（RJ01636650, おふとんハムスター, 2026-05-31発売）を追加
  - 声優: 羽柴礼 / シナリオ: 芽生遊 / イラスト: 木花ゆな / 音楽: 如月夢羽
  - ジャンル: ヤンデレ, クンニ, クリ責め, 潮吹き, 執着攻め, 中出し, 耳舐め
  - status: released（販売日当日）
  - works.jsonをGitHubプッシュ（commit: 9a8c3281）
  - GitHub raw CDN反映確認済み

## 過去セッション履歴

## 2026-05-25セッション完了作業

### check_releases.py 改修
- 発売時期→発売日の変更検知機能を追加
- 従来: `release_period`が空の時のみDLsiteから取得
- 改修後: 毎回チェックし、「4月下旬」→「4月17日」のような具体化を検知・更新
- GitHubプッシュ済み（commit: 5e2e9a7f）

### GitHub Actions ワークフロー修正
- **原因**: `.github/workflows/check.yml`に`actions/checkout@v4`が欠落
- **影響**: 4/16から毎日failし続けていた（リポジトリファイルが取得されずfetch_youtube.pyが見つからないエラー）
- **修正**: checkoutステップ追加（commit: 334d638f）
- **結果**: 手動実行で成功確認済み
- **副作用**: ⚠️ fetch_youtube.pyが走り、123件に拡充していたyoutube.jsonが50件に退行（下記参照）

### トークンスコープ更新
- GitHub Personal Access Tokenに`workflow`スコープを追加
- `.github/workflows/`配下のファイルをAPI経由でプッシュ可能に

### 新作追加
- 「西園寺様の仰せのままに〜絶倫御曹司の求愛セックス〜」（RJ01561078, LOVEpoppo, 5月上旬）を追加（commit: 330520ac）

### 発売チェック実行
- RJ01599651「おとなりさん」の発売時期を「4月下旬」→「4月17日」に更新（commit: 87dacd9c）

### ドキュメント作成
- CLAUDE.md / FEATURES.md / PROGRESS.md を新規作成

### YouTube youtube.json データ復旧 ✅
- チャンネルページスクレイピング（lockupViewModel構造）で全動画を再取得
- yt-dlpで公開動画の正確な日付取得、メン限はチャンネルページから相対日付→推定日付
- 127件（動画63 / 歌5 / ライブ47 / ショート12）、メンバー限定63件
- GitHubプッシュ済み（commit: 9bd59dfc）

### fetch_youtube.py マージ方式に改修 ✅
- 既存youtube.jsonを読み込み、新規動画のみ追加する方式に変更
- members_onlyフラグ等の手動データを保持
- GitHubプッシュ済み（commit: 3194b165）

## 未着手・要対応

### ✅ DMM API有効化＆らぶカル出演作の追加（2026-06-15完了）
- **API認証情報**: GitHub Secrets `DMM_API_ID` / `DMM_AFFILIATE_ID`（値はSecretsのみ。ドキュメントに書かないこと）
  （※末尾は990〜999必須。最初もらった`-001`は広告枠用でAPI不可）→ GitHub Secrets設定済み
- **正しいフロアコード**: らぶカルTLは `floor=digital_doujin_tl`（`digital_doujin`では0件）
  - BLは `digital_doujin_bl`。FloorList APIで確認可能
  - add_work.py / check_releases.py のfloorを修正済み
- `keyword=羽柴礼`（digital_doujin_tl）で46件ヒット。works.jsonとタイトル照合し:
  - ★HP未掲載8件 → Az出演確認OK → 新規追加（commit 46bc5b65）
  - 嘘つきワンナイト(d_775012) → 発売済み補完（commit dd547cf9）
  - 残り37件 = DLsite版がHP既存 → **url2追加候補（未実施・下記）**
- ジャンルはAPIのgenreから「専売」「独占配信」を除外（DLsite作品との一貫性）
- 現在 total 174件 / らぶカル9件

### ✅ DLsite×らぶカル両ボタン化 完了（2026-06-15）
- DLsite既存37件にらぶカルurl2を追加（commit cb3fcf66）
- らぶカル新規8件もDLsite版を検索統合（url=DLsite主体, url2=らぶカル）:
  - お隣のひとたらし=RJ01623962 / 悪魔と淫紋=RJ01150463 / 残響=RJ01536440 /
    大好きな君との=RJ01518901 / ミッドナイト・テラス エピソード0=RJ01529394 /
    Vol.03=RJ01485344 / Vol.02=RJ01468454 / ネトスト=RJ01415154
- **嘘つきワンナイト(d_775012)のみDLsiteに無し → らぶカル単独維持**
- 現在: total 174 / 両ボタン(url2あり)45件 / らぶカル単独1件
- DLsite検索はbash requestsでスクレイピング可能（fsr検索: keyword=サークル名→作品一覧→正規化照合）。
  ♡等の記号差で自動照合を逃すことがあるので、漏れたらシリーズ名で再検索

### 💰 アフィリエイト収益化（調査済み・未実装）
**DLsiteアフィリエイト**: サイト登録すれば「リンク経由なら紹介作品以外の全購入も報酬」（クッキー方式・取りこぼしなし）。
  これはAzが求めた「サイト設定→経由購入が収益」に合致。
  - 料率: ボイス・ASMR 7.5% / マンガ・CG・ノベル 12.5%
  - 開始: ユーザー登録 or サークル登録（はねしば）→ アフィリエイト申請（サイト審査あり。無断転載等は不承認）
  - 実装: 承認後、works.jsonのDLsite URLをアフィリエイトリンク形式に変換すればHP全体が収益化
  - 注意: aタグhref改変不可（装飾は可）/ 自己購入は対象外 / サークルはポイント受取だと50%加算対象外（現金推奨）
  - リンク形式の詳細: https://www.dlsite.com/girls/guide/affiliate/link （承認後に確認）
**らぶカル(DMM)**: 既にアフィリエイトID `hashibarei-990` 取得済み。APIレスポンスの `affiliateURL`(al.fanza.co.jp経由)
  を使えばらぶカルリンクも収益化可能。works.jsonのlovecul URLをaffiliateURLに置換する形。

### 🟡 リポジトリ清掃
- `detect_new_works.py` — 廃止済み、削除推奨
- `check.yml.new` — 不要な残骸、削除推奨

### 🟡 メンバー限定ページ（構想段階）
- YouTubeメンバーシップ連動の限定コンテンツページ
- 方式案: トークン自動ローテーション or YouTube OAuth
- Azと相談中、まだ設計段階

## 過去セッション履歴

### 2026-04-15
- YouTube動画を15件→123件に拡充（チャンネル全履歴）
- メンバー限定バッジ（62件）実装
- ショートタブ分離
- 「もっと見る」ボタン、「メンバーになる」リンク追加
- 自動検出スクリプト（detect_new_works.py）廃止決定
- デプロイ前確認ルール策定（JS欠損事故を受けて）

### 2026-04-14以前
- サイト初期構築（DLsite作品カタログ、YouTubeセクション）
- NEWバッジ、ジャンルフィルター、テキスト検索
- カスタムドメイン設定（reivox.jp）
- OGP画像更新
- check_releases.py / fetch_youtube.py 作成
- GitHub Actions定時実行設定
