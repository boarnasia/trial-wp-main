# ダッシュボードから wp1 / wp2 を起動・停止する方法の調査

調査日: 2026-09-27

> **その後の決定（2026-09-27）**: この調査の後、Docker のエンジンを OrbStack から Docker Desktop に移した。そのうえで、ダッシュボードそのものをコンテナからホストのプロセス（`uv run manage.py devenv serve`）に移す方式を採った（OpenSpec の change `host-side-dashboard`）。ダッシュボードがホストの `docker compose` を直接呼ぶので、下の結論にあるエージェントやジョブの受け渡しは不要になった。Caddy は `host.docker.internal` 経由でホストの `127.0.0.1` に転送する（Docker Desktop で、127.0.0.1 だけで待ち受けるサーバーに届くことを確認した）。CLI も API を通さずに DB へ直接書く。以下の本文は、調査した時点の内容のまま残している。

## 結論

**ホスト側のエージェント（`manage.py devenv` のサブコマンド）が、ダッシュボードの Web API からジョブを取りに行き、ホストで `docker compose` を実行する方式を勧める。**

- ダッシュボードのコンテナに Docker のソケットを渡すと、ホストの root 権限に相当する権限を渡すことになる。ソケットプロキシを挟んでも、止められるコンテナを wp1 / wp2 だけに絞ることはできない
- 「DB に書き込むのは Web 側だけ。CLI は Web API を呼ぶ」という既存の方針に合う。CLI がジョブを取り出して実行し、結果を API に返す。操作履歴（`/api/operations`）も同じ仕組みで記録できる
- 状態の表示には Docker を使わない。エージェントが定期的に `docker compose ps` の結果を API に送る。加えて、ダッシュボードは `wp-global-net` 経由で `wp1-wordpress:80` に HTTP で疎通を確認できる

調査の途中で、前提と違う点が 2 つ見つかった。どちらの方式を選ぶかに関わる。

1. **このマシンの Docker エンジンは Docker Desktop ではなく OrbStack だった。** `docker context ls` では `orbstack *` が選ばれていて、`/var/run/docker.sock` は `~/.orbstack/run/docker.sock` へのシンボリックリンクだった。`docker info` の OperatingSystem は `OrbStack` で、Engine は 29.4.0（API 1.54）、Compose は v5.1.2。以下では、Docker Desktop と OrbStack の両方について書く
2. **一括起動では、wp1 / wp2 のコンテナは `wp-main` プロジェクトに属している。** wp-main の `docker-compose.yml` が `include` で両サイトを取り込んでいるためで、`docker inspect wp1-wordpress` のラベルは `com.docker.compose.project=wp-main`、`project.working_dir=/Users/masatouehara/dev/work/wp-main` だった。したがって、`docker compose -f ../wp-wp1/docker-compose.yml up -d` で起動してはいけない。これを実行すると別のプロジェクト `wp-wp1` として作ろうとし、`container_name: wp1-wordpress` がぶつかる（README の「単体起動と一括起動はコンテナ名が同じなので同時には動かない」と同じ理由）。正しくは wp-main で `docker compose up -d wp1-wordpress` / `docker compose stop wp1-wordpress wp1-db` のように、サービスを指定して実行する

---

## 1. 現状の構成（リポジトリと実機で確認）

