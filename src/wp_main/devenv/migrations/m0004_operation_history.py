from ._env import add_secret, rebuild_if_running

VERSION = 4
DESCRIPTION = "操作履歴を導入し、wp-main の .env に DASHBOARD_API_TOKEN を加える"
REQUIRES_SUDO = False
DESTRUCTIVE = False
LOSES = ""


def up(ctx) -> None:
    add_secret(ctx, "DASHBOARD_API_TOKEN")
    # DB のボリューム、環境変数、起動時の django:migration を反映する
    rebuild_if_running(ctx)
