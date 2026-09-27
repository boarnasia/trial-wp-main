import json
import re
import socket
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .config import CADDY_CONTAINER, CADDY_ROOT_CERT, CADDY_SERVICE, DASHBOARD_DOMAIN, MAIN_DIR, MYSQL_CONTAINER, NETWORK, SITES, Site
from . import session, versioning
from .docker import compose
from .runner import Runner
from .sites import SECRET_PLACEHOLDER, dashboard_port, read_env
from .trust import SYSTEM_KEYCHAIN, pem_sha1

OK, WARN, FAIL, SKIP = "OK", "WARN", "FAIL", "SKIP"
STATUSES = (OK, WARN, FAIL, SKIP)
GROUPS = {
    "config": "構成",
    "host": "ホスト",
    "container": "共有インフラ",
    "site": "サイト",
    "http": "HTTP と WordPress",
}
# macOS 標準の curl だけがキーチェーンの CA を参照する（Homebrew 版や Python の ssl は参照しない）
CURL = "/usr/bin/curl"
CURL_TIMEOUT = "5"
CURL_SSL_ERROR = 60
OUTSIDE_SESSION = "開発セッションの外です（uv run manage.py serve up で始まります）"
INSTALL_HINT = "uv run manage.py devenv install を実行してください"


@dataclass
class Result:
    status: str
    message: str
    hint: str = ""


@dataclass
class Check:
    id: str
    group: str
    title: str
    run: Callable[[], Result]
    requires: tuple[str, ...] = ()


@dataclass
class Outcome:
    id: str
    group: str
    title: str
    status: str
    message: str
    hint: str = ""


def evaluate(checks: list[Check]) -> list[Outcome]:
    statuses: dict[str, str] = {}
    # 前提をたどって SKIP になった項目では、入れ子にせず大もとの項目と理由だけを見せる
    causes: dict[str, str] = {}
    outcomes = []
    for check in checks:
        blocked = [req for req in check.requires if statuses.get(req) in (FAIL, SKIP)]
        if blocked:
            cause = ", ".join(dict.fromkeys(causes[req] for req in blocked))
            result = Result(SKIP, f"前提の項目が OK ではありません: {cause}")
        else:
            try:
                result = check.run()
            except Exception as error:  # 1 項目の想定外の失敗で残りの確認を止めない
                result = Result(FAIL, f"確認中にエラーが発生しました: {error}")
            cause = f"{check.id}（{result.message}）"
        statuses[check.id] = result.status
        causes[check.id] = cause
        outcomes.append(Outcome(check.id, check.group, check.title, result.status, result.message, result.hint))
    return outcomes


def summarize(outcomes: list[Outcome]) -> dict[str, int]:
    return {status: sum(1 for o in outcomes if o.status == status) for status in STATUSES}


def to_json(outcomes: list[Outcome]) -> str:
    summary = summarize(outcomes)
    payload = {"ok": summary[FAIL] == 0, "summary": summary, "checks": [asdict(o) for o in outcomes]}
    return json.dumps(payload, ensure_ascii=False, indent=2)


def resolve_ipv4(domain: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(domain, 443, socket.AF_INET, socket.SOCK_STREAM)
    except socket.gaierror:
        return []
    return sorted({info[4][0] for info in infos})


def parse_compose_ps(output: str) -> dict[str, dict]:
    """Compose のバージョンにより、1 行 1 オブジェクトの形式と配列の形式がある。"""
    text = output.strip()
    if not text:
        return {}
    if text.startswith("["):
        items = json.loads(text)
    else:
        items = [json.loads(line) for line in text.splitlines() if line.strip()]
    return {item["Name"]: item for item in items}


@dataclass
class HttpResponse:
    code: int
    redirect: str
    body: str
    verified: bool


def probe_dashboard(port: int) -> str | None:
    """ホストのダッシュボードが応答すれば None、しなければ理由を返す。"""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=2) as response:
            return None if response.status == 200 else f"HTTP {response.status}"
    except urllib.error.HTTPError as error:
        return f"HTTP {error.code}"
    except (urllib.error.URLError, OSError) as error:
        return str(getattr(error, "reason", error))


def expected_major(site: Site, env: dict[str, str]) -> str | None:
    # サイト設定の正本はサイトの .env なので、SITES の既定値では判定しない
    image = env.get("WP_IMAGE", "")
    match = re.search(r":(\d+)", image)
    return match.group(1) if match else None


