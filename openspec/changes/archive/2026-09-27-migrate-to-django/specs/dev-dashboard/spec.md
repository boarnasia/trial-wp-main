## MODIFIED Requirements

### Requirement: 既存の環境への導入
ダッシュボードを持たない環境バージョン 1 の環境は、migration 2 で導入されなければならない (MUST)。migration 2 は `/etc/hosts` のブロックにダッシュボードのドメインを加えなければならない (MUST)。プロキシが起動している場合は、ダッシュボードのイメージをビルドして起動し、プロキシを新しい構成で作り直さなければならない (MUST)。プロキシが停止している場合は、コンテナを起動してはならない (MUST NOT)。migration 2 は sudo を必要とし、データを失う操作を含まないものとして扱わなければならない (MUST)。何度実行しても結果が同じでなければならない (MUST)。

#### Scenario: 起動中の環境に導入する
- **WHEN** 環境バージョン 1 で全コンテナが起動している状態で `devenv migrate` を実行する
- **THEN** `/etc/hosts` のブロックに `local.wp-main.yamashita109.com` が加わり、`wp-dashboard` が起動し、環境バージョンが 2 になる

#### Scenario: 停止中の環境に導入する
- **WHEN** 環境バージョン 1 でプロキシが停止している状態で `devenv migrate` を実行する
- **THEN** `/etc/hosts` のブロックは更新されるが、コンテナは起動されず、環境バージョンは 2 になる

#### Scenario: pull の後の自動実行
- **WHEN** 環境バージョン 1 の環境で、migration 2 を含むコミットを `git pull` で取り込む
- **THEN** migration は自動では実行されず、`uv run manage.py devenv migrate` を端末で実行するよう表示される

#### Scenario: 再実行
- **WHEN** hosts のブロックに既にダッシュボードのドメインがある状態で migration 2 を実行する
- **THEN** `/etc/hosts` は書き換えられない

## ADDED Requirements

### Requirement: 既存の環境での Django 版への切り替え
環境バージョン 2 の環境は、dev-env:migration 3 で Django 版のダッシュボードに切り替えられなければならない (MUST)。migration 3 は、wp-main の `.env` に `DJANGO_SECRET_KEY` がなければランダム値で加え、既存の値は変更してはならない (MUST NOT)。プロキシが起動している場合はダッシュボードのイメージを再ビルドして起動し直さなければならない (MUST)。停止している場合はコンテナを起動してはならない (MUST NOT)。migration 3 は sudo を必要とせず、データを失う操作を含まないものとして扱わなければならない (MUST)。何度実行しても結果が同じでなければならない (MUST)。切り替えの前後で、ダッシュボードの URL、表示内容、パスワード取得 API の応答は変わってはならない (MUST NOT)。

#### Scenario: pull の後に自動で切り替わる
- **WHEN** 環境バージョン 2 で全コンテナが起動している環境に、migration 3 を含むコミットを `git pull` で取り込む
- **THEN** migration 3 が自動で実行され、`.env` に `DJANGO_SECRET_KEY` が加わり、ダッシュボードが再ビルドされて起動し、環境バージョンが 3 になる

#### Scenario: 秘密鍵が既にある
- **WHEN** wp-main の `.env` に `DJANGO_SECRET_KEY` がある状態で migration 3 を実行する
- **THEN** `.env` は変更されない

#### Scenario: 切り替え後も同じ応答
- **WHEN** 切り替え後に `https://local.wp-main.yamashita109.com/` を開き、wp1 のパスワードを表示する
- **THEN** 切り替え前と同じ一覧が表示され、パスワードは `Cache-Control: no-store` 付きで返る
