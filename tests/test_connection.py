"""Dialogs, late output, echo normalisation and reconnects."""
import pytest

from fake_ma2 import FakeMA2
from ma2kit.client import MA2Client, MA2Error, find_echo, parse_dialog


def logged_in(fake: FakeMA2, **kw) -> MA2Client:
    c = MA2Client("127.0.0.1", fake.port, timeout=3, idle=0.1, **kw)
    c.connect()
    c.login("toolkit", "s3cret")
    return c


def test_parse_dialog_real_format():
    d = parse_dialog("\nATTENTION: Please confirm! : Reload plugin engine ? :\n[1]: Ok\n 2 : Cancel\n")
    assert d.question == "Reload plugin engine ?"
    assert d.options == [(1, "Ok"), (2, "Cancel")]
    assert d.default == 1 and d.cancel_option == 2
    assert parse_dialog("no dialog here") is None


def test_parse_overwrite_dialog_real_format():
    text = (
        'Import/export folder of object type "Plugin" is "plugins".\n\n'
        'Overwrite Confirmation : At the import destination already exists object "ma2kit_info 100". :\n'
        "[1]: Overwrite\n 2 : Overwrite|All\n 3 : Insert\n 4 : Insert|All\n 5 : Cancel\n"
    )
    d = parse_dialog(text)
    assert d.question.startswith("Overwrite Confirmation : At the import destination")
    assert d.option("Overwrite") == 1 and d.cancel_option == 5 and d.default == 1
    assert len(d.options) == 5


def test_find_echo_tolerates_keyword_case():
    text = 'Executing : LUA "gma.echo(1)"\n'
    assert find_echo(text, 'Executing : Lua "gma.echo(1)"') == 0
    assert find_echo("nothing yet", "Executing : List") == -1


def test_dialog_is_cancelled_by_default():
    with FakeMA2(dialogs={"ReloadPlugins": "Reload plugin engine ?"}) as fake, logged_in(fake) as c:
        r = c.send("ReloadPlugins")
        assert fake.received[-1] == "2"
        assert r.cancelled and not r.ok
        assert r.errors == ["confirmation cancelled: Reload plugin engine ?"]
        assert r.prompt == "Channel"
        assert c.send("List Nonsense").error_code[0] == 14  # session still usable


def test_dialog_answered_by_handler():
    with FakeMA2(dialogs={"ReloadPlugins": "Reload plugin engine ?"}) as fake, logged_in(fake) as c:
        r = c.send("ReloadPlugins", confirm=lambda d: d.default)
        assert fake.received[-1] == "1"
        assert r.answer == "Ok" and r.ok


def test_late_output_and_wait_for():
    late = {'Plugin "x"': "first line\nMA2KIT_DONE x ok\n"}
    with FakeMA2(late=late) as fake, logged_in(fake) as c:
        r = c.send('Plugin "x"')
        assert r.ok
        out = c.wait_for(r"MA2KIT_DONE x (ok|error: .*)", timeout=2)
        assert "first line" in out and out.rstrip().endswith("MA2KIT_DONE x ok")


def test_lua_echo_is_recognised():
    with FakeMA2(responses={'Lua "gma.echo(1)"': ""}) as fake, logged_in(fake) as c:
        assert c.send('Lua "gma.echo(1)"').ok


def test_reconnects_after_console_closed_connection():
    with FakeMA2(responses={"List Group": "x\n\r"}) as fake, logged_in(fake) as c:
        c._sock.sendall(b"DROP\r\n")  # make the fake console hang up
        import time

        time.sleep(0.2)
        r = c.send("List Group")
        assert r.ok and c.reconnects == 1 and fake.connections == 2


def test_no_reconnect_when_disabled():
    with FakeMA2() as fake, logged_in(fake, auto_reconnect=False) as c:
        c._sock.sendall(b"DROP\r\n")
        import time

        time.sleep(0.2)
        with pytest.raises(MA2Error):
            c.send("List Group")
