import pytest

from wp_main.hosts import BEGIN, END, strip_block, with_block, write_hosts
from wp_main.runner import DevEnvError

DOMAINS = ["local.wp1.yamashita109.com", "local.wp2.yamashita109.com"]
ORIGINAL = "127.0.0.1\tlocalhost\n255.255.255.255\tbroadcasthost\n"


def test_adds_block():
    text = with_block(ORIGINAL, DOMAINS)
    assert text.startswith(ORIGINAL)
    assert "127.0.0.1\tlocal.wp1.yamashita109.com" in text
    assert text.count(BEGIN) == 1 and text.count(END) == 1


def test_idempotent():
    once = with_block(ORIGINAL, DOMAINS)
    assert with_block(once, DOMAINS) == once


def test_strip_keeps_other_lines():
    text = with_block(ORIGINAL, DOMAINS) + "10.0.0.1\tother\n"
    assert strip_block(text) == ORIGINAL + "10.0.0.1\tother\n"


def test_missing_trailing_newline():
    assert with_block("127.0.0.1 localhost", DOMAINS).startswith("127.0.0.1 localhost\n" + BEGIN)


def test_missing_end_marker_is_error():
    text = ORIGINAL + BEGIN + "\n127.0.0.1\tlocal.wp1.yamashita109.com\n10.0.0.1\tother\n"
    with pytest.raises(DevEnvError, match="がありません"):
        strip_block(text)
    with pytest.raises(DevEnvError):
        with_block(text, DOMAINS)


def test_stray_end_marker_is_error():
    with pytest.raises(DevEnvError, match="対応する"):
        strip_block(ORIGINAL + END + "\n")


def test_nested_begin_is_error():
    with pytest.raises(DevEnvError, match="閉じられる前"):
        strip_block(BEGIN + "\n" + BEGIN + "\n" + END + "\n")


def test_backup_before_overwrite(tmp_path, fake_runner):
    hosts = tmp_path / "hosts"
    hosts.write_text(ORIGINAL)
    backup = tmp_path / "hosts.bak"
    runner = fake_runner()
    assert write_hosts(runner, with_block(ORIGINAL, DOMAINS), path=hosts, backup=backup)
    copies = runner.mutating(["sudo", "cp"])
    assert copies[0] == ["sudo", "cp", "-p", str(hosts), str(backup)]
    assert copies[1][-1] == str(hosts)


def test_no_write_when_unchanged(tmp_path, fake_runner):
    hosts = tmp_path / "hosts"
    hosts.write_text(ORIGINAL)
    runner = fake_runner()
    assert not write_hosts(runner, ORIGINAL, path=hosts)
    assert runner.calls == []
