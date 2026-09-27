import { afterAll, beforeAll, expect, test } from "bun:test";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const MAIN_DIR = resolve(import.meta.dir, "..");
const PORT = 18000 + Math.floor(Math.random() * 1000);
const BASE = `http://127.0.0.1:${PORT}`;
const ROOT_PASSWORD = "e2e-root-secret";
const MASK = "••••••••••";

let workDir: string;
let server: ReturnType<typeof Bun.spawn>;
let view: Bun.WebView;

function siteEnv(id: string, image: string, port: number): string {
  return [
    `WP_IMAGE=${image}`,
    `WP_DEBUG_PORT=${port}`,
    `WP_HOME=https://local.${id}.yamashita109.com`,
    "WP_ADMIN_USER=admin",
    `WP_ADMIN_PASSWORD=${id}-admin-secret`,
    "",
  ].join("\n");
}

async function waitFor<T>(read: () => Promise<T>, ok: (value: T) => boolean, timeout = 10_000): Promise<T> {
  const deadline = Date.now() + timeout;
  let value = await read();
  while (!ok(value)) {
    if (Date.now() > deadline) throw new Error(`timeout: last value ${JSON.stringify(value)}`);
    await Bun.sleep(100);
    value = await read();
  }
  return value;
}

beforeAll(async () => {
  // 実際のサイトの .env と .local/db.sqlite3 を使わないよう、一時ディレクトリで動かす
  workDir = mkdtempSync(join(tmpdir(), "wp-main-e2e-"));
  for (const [id, image, port] of [["wp1", "wordpress:7.1-apache", 8081], ["wp2", "wordpress:6.7-apache", 8082]] as const) {
    mkdirSync(join(workDir, `wp-${id}`));
    writeFileSync(join(workDir, `wp-${id}`, ".env"), siteEnv(id, image, port));
  }
  mkdirSync(join(workDir, "wp-main"));
  writeFileSync(join(workDir, "wp-main", ".env"), `DB_USER=wordpress\nDB_PASSWORD=e2e-user-secret\nDB_ROOT_PASSWORD=${ROOT_PASSWORD}\n`);
  const env = {
    ...process.env,
    DJANGO_DB_PATH: join(workDir, "db.sqlite3"),
    WP_MAIN_ROOT: workDir,
    WP_MAIN_DIR: join(workDir, "wp-main"),
  };
  const migrate = Bun.spawnSync(["uv", "run", "manage.py", "migrate", "-v0"], { cwd: MAIN_DIR, env });
  if (migrate.exitCode !== 0) throw new Error(migrate.stderr.toString());
  server = Bun.spawn(["uv", "run", "manage.py", "runserver", `127.0.0.1:${PORT}`, "--noreload"], {
    cwd: MAIN_DIR, env, stdout: "ignore", stderr: "ignore",
  });
  await waitFor(() => fetch(`${BASE}/healthz`).then((r) => r.ok, () => false), Boolean, 30_000);
  view = new Bun.WebView({ width: 1400, height: 1000 });
}, 60_000);

afterAll(async () => {
  await view?.close();
  server?.kill();
  await server?.exited;
  rmSync(workDir, { recursive: true, force: true });
});

test("Tailwind でビルドした CSS が当たっている", async () => {
  await view.navigate(`${BASE}/`);
  const style = await view.evaluate(`(() => {
    const header = getComputedStyle(document.querySelector("header"));
    const button = getComputedStyle(document.querySelector(".icon-button"));
    return { display: header.display, background: header.backgroundColor, button: button.width };
  })()`);
  expect(style.display).toBe("flex");
  expect(style.background).not.toBe("rgba(0, 0, 0, 0)");
  expect(style.button).toBe("30px");
});

test("DB の root のパスワードは既定で伏せ、表示ボタンで切り替わる", async () => {
  await view.navigate(`${BASE}/`);
  const field = `document.querySelector('[data-secret="db-root"]').textContent`;
  expect(await view.evaluate(field)).toBe(MASK);
  expect(await view.evaluate("document.documentElement.outerHTML.includes('" + ROOT_PASSWORD + "')")).toBe(false);

  await view.click('[data-secret-toggle="db-root"]');
  expect(await waitFor(() => view.evaluate(field), (text) => text === ROOT_PASSWORD)).toBe(ROOT_PASSWORD);

  await view.click('[data-secret-toggle="db-root"]');
  expect(await waitFor(() => view.evaluate(field), (text) => text === MASK)).toBe(MASK);
});

test("コピーのボタンでトーストが出る", async () => {
  await view.navigate(`${BASE}/`);
  await view.click('[data-copy-text][data-label="ホストとポート"]');
  // ヘッドレスではクリップボードの権限がないことがあるため、成否どちらの案内でもトーストが出ればよい
  const message = await waitFor(() => view.evaluate(`document.getElementById("toast").textContent`), (text) => text !== "");
  expect(message).toMatch(/^ホストとポートを(コピーしました|コピーできませんでした)$/);
});
