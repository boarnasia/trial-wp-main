## Context

- CLI は `src/wp_main/` にあり、外部コマンドはすべて `Runner.run` を通る。`mutate=False` の読み取り系コマンドは dry-run でも実行され、テストでは `tests/conftest.py` の `FakeRunner` で置き換えられる。
- install が作るもの（サイトリポジトリ、`.env`、`wp-global-net`、hosts ブロック、CA の登録と `.local/dev-env-state.json`、コンテナ）は `devenv.install` にまとまっている。
- 統合テストでは、Python の `ssl` はキーチェーンを参照しないため Caddy の CA を検証できず、`/usr/bin/curl` はキーチェーンを参照して検証できることを確認済み。
- `devenv.install` を通しで確かめるテストはまだない。

## Goals / Non-Goals

**Goals:**
- 数秒で終わり、sudo なしで何度でも実行できる健全性チェック。
- 壊れている箇所ごとに、次に何をすればよいかが分かる出力。
- install の流れをホストに触れずに検証するテスト。

**Non-Goals:**
- 自動修復（`--fix`）。対処方法は表示するだけにする。
- 単体起動（wp-main を使わない構成）の検査。一括起動の構成だけを対象にする。
- 管理画面へのログイン確認。パスワードを扱う必要があるため、今回は含めない。

## Decisions

### D1. 項目を `Check` の一覧として組み立てる
`health.py` に、`Check`（`id`、`group`、`status`、`message`、`hint`）と、各項目を判定する関数を置く。前提の項目は、`requires` に書いた ID で表す。実行するときは一覧を前から順に評価し、前提の項目のどれかが FAIL（または SKIP）なら、その項目は判定関数を呼ばずに SKIP にする。
- 代替: 項目ごとに if 文で前提を確認する。項目が増えると依存関係が読み取りにくくなるため、採用しない。

項目 ID は `group.subject[.site]` の形にする（例: `config.repo.wp1`、`host.dns.wp1`、`container.wp1-db`、`http.https.wp1`）。

前提の関係:
- `.env` の項目は、リポジトリの項目を前提にする。
- コンテナの項目は、両サイトのリポジトリの項目と `host.network` を前提にする。wp-main の Compose が include するため、どちらかのサイトが欠けると起動できない。
- HTTPS の項目は、そのサイトの名前解決の項目、そのサイトの WordPress コンテナの項目、Caddy コンテナの項目を前提にする。HTTP から HTTPS へのリダイレクトは Caddy が返すため、その項目は名前解決と Caddy コンテナだけを前提にする。
- インストール済みの項目は HTTPS の項目を、バージョンの項目はインストール済みの項目を前提にする。

### D2. 判定の方法
| 項目 | 方法 |
| --- | --- |
| リポジトリ | `git -C <dir> remote get-url origin` の出力が `Site.remote` と一致するか |
| `.env` | ファイルがあるか。`sites.parse_env` で読み、値が `change-me` の変数がないか |
| 名前解決 | `socket.getaddrinfo(domain, 443)` の結果に `127.0.0.1` が含まれるか。macOS の resolver が `/etc/hosts` を参照する |
| ネットワーク | `docker network inspect wp-global-net` |
| CA | `docker compose exec -T caddy cat <root.crt>` の SHA-1（`trust.pem_sha1`）が、`security find-certificate -a -c "Caddy Local Authority" -Z /Library/Keychains/System.keychain` の出力に含まれるか。キーチェーンの読み取りに sudo は不要 |
| コンテナ | `docker compose ps --all --format json` を 1 回実行し、コンテナ名ごとの `State` と `Health` を見る |
| HTTPS | `/usr/bin/curl -sS -o /dev/null -w '%{http_code} %{redirect_url} %{ssl_verify_result}' https://<domain>/` |
| 証明書の検証 | 失敗したときは `-k` を付けて再試行する。応答があれば WARN、なければ FAIL |
| HTTP のリダイレクト | `http://<domain>/` の応答が 301 / 302 / 307 / 308 で、`Location` が `https://<domain>/` で始まるか |
| インストール済み | HTTPS の応答が `/wp-admin/install.php` へのリダイレクトなら FAIL |
| バージョン | トップページの `<meta name="generator" content="WordPress X.Y.Z">` のメジャーバージョンを、`.env` の `WP_IMAGE`（なければ `Site.image`）のタグの先頭の数字と比べる |

- 代替: バージョンを `docker compose exec` の `php` で読み取る。HTTP の応答から読めるうえ、コンテナを起動したままにする必要もないため、採用しない。
- 代替: `urllib` で HTTPS を確認する。キーチェーンの CA を検証できず、正常な環境でも WARN になるため、採用しない。
- `/usr/bin/curl` を絶対パスで呼ぶ。Homebrew の curl は OpenSSL の CA バンドルを使い、キーチェーンを参照しないためである。
- タイムアウトは curl の `--max-time 5` とし、1 つのサイトが応答しなくても全体が止まらないようにする。

### D3. 出力
- 既定では、グループの見出しの下に `[OK]` や `[FAIL]` などの判定、項目名、メッセージを 1 行ずつ表示する。WARN と FAIL の項目は、次の行に `→ 対処方法` を表示する。最後に `OK n / WARN n / FAIL n / SKIP n` を表示する。色は `typer.secho` で付ける。
- `--json` では、`{"ok": bool, "summary": {...}, "checks": [...]}` を `json.dumps(ensure_ascii=False)` で 1 回だけ出力する。Runner がコマンドを表示しないよう、読み取り系は `mutate=False` で実行する。`mutate=False` は元から表示しない。
- 終了コードは、FAIL があれば `typer.Exit(1)` で 1、なければ 0。

### D4. install を通しで確かめるテスト
`tests/test_install.py` では、`FakeRunner` に、コマンドの先頭部分に応じて返り値を返す関数を渡す。そのうえで `devenv.install` を実際に呼ぶ。
- `hosts.HOSTS_FILE` と `hosts.BACKUP_FILE`、`config`・`devenv`・`trust` の `MAIN_DIR` と `LOCAL_DIR` と `STATE_FILE` と `CA_CERT_FILE` を `monkeypatch` で `tmp_path` に向ける。
- `ensure_site_repo` も差し替え、clone の後にテンプレートを描画するようにする。
- 待ち処理（`wait_for`）は、1 回目で成功したとみなすように差し替える。

確かめる内容:
- 通常の流れで、clone → `.env` → `network create` → hosts のバックアップ → hosts の書き込み → `compose up` → `wp core install` → `security add-trusted-cert` の順にコマンドが出ること
- `--no-start` なら、`compose up` 以降のコマンドが出ないこと
- `--skip-trust` なら、`security` のコマンドが出ないこと
- ポートが使用中なら、`compose up` の前に `DevEnvError` で止まること
- `wp core is-installed` が成功したら、`wp core install` が出ないこと

## Risks / Trade-offs

- [`docker compose ps --format json` の出力形式] → Compose のバージョンによって、1 行に 1 オブジェクトか、1 つの配列かが変わる。両方の形式を読めるように解析し、テストでも両方を確かめる。
- [名前解決のキャッシュ] → hosts を変えた直後は、古い結果が返ることがある。FAIL の対処方法に `sudo killall -HUP mDNSResponder` も書く。
- [ネットワークが遅い環境での誤判定] → 1 リクエストあたり 5 秒で打ち切る。タイムアウトは FAIL とし、メッセージにタイムアウトと明記する。
- [CA の判定と HTTPS の判定の重複] → 原因の場所（キーチェーン）と症状（証明書エラー）をそれぞれ表示するのが目的なので、重複は許容する。