@dataclass
class HealthContext:
    runner: Runner
    root: Path
    main_dir: Path = MAIN_DIR
    resolver: Callable[[str], list[str]] = resolve_ipv4
    probe: Callable[[int], str | None] = probe_dashboard
    session_check: Callable[[], bool] = session.is_running
    _in_session: bool | None = field(default=None, init=False)
    _containers: dict | None = field(default=None, init=False)
    _responses: dict[str, HttpResponse] = field(default_factory=dict, init=False)

    def in_session(self) -> bool:
        if self._in_session is None:
            self._in_session = self.session_check()
        return self._in_session

    def cmd(self, args: list[str], cwd: Path | None = None):
        return self.runner.run(args, cwd=cwd, check=False, mutate=False)

    def containers(self) -> dict[str, dict]:
        if self._containers is None:
            result = compose(
                self.runner, "ps", "--all", "--format", "json", cwd=self.main_dir, check=False, mutate=False
            )
            if result.returncode != 0:
                detail = (result.stderr or "").strip().splitlines()
                raise RuntimeError(detail[-1] if detail else "docker compose ps が失敗しました")
            self._containers = parse_compose_ps(result.stdout)
        return self._containers

    def fetch(self, url: str) -> HttpResponse | str:
        """応答を返す。接続できなければエラーメッセージ（str）を返す。"""
        if url in self._responses:
            return self._responses[url]
        base = [CURL, "-sS", "--max-time", CURL_TIMEOUT, "-w", "\n%{http_code} %{redirect_url}"]
        result = self.cmd([*base, url])
        verified = True
        if result.returncode == CURL_SSL_ERROR:
            verified = False
            result = self.cmd([*base, "-k", url])
        if result.returncode != 0:
            return (result.stderr or f"curl が終了コード {result.returncode} で失敗しました").strip()
        body, _, status_line = result.stdout.rpartition("\n")
        code, _, redirect = status_line.partition(" ")
        response = HttpResponse(int(code), redirect.strip(), body, verified)
        self._responses[url] = response
        return response


def config_checks(ctx: HealthContext) -> list[Check]:
    checks = []

    def env_check(directory: Path) -> Callable[[], Result]:
        def run() -> Result:
            env_file = directory / ".env"
            if not env_file.exists():
                return Result(FAIL, f"{env_file} がありません", INSTALL_HINT)
            leftovers = [key for key, value in read_env(directory).items() if value == SECRET_PLACEHOLDER]
            if leftovers:
                return Result(
                    WARN,
                    f"{SECRET_PLACEHOLDER} のままの値があります: {', '.join(leftovers)}",
                    f"{env_file} の値をランダムな文字列に書き換えてください",
                )
            return Result(OK, str(env_file))

        return run

    for site in SITES:
        path = ctx.root / site.dir_name

        def repo(site=site, path=path) -> Result:
            if not path.exists():
                return Result(FAIL, f"{path} がありません", INSTALL_HINT)
            origin = ctx.cmd(["git", "-C", str(path), "remote", "get-url", "origin"]).stdout.strip()
            if origin != site.remote:
                return Result(
                    FAIL,
                    f"origin が {origin or '(なし)'} です（期待値: {site.remote}）",
                    f"{path} を確認し、{site.remote} の clone に置き換えてください",
                )
            return Result(OK, f"{path} ({origin})")

        checks.append(Check(f"config.repo.{site.id}", "config", f"{site.dir_name} リポジトリ", repo))
        checks.append(
            Check(f"config.env.{site.id}", "config", f"{site.dir_name}/.env", env_check(path), (f"config.repo.{site.id}",))
        )
    checks.append(Check("config.env.main", "config", "wp-main/.env", env_check(ctx.main_dir)))

    def version() -> Result:
        installed, newest = versioning.installed_version(ctx.root), versioning.latest()
        if installed is None:
            return Result(FAIL, "環境が導入されていません", INSTALL_HINT)
        if installed < newest:
            return Result(WARN, f"{installed}（最新: {newest}）", f"{versioning.MIGRATE_COMMAND} を実行してください")
        if installed > newest:
            return Result(
                FAIL, f"{installed}（コードの最新 {newest} より新しい）", "wp-main を git pull してコードを更新してください"
            )
        return Result(OK, f"{installed}（最新）")

    checks.append(Check("config.version", "config", "環境バージョン", version))
    return checks