| 項目 | 内容 | 出所 |
| --- | --- | --- |
| ダッシュボード | `wp-dashboard`。gunicorn、`USER nobody`（コンテナ内で `uid=65534(nobody) gid=65534(nogroup)`）、`wp-global-net` に接続 | `dashboard.Dockerfile`、`docker exec wp-dashboard id` |
| サイトのマウント | `../wp-wp1:/sites/wp1:ro`、`../wp-wp2:/sites/wp2:ro` だけ。Docker のソケットはマウントしていない | `docker-compose.yml`、`docker inspect wp-dashboard` |
| 一括起動 | `name: wp-main` と `include: [../wp-wp1/docker-compose.yml, ../wp-wp2/docker-compose.yml]` | `docker-compose.yml` |
| サイトのサービス | `wp1-db`（`wp1-internal` だけ）、`wp1-wordpress`（`wp1-internal` と `wp-global-net`。`depends_on: wp1-db: service_healthy`）、`wp1-cli`（`profiles: [cli]`）。すべて `restart: unless-stopped` | `../wp-wp1/docker-compose.yml` |
| 相対パスのバインドマウント | `./wp-content:/var/www/html/wp-content`、`./config/wp-config-proxy.php:...` | 同上 |
| API | Django Ninja。`/api/operations` は Bearer トークン（`DASHBOARD_API_TOKEN`）で認証する | `src/wp_main/dashboard/views.py` |
| CLI から API への送信 | `operations.call_api()` が Caddy のルート証明書で検証しつつ、3 秒で打ち切る | `src/wp_main/operations.py` |
| 方針 | 「記録はダッシュボードの Web API を通して行い、DB に書き込むのはダッシュボードだけにする」「CLI は DB のファイルを直接開いてはならない」 | `openspec/specs/dev-operation-history/spec.md` |
| CSRF | `MIDDLEWARE` に `CsrfViewMiddleware` がない。画面は認証なしで、`PROXY_BIND_ADDRESS=0.0.0.0` にすると LAN から見える | `src/wp_main/settings.py`、README |

---

## 2. 案 A: Docker のソケットをダッシュボードにマウントする

### 2.1 仕組み

- Docker のデーモンは root 権限で動き、CLI は Unix ソケット経由で REST API を呼ぶ。「Docker のデーモンを操作できるのは信頼できるユーザーだけにすべき」とされ、ファイアウォールで守っていても「コンテナからはエンドポイントに届きうるので、権限昇格につながりやすい」と明記されている — <https://docs.docker.com/engine/security/>
- OWASP は Rule #1 で、ソケットへのアクセスは「ホストへの無制限の root アクセスを与えるのと同じ」とし、コンテナに `/var/run/docker.sock` を渡さないよう求めている。読み取り専用（`:ro`）でマウントしても解決にはならず、悪用を少し難しくするだけだとしている — <https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html>
- Engine API には、既存のコンテナを操作する `POST /containers/{id}/start` と `POST /containers/{id}/stop` がある。`GET /containers/json` は `label=key` / `label="key=value"` で絞り込める — <https://docs.docker.com/reference/api/engine/version/v1.54/>（OpenAPI の `v1.54.yaml`）
- docker-py では `client.containers.list(filters={"label": "com.docker.compose.project=wp-main"})`、`Container.start()`、`Container.stop(timeout=10)`、`Container.status` が使える — <https://docker-py.readthedocs.io/en/stable/containers.html>

### 2.2 macOS 上のソケットのパスと権限

- Docker Desktop では、ソケットの実体は `~/.docker/run/docker.sock` にある。管理者の許可があれば、`/var/run/docker.sock` へのシンボリックリンクを launchd のタスクで作り直す。許可しない場合は、クライアント側で `DOCKER_HOST` を指定する必要がある — <https://docs.docker.com/desktop/setup/install/mac-permission-requirements/>
- コンテナにバインドするときの送り元は、`/var/run/docker.sock` と書く必要がある。`$HOME/.docker/run/docker.sock` を直接指定すると接続できないという報告がある — <https://github.com/docker/for-mac/issues/6545>（docker/for-mac の issue。Docker 社は acknowledged のラベルだけを付けている）
- OrbStack は `orbstack` コンテキストを作り、互換のために `/var/run/docker.sock` へのシンボリックリンクを置く — <https://docs.orbstack.dev/docker/>
- Docker Desktop の Enhanced Container Isolation を有効にすると、ソケットのマウントは既定で拒否される — <https://docs.docker.com/enterprise/security/hardened-desktop/enhanced-container-isolation/config/>
- **`nobody` で動くプロセスから使えるか**: コンテナから見えるソケットは VM の中のソケットで、macOS 上の所有者やパーミッションは引き継がれない。コンテナ内での所有者（多くは `root:root` か、VM 内の `docker` グループ）に合わせて、`group_add` でその GID を加える必要がある。これについては一次資料で確かめられなかった。状態を変えない範囲では試せないため、未検証とする。採用するなら、`docker run --rm -v /var/run/docker.sock:/s alpine stat -c '%u:%g %a' /s` のような確認が必要になる

