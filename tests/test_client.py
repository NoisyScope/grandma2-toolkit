from pathlib import Path

import pytest

from ma2kit import cli
from ma2kit.client import (
    LoginError,
    MA2Client,
    RemoteDisabledError,
    clean,
    risky_reason,
    split_prompt,
    strip_telnet,
)

from fake_ma2 import FakeMA2

# Shape copied from a real onPC 3.9.61 reply (group names changed).
LIST_GROUP = (
    "\x1b[33m        No.  Name         Info  \n\r"
    "Group 1 1    All PARs\n\r"
    "Group 2 2    Beams\n\r"
)


def make_client(port: int, tmp_path: Path | None = None, **kw) -> MA2Client:
    transcript = tmp_path / "transcript.log" if tmp_path else None
    return MA2Client("127.0.0.1", port, timeout=3, transcript=transcript, idle=0.1, **kw)


def test_clean_and_split_prompt():
    text = clean("\x1b[32mhello\n\rworld\r\n\r [Group]>")
    body, prompt = split_prompt(text)
    assert prompt == "Group"
    assert body.split() == ["hello", "world"]


def test_strip_telnet_negotiation():
    assert strip_telnet(bytes([255, 251, 1]) + b"ok" + bytes([255, 255])) == b"ok\xff"


@pytest.mark.parametrize(
    "command, flagged",
    [
        ("Delete Group 5", True),
        ("del group 5", True),
        ("Store Group 5 /nc", True),
        ("NewShow test", True),
        ("LoadShow x", True),
        ("List Group", False),
        ("Fixture 1 Thru 4", False),
    ],
)
def test_risky_reason(command, flagged):
    assert (risky_reason(command) is not None) is flagged


def test_greeting_login_and_list(tmp_path):
    with FakeMA2(responses={"List Group": LIST_GROUP}) as fake, make_client(fake.port, tmp_path) as c:
        c.connect()
        assert c.user == "guest"
        assert c.prompt == "Group"
        c.login("toolkit", "s3cret")
        assert c.user == "toolkit"
        result = c.send("List Group")
        assert result.ok
        assert result.text.splitlines()[0].split() == ["No.", "Name", "Info"]  # echo removed
        assert result.text.splitlines()[-1] == "Group 2 2    Beams"  # trailing blanks removed
        assert result.prompt == "Channel"


def test_login_failure_raises():
    with FakeMA2() as fake, make_client(fake.port) as c:
        c.connect()
        with pytest.raises(LoginError, match="Error #72"):
            c.login("toolkit", "wrong")


def test_remote_disabled():
    with FakeMA2(disabled=True) as fake, make_client(fake.port) as c:
        with pytest.raises(RemoteDisabledError):
            c.connect()


def test_unknown_command_reports_error():
    with FakeMA2() as fake, make_client(fake.port) as c:
        c.connect()
        c.login("toolkit", "s3cret")
        result = c.send("List Nonsense")
        assert not result.ok
        assert result.error_code == (14, "OBJECT DOES NOT EXIST")


def test_password_never_in_transcript_or_result(tmp_path):
    with FakeMA2() as fake, make_client(fake.port, tmp_path) as c:
        c.connect()
        result = c.login("toolkit", "s3cret")
        assert "s3cret" not in result.command
        assert "s3cret" not in result.text
    log = (tmp_path / "transcript.log").read_text(encoding="utf-8")
    assert "Login" in log
    assert "s3cret" not in log


def test_dry_run_sends_nothing():
    c = MA2Client("127.0.0.1", 1, dry_run=True)  # port 1: would fail if contacted
    c.connect()
    c.login("toolkit", "s3cret")
    result = c.send("Store Group 500")
    assert not result.sent
    assert c.sent_log == ['Login "toolkit" "****"', "Store Group 500"]


def test_rejects_multiline_and_quotes():
    c = MA2Client(dry_run=True)
    with pytest.raises(ValueError):
        c.send("List\nDelete Group 1")
    with pytest.raises(ValueError):
        c.login("toolkit", 'pa"ss')


def test_cli_cmd_against_fake(tmp_path, capsys):
    with FakeMA2(responses={"List Group": LIST_GROUP}) as fake:
        cfg = tmp_path / "config.toml"
        cfg.write_text(
            f'[console]\nport = {fake.port}\nuser = "toolkit"\npassword = "s3cret"\ntimeout = 3\n',
            encoding="utf-8",
        )
        assert cli.main(["--config", str(cfg), "cmd", "List", "Group"]) == 0
    out = capsys.readouterr().out
    assert "Beams" in out


def test_cli_doctor_without_password(tmp_path, capsys):
    with FakeMA2() as fake:
        cfg = tmp_path / "config.toml"
        cfg.write_text(f'[console]\nport = {fake.port}\ntimeout = 3\n', encoding="utf-8")
        assert cli.main(["--config", str(cfg), "doctor"]) == 0
    out = capsys.readouterr().out
    assert "Telnet enabled" in out
    assert "login check skipped" in out
