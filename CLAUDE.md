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

### SCHEDULEに載せる情報の基準(2026-09-21確定、ユーザー指示)

SCHEDULEタブに表示するのは以下の4種類**のみ**。それ以外(TV/ラジオ/雑誌出演、配信限定リリース、キャンペーン告知等)は全て`NEWS`扱いにする。

1. DVD/Blu-rayの発売日
2. チケットの先行/一般販売日
3. グッズの発売日
4. ライブ・コンサート・ファンミーティング等の開催日
5. メンバーの誕生日(`backend/befarst/birthdays.py`で固定データとして管理。公式サイトのニュースとは別枠で毎回自動生成される)

`backend/befarst/ai.py`の`SCHEDULE_CATEGORIES = {"LIVE", "GOODS", "RELEASE"}`がこの分類ロジック本体。`schedule_category`という値を各アイテムに持たせ、フロント側のカレンダーで色分け表示に使う。

**SCHEDULE UIはカレンダー形式**(2026-09-21実装): リスト表示ではなく、月間カレンダーグリッドに日付ごとのイベントをドット表示し、日付をタップするとその日の予定が下部に一覧表示される形式。`docs/js/app.js`の`calendarState`まわりが該当ロジック。

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
- リポジトリ: **`https://github.com/yotahina3316/befarst`(Public、作成・push完了、2026-09-20)**
- GitHub Pages公開URL: **`https://yotahina3316.github.io/befarst/`(稼働確認済み)**
- ローカルには`gh` CLI(GitHub CLI)をインストール・`yotahina3316`で認証済み(`gh auth login`、scope: repo, workflow, gist, read:org)。以後のGitHub操作は`gh`コマンド経由で可能。

### 完了済みの設定

1. ✅ リポジトリ作成・初回push完了(`gh repo create befarst --public --source=. --remote=origin --push`)
   - 初回pushは`.github/workflows/collect.yml`を含むため`workflow`スコープが無く失敗 → `gh auth refresh -h github.com -s workflow`でスコープ追加後に再push成功、という経緯があった
2. ✅ Secrets登録完了(`gh secret set`で設定): `ANTHROPIC_API_KEY`、`VAPID_PRIVATE_KEY_PEM`(`.pem`ファイルの中身)、`VAPID_CLAIM_EMAIL`(`mailto:yotahina3316@gmail.com`、GitHub登録メールを使用)
3. ✅ Actions Workflow permissions を「Read and write」に設定済み(`gh api`経由)
4. ✅ GitHub Pages有効化済み(`gh api`経由、Branch: `master` / Folder: `/docs`)
5. ✅ `collect.yml`を手動実行(`gh workflow run`)して動作確認済み。実際に新規1件のニュースを検出・追加し、自動コミット→Pages再デプロイまで正常に完了(2026-09-20 12:52 UTC)。既存27件のスケジュールは重複除去により再登録されず、dedupロジックが正しく機能していることも確認できた。
6. ✅ サイトが実際に稼働していることを確認(`https://yotahina3316.github.io/befarst/`が200、`data/news.json`も正しく配信されている)

7. ✅ トップページにヒーロー画像を追加(公式サイトの最新ビジュアル`Campaign_1-scaled.webp`を`docs/images/hero.webp`として保存、2026-09-20)
8. ✅ iPhoneへのインストール確認済み(ホーム画面に追加、Safari共有メニューから)
9. ✅ **Web Push通知が実機で動作確認済み(2026-09-20)**: `data/subscriptions.json`に購読情報を登録し、`notify_all()`でテスト通知を送信 → iPhoneに実際に通知が届くことを確認済み。

### 残っている作業(任意・低優先度)

- [ ] GitHub Actions環境でのYouTube RSS収集の動作確認(ローカルでは成功、Actions上のログでも要確認。次回の定期実行ログで確認可能)
- [ ] アプリアイコンの差し替え(現状はPillowで生成した仮アイコン。「BE」の文字のみのプレースホルダー)
- [ ] Phase 2以降の機能(MEMBER別ページ、SOCIAL、GOODS等)
- [ ] (任意)カスタムドメイン`befirst.maryue.info`を使いたい場合は、Settings → Pages → Custom domainで設定し、DNSのAレコードをGitHub PagesのIPに向け直す(現状は旧VPSのIPを向いたまま)。必須ではなく`github.io`のURLでも問題なく動作する。
- [ ] (任意)Xserver VPSクラウドの解約(使わないと決めたため。Xserver VPS管理パネルの「解約申請」から)

## 現状の実装状況

**Phase 1(SCHEDULE + NEWS)は完成し、本番相当の環境で全機能の動作確認が完了している。**

- [x] 収集・AI処理スクリプト(`backend/collect.py`)の実装、DB不要のJSON方式
- [x] PWAフロント一式(`docs/`、SCHEDULE/NEWSタブ、ヒーロー画像、Service Worker、手動Push購読フロー)
- [x] 公式サイトの実データ取得ロジック(WP REST API)+ YouTube RSS
- [x] Anthropic APIキー・VAPIDキーの生成・設定(ローカル`.env`+GitHub Actions Secrets)
- [x] GitHubリポジトリの作成・push・Secrets登録・Pages有効化・動作確認(2026-09-20)
- [x] GitHub Actionsでの自動収集(30分おき)が実際に新着を検出・反映することを確認済み
- [x] iPhoneへのインストール(ホーム画面に追加)確認済み
- [x] **Web Push通知が実機で動作確認済み(2026-09-20)**
- [ ] アプリアイコンの差し替え(任意、現状はプレースホルダー)
- [ ] Phase 2以降の機能(MEMBER別ページ、SOCIAL、GOODS等、未着手)
- [x] ~~Xserver VPSへのデプロイ~~ → 方針転換によりこのプロジェクトでは使用しないことに決定(VPS契約自体は残っている)

## 過去の経緯(参考・アーカイブ)

Xserver VPSクラウドへのデプロイを試みたが、作成したVPSのグローバルIPが外部から一切到達不能という問題が発生し、Xserverサポートに問い合わせても即座に解決しなかった(サーバー内部・DNS・ファイアウォール等はすべて正常と確認済みだった)。この過程で「本当にVPSが必要か」を再検討し、GitHub Actions + Pagesへの移行を決定した。VPSの解約要否はユーザー判断(Xserver VPS管理パネルの「解約申請」から可能)。ドメイン`befirst.maryue.info`のDNS Aレコードは現状VPSのIPを向いたままなので、使わないなら放置でも実害はないが、気になる場合は削除して良い。