### 2.3 コンテナの中から `docker compose up/stop` を実行したときの「パスの食い違い」

- Compose は、相対パスのホストパスを「Compose ファイルの親ディレクトリから」解決する。これはローカルのランタイムに対してだけ意味を持つ — <https://docs.docker.com/reference/compose-file/services/>
- `include` した各ファイルは、それぞれのプロジェクトディレクトリで相対パスを解決したうえで、元のプロジェクトのモデルにコピーされる — <https://docs.docker.com/compose/how-tos/multiple-compose-files/include/>
- ダッシュボードのコンテナでは、サイトは `/sites/wp1` にマウントされている。そこで Compose を動かすと、`./wp-content` は `/sites/wp1/wp-content` に解決され、そのパスのままエンジンに送られる。エンジン（Docker Desktop や OrbStack の VM。macOS のファイル共有でホストのパスを見ている）には `/sites/wp1` が存在しない。そのため、空のディレクトリがマウントされるか、エラーになる
- さらに、`docker compose up` は「サービスの設定が作成後に変わっていれば、止めて作り直す」 — <https://docs.docker.com/reference/cli/docker/compose/up/>。パスが変わると設定のハッシュ（`com.docker.compose.config-hash` ラベル）も変わり、コンテナが作り直される
- 避けるには、wp-main・wp-wp1・wp-wp2 を**ホストと同じ絶対パス**（`/Users/masatouehara/dev/work/...`）でマウントし、`.env` も読めるようにする必要がある。ただしそれは、ダッシュボードの spec にある「サイトディレクトリに書き込めてはならない」や、パスをユーザーの環境に依存させない方針とぶつかる
- 一方、`docker compose start` は「既存のコンテナを起動する」だけで、作り直しはしない — <https://docs.docker.com/reference/cli/docker/compose/start/>。`docker compose -p <project> ps` のように、プロジェクト名だけで既存のプロジェクトを操作する使い方もある — <https://docs.docker.com/reference/cli/docker/compose/>。**既存のコンテナを start / stop するだけなら、Compose を使わずに Engine API でラベルを絞り込み、start / stop を呼べば、パスの問題は起きない。** ただし、`down` した後の「作成」はできない

### 2.4 評価

- ソケットを渡すと、ダッシュボードの脆弱性（認証のない画面、CSRF 対策の欠如、LAN への公開）がそのままホストの root 権限の奪取につながる。ダッシュボードは管理者パスワードを表示するため、もともと価値の高い標的でもある
- 止められるコンテナを wp1 / wp2 に絞る仕組みは、Docker 側にはない。アプリのコードで絞るしかない
- Docker Desktop の ECI や、エンジンの切り替え（OrbStack と Docker Desktop）で動作が変わる

**不採用とする。**

---

## 3. 案 B: ソケットプロキシ（tecnativa/docker-socket-proxy）を挟む

- HAProxy がソケットの前に立ち、環境変数で許可していない API には `403` を返す。`EVENTS` / `PING` / `VERSION` は既定で許可され、`POST`（GET と HEAD 以外のすべて）・`CONTAINERS`・`ALLOW_START`・`ALLOW_STOP` などは既定で拒否される — <https://github.com/Tecnativa/docker-socket-proxy>
- 許可できる単位は、実際の `haproxy.cfg` を見ると**URL の接頭辞と HTTP メソッドだけ**だった — <https://github.com/Tecnativa/docker-socket-proxy/blob/master/haproxy.cfg>
  - `http-request deny unless METH_GET || { env(POST) -m bool }`
  - `ALLOW_START`: `^(/v[\d\.]+)?/containers/[a-zA-Z0-9_.-]+/start`（`ALLOW_STOP` も同様）
  - `CONTAINERS`: `^(/v[\d\.]+)?/containers` の接頭辞に一致するものはすべて許可
