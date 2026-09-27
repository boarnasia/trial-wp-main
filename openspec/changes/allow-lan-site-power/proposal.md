## Why

LAN 公開（`PROXY_BIND_ADDRESS` が `127.0.0.1` 以外）は、実機の端末から確認するために利用者が自分で選ぶ設定である。それなのに、LAN 公開中はダッシュボードからサイトを起動・停止できず、確認のたびに端末へ戻る必要がある。同じ LAN から管理者パスワードは既に見えるので、起動・停止だけを止めても守れるものは少ない。

## What Changes

- LAN 公開中も、ダッシュボードからのサイトの起動・停止を有効にする。
- CSRF トークンの検証と、POST でだけ受け付ける規則は変えない。
- LAN 公開中に表示していた「起動・停止は無効です」の案内をなくす。
- `.env.example` と README の説明を、LAN 公開中も起動・停止できる前提に直す。

## Capabilities

### New Capabilities
（なし）

### Modified Capabilities
- `dev-site-power`: 「操作の保護」から、LAN 公開中に起動・停止を無効にする規則を外す。

## Impact

- コード: `src/wp_main/dashboard/views.py`（`PUBLIC_REASON` と LAN 公開の判定を外す）、`src/wp_main/dashboard/templates/index.html`（案内の表示を外す）
- テスト: `tests/test_site_power_views.py`
- ドキュメント: `.env.example`、`README.md`
- 利用者: LAN 公開中も、同じ LAN の端末からサイトを起動・停止できるようになる
