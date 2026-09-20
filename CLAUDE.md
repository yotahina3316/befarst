# BE:FIRST 情報収集アプリ(befarst)

BE:FIRST関連の情報を集約・分類・翻訳・要約して届ける、**個人利用専用**のスマホアプリ(PWA)。
企画の全体像は [`BEFIRST_情報収集アプリ_企画整理.docx`](./BEFIRST_情報収集アプリ_企画整理.docx) を参照。

## 前提・確定事項(重要)

- **個人利用のみ**。配布・公開・販売の予定は将来を含めて一切なし。
- 上記の理由により、**著作権・商標・パブリシティ権などの権利面は気にせず実装する方針**(ユーザー明示の指示)。公開・配布する話に変わった場合はこの前提が崩れるため、改めて権利面を検討すること。
- **対象端末はiPhoneのみ**。Macを持たない/使いたくないため、**ネイティブアプリではなくPWA**として実装する(Xcode・Apple Developer登録が一切不要)。iPhoneはSafariの「ホーム画面に追加」でインストールする。
- **バックエンドサーバーは持たない**。GitHub Actions(定期実行)+ GitHub Pages(静的ホスティング)の組み合わせで実現する(下記「アーキテクチャ」参照)。

## フェーズ構成

- **Phase 1(現在実装中)**: `SCHEDULE`(統合カレンダー) + `NEWS`(ニュース集約)
- Phase 2以降(未着手、企画書に記載のみ): HOME、MEMBER別ページ、SOCIAL(SNS集約)、LIVE & TICKET詳細、GOODS、MUSIC/VIDEO、MY BESTY、AI BESTY、多言語対応

## アーキテクチャ(2026-09-20 GitHub Actions + Pages構成に移行)

### 移行の経緯

当初はXserver VPSに常時稼働のFastAPIサーバーを立てる構成だったが、VPSのグローバルIPが外部から到達不能になる問題が発生し、Xserverサポートとのやり取りが長期化した。その過程でユーザーから「そもそもこのアプリは単純な静的サイトで作れないのか」という根本的な問い直しがあり、検討の結果「サーバーを持たない構成(GitHub Actions + GitHub Pages)」に切り替えることを決定した。VPSの契約自体は残っているが、本プロジェクトのデプロイ先としては使わない方針。

### 全体構成

```
befarst/
├── CLAUDE.md
├── BEFIRST_情報収集アプリ_企画整理.docx
├── .github/workflows/
│   └── collect.yml       GitHub Actions: 30分おきに情報収集→data更新→コミット&push
├── backend/               収集・AI処理スクリプト(常時稼働サーバーではない、都度実行のみ)
│   ├── requirements.txt
│   ├── .env.example       ローカル検証用。GitHub Actionsでは使わずSecretsを使う
│   ├── collect.py         エントリーポイント(1回分の収集サイクルを実行)
│   └── befarst/
│       ├── config.py       環境変数読み込み
│       ├── ai.py           Claude APIで分類/日付抽出/翻訳/要約
│       ├── notifications.py Web Push送信(pywebpush、購読先はdata/subscriptions.jsonから読む)
│       └── collectors/
│           ├── official_news.py  BE:FIRST公式サイトのWordPress REST APIから収集
│           └── youtube.py        BE:FIRST公式YouTubeチャンネルのRSSから収集
├── data/
│   ├── README.md
│   └── subscriptions.json  Web Push購読情報(GitHub Pagesでは公開されない。手動で1回だけ登録)
└── docs/                  ← GitHub Pagesの公開ルート(Settings→Pages→Branch:main /docs)
    ├── index.html          SCHEDULE/NEWSタブのUI
    ├── manifest.json
    ├── service-worker.js   オフラインキャッシュ + Push通知受信
    ├── css/style.css
    ├── js/app.js           data/*.jsonを直接fetchして表示。VAPID公開鍵をハードコード
    ├── icons/
    └── data/
        ├── news.json        ニュース一覧(GitHub Actionsが更新、公開される)
        └── schedule.json    スケジュール一覧(同上)
```

**注意**: `docs/`という名前だが「ドキュメント」ではなく、GitHub Pagesの標準機能(Settings→Pages→Source: Deploy from a branch→Folder: `/docs`)がこの名前のフォルダしか選べないため。実質的にはフロントエンド一式(旧`frontend/`)。

処理の流れ(企画書の「情報取得→関連性判定→重複除去→分類→翻訳→要約→信頼度付与→表示→通知」に対応):

1. GitHub Actions(`*/30 * * * *`のcron)が`backend/collect.py`を実行
2. `collect.py`が`docs/data/news.json`・`docs/data/schedule.json`を読み込み、既存の`source_id`から重複除去した上で新着のみ`official_news.py`/`youtube.py`で取得
3. `ai.py`がClaude APIで1件ずつ「news/scheduleの判定・開催日時抽出・日本語タイトル・要約」を生成
4. 結果を`docs/data/news.json`(新着順、最大200件)・`docs/data/schedule.json`(開催日順、過去3日分までは保持しそれより古いものは除外)に書き戻す
5. 新着スケジュールがあれば、`data/subscriptions.json`に登録済みの購読先へWeb Push通知を送信
6. GitHub Actionsが変更を`git commit && git push`し、GitHub Pagesが自動的に再デプロイされる
7. フロント(`docs/js/app.js`)は`./data/schedule.json`・`./data/news.json`を直接fetchして表示するのみ(APIサーバーへのリクエストは一切ない)