- ここからわかること:
  - **コンテナの ID や名前、ラベルでは絞り込めない。** `ALLOW_STOP=1` にすると、ホスト上のすべてのコンテナ（Caddy、ダッシュボード自身、他のプロジェクト）を止められる
  - 状態を読むために `CONTAINERS=1` を有効にし、同時に `POST=1` にすると、`POST /containers/create`（特権コンテナやホストの `/` のバインドマウント）や `POST /containers/{id}/exec` も通ってしまう。これは実質的に root 相当に戻る
  - 安全寄りの設定は `POST=1, ALLOW_START=1, ALLOW_STOP=1, CONTAINERS=0` になる。この場合、一覧も inspect もできないので、コンテナ名（`wp1-wordpress` など）を決め打ちで start / stop するだけになる。状態を読むには、`CONTAINERS=1, POST=0` の読み取り専用のプロキシをもう 1 つ立てる必要がある。ただし inspect の結果には `MYSQL_ROOT_PASSWORD` などの環境変数が含まれ、他のプロジェクトのコンテナの情報も見えてしまう
- README も、プロキシのポートを公開せず、プロキシと利用側だけがいる Docker ネットワークに置くよう勧めている。TLS はない — 同上
- `down` した後の「作成」はできない（Compose のモデルがないため）。`wp1-db` の healthy を待ってから `wp1-wordpress` を起動するという `depends_on` の順序も、自分で実装することになる

**評価**: 案 A より危険は減る。一方で、止められる範囲は「全コンテナ」のままで、プロキシのコンテナも増える。ホストのエージェント（案 C）より複雑なのに、制御は粗い。**次善の策にとどめる。**

---

## 4. 案 C（推奨）: ホスト側のエージェントがジョブを取りに行く

### 4.1 流れ

```
ブラウザ ──POST(CSRF 保護)──▶ dashboard ──INSERT──▶ SQLite (SiteJob: pending)
                                   ▲
host: manage.py devenv agent ──GET /api/site-jobs/next (Bearer)── 取り出し(running)
      └─ docker compose (wp-main で) up -d --wait wp1-wordpress / stop wp1-wordpress wp1-db
      └─ POST /api/site-jobs/{id}/result (Bearer)   ── 成否・要約を書き込むのは dashboard
      └─ POST /api/site-status (Bearer、定期)        ── docker compose ps --format json の要約
```

- DB に書き込むのはダッシュボードだけで、CLI は既存の `operations.call_api()`（Bearer 認証と Caddy の CA での検証）をそのまま使える。`dev-operation-history` の方針と矛盾しない
- ホストの Compose で、wp-main をプロジェクトディレクトリとして実行する。そのため、相対パス・`.env`・`include` は今と同じに解決される。2.3 のパスの食い違いは起きない
- `up -d` は、依存するサービスを「起動していなければ一緒に起動する」 — <https://docs.docker.com/reference/cli/docker/compose/up/>。`wp1-wordpress` を指定すれば `wp1-db` も起動し、`--wait` で healthy になるまで待てる。`down` した後でも作り直せる
- `restart: unless-stopped` は「手動などで止めたコンテナは、デーモンを再起動しても起動しない」 — <https://docs.docker.com/engine/containers/start-containers-automatically/>。ダッシュボードで止めた状態は、Docker（OrbStack）を再起動しても保たれる
- エージェントが実行できる操作を「サイト ID × {start, stop}」の固定の組み合わせに限れば、ダッシュボードが乗っ取られても、wp1 / wp2 の起動と停止しかできない。これが最大の利点になる

### 4.2 常駐のさせ方（macOS の launchd）

- ユーザーごとのエージェントは `~/Library/LaunchAgents` に plist を置く。「ユーザーがログインしている間だけ動く」 — <https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html>（Apple のアーカイブ文書）
- 使うキー: `Label`、`ProgramArguments`（必須）、`KeepAlive`（常駐）、または `StartInterval`（一定間隔で起動）。`WorkingDirectory`、`EnvironmentVariables`、`StandardErrorPath` — 同上、および `man launchd.plist`（macOS 25.6 のローカルの man ページで確認）
- 注意: launchd から起動したプロセスは、ログインシェルの `PATH` を引き継がない。`ProgramArguments` には `uv` の絶対パスを書き、`EnvironmentVariables` の `PATH` に `docker` のあるディレクトリ（OrbStack なら `~/.orbstack/bin`、Docker Desktop なら `/usr/local/bin`）を入れる。Docker のコンテキストは `~/.docker/config.json` から読まれるので、`HOME` があれば今と同じエンジンにつながる
- 最初は launchd を使わず、`uv run manage.py devenv agent` をターミナルで動かしっぱなしにする形でも十分に動く。launchd の登録は `devenv install` の任意の手順（`--with-agent`）にするか、別のサブコマンドにして、`uninstall` で外す

