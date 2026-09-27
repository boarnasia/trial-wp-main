## 1. 取得と判定

- [x] 1.1 `plugins.py` に版の比較とプラグイン対応状況の判定（メジャー単位・サイトの版）を実装し、境界をテストで確かめる
- [x] 1.2 `{site}-cli` による取得（`wp core version`・`wp plugin list`、dropin の除外、html が空のときの案内）を実装し、偽の Runner でテストする
- [x] 1.3 wordpress.org の API の取得（登録なし・通信失敗）を実装し、偽の取得関数でテストする
- [x] 1.4 モデル（`SiteFetch`・`SitePlugin`・`PluginInfo`）と migration を加え、再取得で成功したサイトだけ置き換え、失敗は前回の値を残すことをテストで確かめる

## 2. 画面

- [x] 2.1 テンプレートを `base.html` に分け、ヘッダーに WordPress メニューとサブメニューを加える。既存のダッシュボードのテストが通ることを確かめる
- [x] 2.2 `/wordpress/plugins` の表（列・未導入・無効・MU・警告・未取得・取得失敗）を実装し、テストで確かめる
- [x] 2.3 `POST /wordpress/plugins/refresh`（CSRF、ロック、操作履歴、結果のメッセージ）を実装し、テストで確かめる
- [x] 2.4 絞り込み（プラグイン名・サイト名、`?q=`・`?site=`）を `main.js` に実装し、ビルドする

## 3. e2e とドキュメント

- [x] 3.1 e2e に、WordPress メニューからプラグイン横断リストを開けることを確かめるテストを加える
- [x] 3.2 README にプラグイン横断リストを書く