def host_checks(ctx: HealthContext) -> list[Check]:
    checks = []
    targets = [(site.id, site.domain, INSTALL_HINT) for site in SITES]
    # ダッシュボードのドメインは migration 2 で hosts に加わるため、既存の環境では migrate を案内する
    targets.append(("dashboard", DASHBOARD_DOMAIN, f"{versioning.MIGRATE_COMMAND} または {INSTALL_HINT}"))
    for target_id, domain, hint in targets:

        def dns(domain=domain, hint=hint) -> Result:
            addresses = ctx.resolver(domain)
            if "127.0.0.1" in addresses:
                return Result(OK, f"{domain} → 127.0.0.1")
            found = ", ".join(addresses) if addresses else "解決できません"
            return Result(
                FAIL,
                f"{domain} が 127.0.0.1 になりません（{found}）",
                f"{hint}。直後なら sudo killall -HUP mDNSResponder で DNS キャッシュを消してください",
            )

        checks.append(Check(f"host.dns.{target_id}", "host", f"名前解決 {domain}", dns))

    def network() -> Result:
        if ctx.cmd(["docker", "network", "inspect", NETWORK]).returncode == 0:
            return Result(OK, NETWORK)
        return Result(FAIL, f"{NETWORK} がありません", f"docker network create {NETWORK} または {INSTALL_HINT}")

    checks.append(Check("host.network", "host", f"ネットワーク {NETWORK}", network))

    def dashboard() -> Result:
        port = dashboard_port(ctx.main_dir)
        # ダッシュボードは開発セッションの間だけ動くものなので、セッションの外で止まっていても故障とはみなさない
        if not ctx.in_session():
            return Result(SKIP, OUTSIDE_SESSION)
        problem = ctx.probe(port)
        if problem:
            return Result(FAIL, f"127.0.0.1:{port} で応答しません（{problem}）", "uv run manage.py serve logs dashboard を確認してください")
        return Result(OK, f"127.0.0.1:{port}")

    checks.append(Check("host.dashboard", "host", "ダッシュボードのプロセス", dashboard))
    return checks


def ca_check(ctx: HealthContext) -> Check:
    def run() -> Result:
        pem = ctx.cmd(
            ["docker", "compose", "exec", "-T", CADDY_SERVICE, "cat", CADDY_ROOT_CERT], cwd=ctx.main_dir
        )
        if pem.returncode != 0:
            return Result(FAIL, "Caddy のルート証明書を読み取れません", "docker compose logs caddy を確認してください")
        sha1 = pem_sha1(pem.stdout)
        keychain = ctx.cmd(
            ["security", "find-certificate", "-a", "-c", "Caddy Local Authority", "-Z", SYSTEM_KEYCHAIN]
        ).stdout
        if f"SHA-1 hash: {sha1}" in keychain:
            return Result(OK, f"SHA-1 {sha1}")
        return Result(
            WARN,
            f"Caddy の現在の CA（SHA-1 {sha1}）がキーチェーンに登録されていません。ブラウザで証明書の警告が出ます",
            "uv run manage.py devenv install を --skip-trust なしで実行してください",
        )

    return Check("host.ca", "host", "Caddy ローカル CA の信頼登録", run, (f"container.{CADDY_CONTAINER}",))


INFRA_HINT = "uv run manage.py serve down の後に uv run manage.py serve up で始め直してください"


def container_checks(ctx: HealthContext) -> list[Check]:
    checks = []
    for name in (CADDY_CONTAINER, MYSQL_CONTAINER):

        def run(name=name) -> Result:
            # 共有インフラも開発セッションの間だけ動くものなので、セッションの外で止まっていても故障とはみなさない
            if not ctx.in_session():
                return Result(SKIP, OUTSIDE_SESSION)
            info = ctx.containers().get(name)
            if info is None:
                return Result(FAIL, "コンテナがありません", INFRA_HINT)
            state, health = info.get("State", ""), info.get("Health", "")
            if state != "running":
                return Result(FAIL, f"状態: {state}", INFRA_HINT)
            if name == MYSQL_CONTAINER and health != "healthy":
                return Result(FAIL, f"ヘルスチェック: {health or '未設定'}", f"docker compose logs {name} を確認してください")
            return Result(OK, f"{state}{f' ({health})' if health else ''}")

        checks.append(Check(f"container.{name}", "container", name, run, ("host.network",)))
    return checks


def site_checks(ctx: HealthContext) -> list[Check]:
    checks = []
    for site in SITES:

        def run(site=site) -> Result:
            info = ctx.containers().get(site.wordpress_service)
            state = info.get("State", "") if info else ""
            if state != "running":
                # サイトは開発セッションの間だけ動くものなので、止まっていても故障とはみなさない
                return Result(SKIP, f"停止中（uv run manage.py serve up --site={site.id} で起動します）")
            return Result(OK, state)

        checks.append(Check(
            f"site.{site.id}", "site", site.wordpress_service, run,
            (f"config.repo.{site.id}", f"container.{MYSQL_CONTAINER}"),
        ))
    return checks


