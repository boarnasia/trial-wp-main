import sys

NEW_COMMAND = "uv run manage.py devenv"


def replacement(args: list[str]) -> str:
    if not args or args[0] == "help":
        return "uv run manage.py help devenv"
    name, rest = args[0].removeprefix("dev-env:"), args[1:]
    return " ".join([NEW_COMMAND, name, *rest])


def main() -> None:
    # 手順書や履歴に残る旧コマンドで誤って実行しないよう、案内だけして失敗させる
    print(f"uv run cli は廃止しました。代わりに次を実行してください:\n  {replacement(sys.argv[1:])}", file=sys.stderr)
    sys.exit(2)