### Web Push通知の仕組み(サーバーレス化に伴う変更点)

バックエンドサーバーが無いため、ブラウザが動的に購読登録APIへPOSTする仕組みが使えない。個人・単一ユーザー利用という前提のもと、以下の**手動・一度だけの運用**にしている。

1. アプリの「通知を有効にする」ボタンを押すと、`docs/js/app.js`がブラウザで購読(`PushSubscription`)を作成し、その内容(JSON)を画面上のテキストエリアに表示する
2. 利用者がその内容をコピーし、`data/subscriptions.json`に貼り付けてコミットする(このファイルは`docs/`の外にあるためGitHub Pagesでは公開されない)
3. 以後、GitHub Actionsの`collect.py`実行時にこのファイルを読んで通知を送る

VAPID公開鍵は非秘密情報のため`docs/js/app.js`に直接埋め込み済み。秘密鍵はGitHub Actions Secretsで管理する(後述)。

**残る注意点**: GitHub Pagesを無料で使うにはリポジトリを**公開(Public)**にする必要がある。そのため`docs/data/news.json`・`schedule.json`は誰でも閲覧可能になる(BE:FIRSTの公開ニュースなので実害は無い想定)。一方`data/subscriptions.json`は`docs/`の外なのでPagesサイトには出ないが、**リポジトリ自体が公開なのでリポジトリを直接見れば内容は分かってしまう**(Push購読先を使って偽の通知を送られる程度のリスクで、深刻な実害は想定しにくいが、ゼロではない点は認識しておくこと)。

## 情報源(2026年9月時点で調査・確認済み)

- **公式サイト**: `https://befirst.tokyo` はWordPress製で、**認証不要の公開REST APIが利用可能**(`https://befirst.tokyo/wp-json/wp/v2/posts`)。HTMLスクレイピングより大幅に安定するためこちらを採用。
  - カテゴリID対応(`/wp-json/wp/v2/categories`で確認済み): `1=NEWS, 9=MEDIA, 10=TV, 11=RADIO, 12=WEB, 13=MAGAZINE, 14=LIVE, 15=MUSIC, 16=DVD/Blu-ray, 17=GOODS, 18=CM`
  - `backend/befarst/collectors/official_news.py` 内の `CATEGORY_MAP` に反映済み。サイト側でカテゴリ構成が変わった場合はここを更新する。
- **BE:FIRST公式YouTubeチャンネル**: チャンネルID `UChNkqst-cjAoIbXb-ukn_tQ`。RSS URLは `https://www.youtube.com/feeds/videos.xml?channel_id=UChNkqst-cjAoIbXb-ukn_tQ`。
  - 2026-09-19時点のテストでは404だったが、2026-09-20の実機テストでは正常に動画が取得できることを確認済み(一時的なネットワーク要因だった可能性が高い)。GitHub Actions上でも動作確認が必要。
- 今後の候補(未実装): 音楽ナタリーのBE:FIRST関連ページ(`https://natalie.mu/music/artist/121056`、ただし自動アクセスがブロックされる挙動を確認済みで要調査)。
- **BMSG公式サイト(`https://bmsg.tokyo`)は調査の結果、今回(Phase 1)は見送り**: 同じくWordPress製で公開REST APIはあるものの、BMSG所属の他アーティスト(BMSG STRIKERS等)の情報も同じ`posts`エンドポイントに混在しており、`search`パラメータで絞り込んでもBE:FIRSTと無関係な記事が混入することを確認した。Phase 2以降でAIによる事前フィルタリング等を追加する形で再検討する。

## セットアップ・起動方法(ローカル検証)

```bash
cd backend
python -m venv venv
venv\Scripts\activate       # Windowsの場合
pip install -r requirements.txt
copy .env.example .env      # ANTHROPIC_API_KEY等を編集して埋める
python collect.py           # 1回分の収集サイクルを実行(サーバーは起動しない)
```

実行結果は `docs/data/news.json` / `docs/data/schedule.json` に反映される。フロントを見たい場合は `docs/` を適当な静的サーバー(例: `python -m http.server` を`docs/`内で実行)で開けばよい。

### VAPIDキーの生成(Web Push通知に必要)

**生成済み**(2026-09-19、`vapid --gen --applicationServerKey` コマンドで生成)。`backend/keys/vapid_private_key.pem` / `backend/keys/vapid_public_key.pem` として保存済み(`.gitignore`済みなのでリポジトリには含まれない)。
- 公開鍵(`BAvDkNGVDoA1iLGfn8SC6rSGcx_A4VygbgxS07MQV09qHJxCJJ9nUHJAS4uZiue2XY8SlwqP_cXkZCIp10eEMCY`)は非秘密情報のため `docs/js/app.js` に直接埋め込み済み。
- 秘密鍵は `backend/.env` の `VAPID_PRIVATE_KEY=keys/vapid_private_key.pem` で参照(ローカル用)。GitHub Actionsでは `VAPID_PRIVATE_KEY_PEM` というSecret(.pemファイルの中身をそのままテキストとして登録)から、ワークフロー実行時に一時ファイルとして書き出して使う。