### 4.3 状態の表示（Docker に触れずに）

| 手段 | 分かること | 備考 |
| --- | --- | --- |
| エージェントの定期報告（例: 10 秒ごと） | `docker compose ps` の State と Health（running / exited / healthy） | 報告の時刻を表示し、古ければ「エージェント停止中」とする。ボタンを無効にする判定にも使う |
| ダッシュボードから `http://wp1-wordpress/` への HTTP の疎通 | WordPress が応答しているか | `wp1-wordpress` は `wp-global-net` にいる。ダッシュボードも同じネットワークにいるため届く。DB は `wp1-internal` にいて届かないので、DB の状態はエージェントの報告に頼る |
| ジョブの状態 | pending / running / succeeded / failed と要約 | 操作履歴の一覧に並べて表示できる |

---

## 5. その他の案

| 案 | 評価 | 根拠 |
| --- | --- | --- |
| Docker Desktop の拡張機能 | 拡張機能は「ホスト上で高い権限で動き、Docker Engine に直接アクセスでき、ネイティブのバイナリを実行できる」。Docker Desktop の UI の中で動くもので、今のダッシュボード（Caddy 経由の Django）とは別物になる。このマシンは OrbStack なので、そもそも使えない（OrbStack が対応しているという記述は見つからなかった）。不採用 | <https://docs.docker.com/extensions/> |
| コンテナから `host.docker.internal` 経由で SSH | `host.docker.internal` は「ホストの内部 IP に解決される」。macOS で「リモートログイン」を有効にして、ダッシュボードに SSH の秘密鍵を持たせる必要がある。`authorized_keys` の `command=` で実行できるコマンドは縛れる。しかし、システムの設定の変更と鍵の管理が増えるうえ、実質的には案 C と同じ「ホストで実行する」形を、より危険な経路で実現することになる。不採用 | <https://docs.docker.com/desktop/features/networking/networking-how-tos/> |
| Compose の `profiles` | 「profile に割り当てたサービスは、その profile が有効なときだけ起動・停止する」。起動時にどのサービスを含めるかを選ぶ仕組みで、誰がどこから実行するかという問題は解決しない。ホストのエージェントの中で `--profile` を使う余地はあるが、`stop <service>` で足りる。不要 | <https://docs.docker.com/compose/how-tos/profiles/> |
| ホストに小さな HTTP サーバーを立て、ダッシュボードから押しに行く（push 型） | ホストでポートを待ち受けることになり、その認証とバインド先の管理が増える。ダッシュボードからホストへの接続経路も必要になる。pull 型（案 C）なら、ホスト側は外向きの HTTPS だけで済み、既存の `call_api()` を使い回せる。案 C より劣る | — |

---

## 6. 比較

| 観点 | A: ソケットを直接渡す | B: ソケットプロキシ | **C: ホストのエージェント（pull 型）** |
| --- | --- | --- | --- |
| ダッシュボードが乗っ取られたときの被害 | ホストの root 相当 | 全コンテナの start / stop（`CONTAINERS`+`POST` を許可すれば root 相当） | **wp1 / wp2 の start / stop だけ** |
| 対象を wp1 / wp2 に限れるか | アプリのコード次第 | できない（URL の接頭辞だけ） | エージェントの許可リストで限れる |
| `down` 後の作成、`depends_on`、healthy の待機 | Compose を使えばパスの食い違いがある。API だけならできない | できない | できる（ホストの Compose をそのまま使う） |
| 既存の方針（Web が DB に書き、CLI は API を呼ぶ） | 関係しない | 関係しない | 合う（`call_api()` を再利用できる） |
| エンジンの違い（OrbStack / Docker Desktop・ECI）の影響 | 受ける（ソケットのパス、GID、ECI） | 受ける | 受けない（ホストの `docker` CLI とコンテキストを使う） |
| 追加するもの | マウント、`group_add` | プロキシのコンテナ、場合によって 2 つ | API 2〜3 本、モデル 1 つ、CLI のサブコマンド 1 つ、任意で launchd の plist |
| 弱点 | 危険すぎる | 制御が粗い | エージェントが動いていないと操作できない（状態の表示で知らせる）。ジョブの取得に数秒の遅れがある |