def http_checks(ctx: HealthContext) -> list[Check]:
    checks = []
    for site in SITES:
        https_url = f"https://{site.domain}/"
        base_requires = (f"host.dns.{site.id}", f"container.{CADDY_CONTAINER}", f"site.{site.id}")

        def https(site=site, url=https_url) -> Result:
            response = ctx.fetch(url)
            if isinstance(response, str):
                return Result(FAIL, f"接続できません: {response}", "docker compose logs caddy を確認してください")
            if response.code != 200 and "/wp-admin/install.php" not in response.redirect:
                return Result(FAIL, f"HTTP {response.code}", f"docker compose logs {site.wordpress_service} を確認してください")
            if not response.verified:
                return Result(
                    WARN,
                    f"HTTP {response.code}。ただし証明書を検証できません",
                    "uv run manage.py devenv install を --skip-trust なしで実行してください",
                )
            return Result(OK, f"HTTP {response.code}")

        def redirect(site=site) -> Result:
            response = ctx.fetch(f"http://{site.domain}/")
            if isinstance(response, str):
                return Result(FAIL, f"接続できません: {response}", "docker compose logs caddy を確認してください")
            if response.code in (301, 302, 307, 308) and response.redirect.startswith(f"https://{site.domain}/"):
                return Result(OK, f"HTTP {response.code} → {response.redirect}")
            return Result(FAIL, f"HTTP {response.code} → {response.redirect or '(なし)'}", "Caddyfile を確認してください")

        def installed(site=site, url=https_url) -> Result:
            response = ctx.fetch(url)
            if "/wp-admin/install.php" in response.redirect:
                return Result(FAIL, "WordPress が未インストールです", INSTALL_HINT)
            return Result(OK, "インストール済み")

        def version(site=site, url=https_url) -> Result:
            match = re.search(r'<meta name="generator" content="WordPress ([\d.]+)"', ctx.fetch(url).body)
            if not match:
                return Result(WARN, "バージョンを取得できません", "テーマが generator メタタグを出力しているか確認してください")
            actual = match.group(1)
            expected = expected_major(site, read_env(ctx.root / site.dir_name))
            if expected and actual.split(".")[0] != expected:
                return Result(
                    WARN,
                    f"WordPress {actual}（期待するメジャーバージョン: {expected}）",
                    f"{site.dir_name}/.env の WP_IMAGE を確認してください",
                )
            return Result(OK, f"WordPress {actual}")

        checks += [
            Check(f"http.https.{site.id}", "http", f"HTTPS {site.domain}", https, base_requires),
            Check(f"http.redirect.{site.id}", "http", f"HTTP → HTTPS {site.domain}", redirect, base_requires),
            Check(f"http.installed.{site.id}", "http", f"インストール済み {site.domain}", installed,
                  (f"http.https.{site.id}",)),
            Check(f"http.version.{site.id}", "http", f"バージョン {site.domain}", version,
                  (f"http.installed.{site.id}",)),
        ]
    return [*checks, *dashboard_http_checks(ctx)]


def dashboard_http_checks(ctx: HealthContext) -> list[Check]:
    https_url = f"https://{DASHBOARD_DOMAIN}/"
    base_requires = ("host.dns.dashboard", f"container.{CADDY_CONTAINER}")

    def https() -> Result:
        response = ctx.fetch(https_url)
        if isinstance(response, str):
            return Result(FAIL, f"接続できません: {response}", "docker compose logs caddy を確認してください")
        if response.code != 200:
            # ホストのプロセスは応答しているので、502 なら Caddy からホストへの転送を疑う
            return Result(FAIL, f"HTTP {response.code}", "docker compose logs caddy を確認してください")
        if not response.verified:
            return Result(
                WARN,
                f"HTTP {response.code}。ただし証明書を検証できません",
                "uv run manage.py devenv install を --skip-trust なしで実行してください",
            )
        return Result(OK, f"HTTP {response.code}")

    def redirect() -> Result:
        response = ctx.fetch(f"http://{DASHBOARD_DOMAIN}/")
        if isinstance(response, str):
            return Result(FAIL, f"接続できません: {response}", "docker compose logs caddy を確認してください")
        if response.code in (301, 302, 307, 308) and response.redirect.startswith(https_url):
            return Result(OK, f"HTTP {response.code} → {response.redirect}")
        return Result(FAIL, f"HTTP {response.code} → {response.redirect or '(なし)'}", "Caddyfile を確認してください")

    return [
        Check("http.https.dashboard", "http", f"HTTPS {DASHBOARD_DOMAIN}", https,
              (*base_requires, "host.dashboard")),
        Check("http.redirect.dashboard", "http", f"HTTP → HTTPS {DASHBOARD_DOMAIN}", redirect, base_requires),
    ]


def build_checks(ctx: HealthContext) -> list[Check]:
    # CA はコンテナの項目を前提にするため、表示順（グループ順）とは別に後ろで評価する
    return [
        *config_checks(ctx), *host_checks(ctx), *container_checks(ctx), ca_check(ctx), *site_checks(ctx), *http_checks(ctx)
    ]


def run_health(ctx: HealthContext) -> list[Outcome]:
    outcomes = evaluate(build_checks(ctx))
    order = list(GROUPS)
    return sorted(outcomes, key=lambda outcome: order.index(outcome.group))