再生成する場合のコマンド:
```bash
cd backend
venv\Scripts\vapid.exe --gen --applicationServerKey
```
(再生成した場合、`docs/js/app.js`内のVAPID_PUBLIC_KEYと、GitHub Actions Secretsの`VAPID_PRIVATE_KEY_PEM`の両方を更新すること)

## GitHub リポジトリのセットアップ(進行中)

- GitHubユーザー名: `yotahina3316`(2026-09-20作成)
- ローカルgitリポジトリは初期化済み(`git init`実施済み、2026-09-20)
- **未実施**: GitHubリモートリポジトリの作成・push、Secretsの登録、Pages設定の有効化

### 必要な設定手順(リポジトリ作成後)

1. GitHub上で新規リポジトリを作成(**Public**にする。無料でPagesを使うには公開リポジトリである必要がある)
2. ローカルから `git remote add origin https://github.com/yotahina3316/<リポジトリ名>.git` → `git push -u origin master`(または`main`にリネームしてから)
3. リポジトリの Settings → Secrets and variables → Actions → New repository secret で以下を登録:
   - `ANTHROPIC_API_KEY`(ローカルの`backend/.env`と同じ値)
   - `VAPID_PRIVATE_KEY_PEM`(`backend/keys/vapid_private_key.pem`の中身をそのまま貼り付け)
   - `VAPID_CLAIM_EMAIL`(例: `mailto:xxxxx@example.com`)
4. リポジトリの Settings → Actions → General → Workflow permissions で「Read and write permissions」を有効化(`collect.yml`がdata更新をpushできるようにするため必須)
5. リポジトリの Settings → Pages → Source: 「Deploy from a branch」→ Branch: `main`(または`master`) / Folder: `/docs` を選択
6. `.github/workflows/collect.yml` の Actions タブから手動実行(workflow_dispatch)して動作確認
7. 数分後、`https://yotahina3316.github.io/<リポジトリ名>/` でアプリが表示されることを確認
8. iPhoneのSafariでそのURLを開き「ホーム画面に追加」してインストール

カスタムドメイン(`befirst.maryue.info`、旧VPS用にDNS設定済み)を使いたい場合は、Settings → Pages → Custom domainで設定し、DNSのAレコードをGitHub PagesのIPに向け直す必要がある(現状は旧VPSのIPを向いたままなので要変更)。必須ではなく、`github.io`のURLでもPWAとして問題なく動作する。

## 現状の実装状況

- [x] 収集・AI処理スクリプト(`backend/collect.py`)の実装、DB不要のJSON方式に移行済み
- [x] PWAフロント一式(`docs/`、SCHEDULE/NEWSタブ、Service Worker、手動Push購読フロー)
- [x] 公式サイトの実データ取得ロジック(WP REST API)
- [x] **ローカル環境でのE2E動作確認済み(2026-09-20、新アーキテクチャで再確認)**: `python collect.py`を実行し、公式サイト+YouTubeから実データを収集→AI分類(拡張思考対応、日付の年補完含む)→`docs/data/news.json`(11件)・`docs/data/schedule.json`(27件、過去3日〜未来分)に正しく保存されることを確認済み。
- [x] Anthropic APIキー・VAPIDキーの生成・ローカル設定済み
- [ ] **GitHubリポジトリの作成・push・Secrets登録・Pages有効化** ← 次の作業
- [ ] GitHub Actions上でのYouTube RSS収集の動作確認(ローカルでは動作確認済みだが、Actions環境固有の到達性は未確認)
- [ ] Web Push通知の実機(iPhone)での動作確認(`data/subscriptions.json`への手動登録がまだ)
- [ ] アプリアイコンの差し替え(現状はPillowで生成した仮アイコン)
- [ ] Phase 2以降の機能(MEMBER別ページ、SOCIAL、GOODS等)
- [x] ~~Xserver VPSへのデプロイ~~ → 方針転換によりこのプロジェクトでは使用しないことに決定(VPS契約自体は残っている)

## 過去の経緯(参考・アーカイブ)

Xserver VPSクラウドへのデプロイを試みたが、作成したVPSのグローバルIPが外部から一切到達不能という問題が発生し、Xserverサポートに問い合わせても即座に解決しなかった(サーバー内部・DNS・ファイアウォール等はすべて正常と確認済みだった)。この過程で「本当にVPSが必要か」を再検討し、GitHub Actions + Pagesへの移行を決定した。VPSの解約要否はユーザー判断(Xserver VPS管理パネルの「解約申請」から可能)。ドメイン`befirst.maryue.info`のDNS Aレコードは現状VPSのIPを向いたままなので、使わないなら放置でも実害はないが、気になる場合は削除して良い。
