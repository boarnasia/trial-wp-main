## MODIFIED Requirements

### Requirement: 操作の保護
起動・停止の要求は POST でだけ受け付け、CSRF トークンを検証しなければならない (MUST)。トークンがない、または一致しない要求は 403 を返し、Docker を操作してはならない (MUST NOT)。wp-main の `.env` の `PROXY_BIND_ADDRESS` が `127.0.0.1` 以外の場合も、起動・停止のボタンは有効にし、正しい要求は実行しなければならない (MUST)。

#### Scenario: 別のサイトからの POST
- **WHEN** 別のオリジンのページから、CSRF トークンなしで wp1 の停止を POST する
- **THEN** 403 が返り、wp1 は停止しない

#### Scenario: GET では操作しない
- **WHEN** 停止の URL に GET でアクセスする
- **THEN** 405 が返り、wp1 は停止しない

#### Scenario: LAN に公開している
- **WHEN** wp-main の `.env` に `PROXY_BIND_ADDRESS=0.0.0.0` がある状態でダッシュボードを開き、wp1 の停止のボタンを選ぶ
- **THEN** 起動・停止のボタンは有効で、wp1 が停止する
