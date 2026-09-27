## Context

`dev-site-power` の「操作の保護」は、LAN 公開中の起動・停止を 403 で拒否している。判定は `sites.proxy_is_public()` で、wp-main の `.env` の `PROXY_BIND_ADDRESS` を読む。

## Goals / Non-Goals

**Goals:**
- LAN 公開中も、ダッシュボードから起動・停止できるようにする。

**Non-Goals:**
- 認証を加えること。ダッシュボードは今までどおり認証なしで動く。
- `proxy_is_public()` を消すこと。後の change（開発セッションの終了ボタン）が同じ判定を使う。

## Decisions

- **CSRF の検証と POST だけの受け付けは残す。** 別のオリジンのページから Docker を操作される経路を塞ぐ対策で、LAN 公開の有無とは関係がないためである。
- **`proxy_is_public()` は残す。** ダッシュボードの view からは参照を外すが、関数とそのテストは残す。

## Risks / Trade-offs

- 同じ LAN の誰でも、サイトを起動・停止できる。→ LAN 公開は利用者が自分で選ぶ設定で、README に信頼できないネットワークでは使わないよう書いてある。起動・停止ではデータは失われない。