---

## 7. 実装の概略（案 C。リポジトリは変更していない）

1. **ダッシュボード（Web 側）**
   - モデル `SiteJob(site: wp1|wp2, action: start|stop, state: pending|running|succeeded|failed, requested_at, claimed_at, finished_at, summary)`。同じサイトで未完了のジョブがあるときは、新しいジョブを受け付けない
   - モデル `SiteStatus(site, services: JSON, reported_at)`。エージェントからの最新の報告だけを持つ
   - 画面のボタン用の POST。Django Ninja は、Cookie 認証以外では CSRF の検証が既定で無効になる — <https://django-ninja.dev/reference/csrf/>。今の `MIDDLEWARE` には `CsrfViewMiddleware` がないので、この POST だけは `csrf_protect` を付けた Django のビューにするか、ミドルウェアを加える — <https://docs.djangoproject.com/en/5.2/howto/csrf/>。これがないと、ブラウザで開いた別のサイトから、フォームの POST でサイトを止められてしまう
   - Bearer 認証の API（既存の `TokenAuth`）:
     - `POST /api/site-jobs/claim`: 最も古い pending のジョブを running にして返す。なければ 204
     - `POST /api/site-jobs/{id}/result`: 成否と要約を書き込み、`Operation` にも 1 件記録する（コマンド名は `site-start` / `site-stop`）
     - `PUT /api/site-status`: エージェントの定期報告
   - running のまま一定時間（例: 5 分）たったジョブは failed にする（エージェントが途中で落ちたとき用）
2. **CLI（ホスト側）**
   - `devenv site start|stop <wp1|wp2>`: 手動でも実行できる本体。実行するコマンドはサイト ID から決め、許可リストの外は拒否する
     - 一括起動（`wp1-wordpress` のラベル `com.docker.compose.project` が `wp-main`）のとき: `MAIN_DIR` で `docker compose up -d --wait wp1-wordpress`、または `docker compose stop wp1-wordpress wp1-db`
     - 単体起動（プロジェクトが `wp-wp1`）のとき: `../wp-wp1` で同じサービス名を指定する。どちらの場合でも、ラベルを見てそのプロジェクトで実行し、プロジェクトを二重に作らない
   - `devenv agent`: 2〜3 秒ごとに `claim` を呼び、`site` の処理を実行して `result` を送る。10 秒ごとに `docker compose ps --format json` の要約を `site-status` に送る。ダッシュボードに届かないときは待って再試行する（`call_api()` の 3 秒のタイムアウトはそのまま使える）
   - 任意: `devenv agent install|uninstall` で `~/Library/LaunchAgents/com.yamashita109.wp-main.agent.plist` を置き、`launchctl bootstrap gui/$(id -u) <plist>` で登録する（`KeepAlive`、`WorkingDirectory=MAIN_DIR`、`EnvironmentVariables.PATH`、`StandardErrorPath=.local/agent.log`）。`devenv uninstall` でも外す
3. **表示**: サイトの行に「状態（running/healthy・stopped）・報告の時刻・起動/停止ボタン・実行中のジョブ」を出す。報告が古いときは「エージェントが停止中です。`uv run manage.py devenv agent` を実行してください」と表示し、ボタンを無効にする
4. **spec**: `dev-dashboard` に「サイトの起動・停止」、`dev-operation-history` に `site-start` / `site-stop` の記録を加える。新しい capability（例: `dev-site-power`）として OpenSpec の change にする

---

## 未確認の点

- OrbStack と Docker Desktop で、コンテナ内から見えるソケットの所有者と GID（2.2）。状態を変える検証になるため、実施していない。案 C を採るなら不要
- OrbStack が Docker Desktop の拡張機能に対応しているか。公式ドキュメントに記述が見つからなかった
