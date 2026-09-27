## Context

各サイトの compose には WP-CLI のサービス `{site}-cli`（profile `cli`）があり、WordPress のコンテナと html ボリューム・`wp-content`・DB の接続先を共有している。開発セッション中は共有 MySQL が動いているので、WordPress のコンテナを起動しなくても `docker compose run --rm -T {site}-cli wp ...` が動く。

## Goals / Non-Goals

**Goals:**
- 全サイトのプラグインと版、プラグイン対応状況を 1 つの表で見られるようにする。
- 取得でサイトの状態（起動・停止）を変えない。

**Non-Goals:**
- プラグインの更新・有効化などの操作。
- 自動の定期取得。

## Decisions

### 取得
- サイトごとに `wp core version` と `wp plugin list --format=json --fields=name,title,version,status` を `{site}-cli` で実行する。`dropin` は除く。
- 一度も起動していないサイトは html ボリュームが空で失敗する。その場合は「一度サイトを起動してください」と表示する。
- wordpress.org の API（`plugins/info/1.2/?action=plugin_information`）は、active と inactive の slug にだけ問い合わせる（must-use は wordpress.org のプラグインではないことが多いので「不明」）。タイムアウトは 10 秒。
- 再取得は同期で実行する。ファイルロック `plugins.lock` で 1 本ずつに限る。

### 保存（SQLite、dashboard app）
- `SiteFetch`: サイトごとの最後の試行（時刻、成否、エラー、成功時の WordPress の版、最後に成功した時刻）。
- `SitePlugin`: サイトごとの最後に成功した取得結果（slug、表示名、版、状態）。取得に成功したサイトだけ置き換える。
- `PluginInfo`: slug ごとの wordpress.org の結果（登録の有無、requires、tested、取得時刻）。問い合わせに失敗した slug は前回の値を残す。

### 判定
- メジャーの列: `requires` のメジャー ≤ M ≤ `tested` のメジャーなら OK、外れれば NG、情報がなければ不明。
- サイトのセル: サイトの版が `requires` 以上、かつ (メジャー, マイナー) が `tested` の (メジャー, マイナー) 以下でなければ「6.7 非対応」のように警告する。
- メジャーの列は、取得できたサイトの版（なければ `WP_IMAGE` のタグ）から、使われているメジャーだけを並べる。

### 画面
- テンプレートを `base.html`（ヘッダー・ナビ・終了ボタン・トースト）と、`index.html`・`plugins.html` に分ける。
- 表は `<table>` にする。絞り込みで列を隠すとき、`<td>` と `<th>` を隠すだけで列がそろうため。
- 絞り込みはブラウザで行う。サイト名で絞ると、一致しないサイトの列、残ったサイトが使っていないメジャーの列、残ったサイトのどれにも入っていない行を隠す。値は `?site=` と `?q=` に残す。

## Risks / Trade-offs

- wordpress.org の値は最新版のもので、入っている版の対応ではない → 画面に明記する。
- 取得中はリクエストが数十秒かかることがある → ボタンを「取得中…」にして二重送信を防ぐ。gunicorn のタイムアウト（150 秒）に収まる。
