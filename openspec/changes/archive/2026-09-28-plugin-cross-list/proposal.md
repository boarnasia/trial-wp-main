## Why

サイトが増えると、どのサイトにどのプラグインのどの版が入っているか、今の WordPress で動くとされているかを、サイトごとの管理画面を開かずに確かめたくなる。ダッシュボードに WordPress 用のメニューを設け、全サイトのプラグインを 1 つの表で見比べられるようにする。

## What Changes

- ヘッダーに大メニュー「WordPress」を加え、サブメニュー「プラグイン横断リスト」（`/wordpress/plugins`）を置く。
- プラグイン横断リストは、プラグインごとに 1 行で、次の列を並べる。
  - プラグイン名（wordpress.org のページへのリンクと slug）
  - サイトが使っている WordPress のメジャーごとの **プラグイン対応状況**（OK / NG / 不明）
  - サイトごとの版（未導入は `-`、無効・must-use の印、そのサイトの版で対応外なら警告）
- 「再取得」で、サイトを起動せずに `{site}-cli` の WP-CLI で各サイトのプラグインを取得し、wordpress.org の API で対応状況を取得する。結果は SQLite に保存し、ページの表示では外部に問い合わせない。
- 一部が失敗しても、サイト単位・プラグイン単位で前回の値を残す。再取得は操作履歴に `plugins-refresh` として記録する。
- プラグイン名とサイト名で絞り込める。値は URL のクエリに残す。

## Capabilities

### New Capabilities
- `dev-plugin-cross-list`: WordPress メニュー、プラグイン横断リストの表示・取得・絞り込み。

### Modified Capabilities
（なし）

## Impact

- コード: `src/wp_main/plugins.py`（新規）、`src/wp_main/dashboard/`（`models.py` と migration 0002、`views.py`、`urls.py`、テンプレートを `base.html` と `plugins.html` に分ける、`frontend/main.js`、`static/dist/`）
- 外部通信: 再取得のときだけ `api.wordpress.org` に問い合わせる
- テスト: `tests/test_plugins.py`（新規）、`tests/test_plugin_views.py`（新規）、e2e に 1 本
- ドキュメント: `README.md`
