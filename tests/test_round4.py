"""Tree-path prompts after `cd`, late feedback in batches, and the reference-doc plugins."""
from fake_ma2 import FakeMA2
from ma2kit import batch
from ma2kit.client import MA2Client, split_prompt, split_reply
from ma2kit.plugins import source_plugins


def _client(fake):
    c = MA2Client("127.0.0.1", fake.port, timeout=3, idle=0.1)
    c.connect()
    c.login("toolkit", "s3cret")
    return c


def test_path_prompt_parsing():
    # Captured on 3.9.61 after `cd "EditSetup"; cd "Layers"; cd 3`.
    text = 'Executing : ChangeDest 3\n\nEditSetup/Layers 4/PAR_LED 3 >'
    assert split_reply(text, "cd 3")[2] == "EditSetup/Layers 4/PAR_LED 3"
    assert split_prompt("Executing : List\nrow\nSettings 3 >") == ("Executing : List\nrow", "Settings 3")
    assert split_prompt("x\n [Group]>")[1] == "Group"
    # Table cells such as "Dir = >" are not prompts.
    assert split_prompt("Dir = >")[1] is None


def test_cd_session_keeps_working():
    responses = {"List": "row\n\r"}
    with FakeMA2(responses=responses) as fake, _client(fake) as c:
        r = c.send('cd "EditSetup"')
        assert r.prompt == "EditSetup" and r.ok
        r = c.send("List")
        assert r.prompt == "EditSetup" and r.text == "row"
        assert c.send("cd /").prompt == "Channel"


def test_poll_returns_late_feedback():
    with FakeMA2(late={"Plugin 5": "PLUGIN SAYS hi\n\r [Channel]>"}) as fake, _client(fake) as c:
        r = c.send("Plugin 5")
        import time

        time.sleep(0.2)
        # Depending on timing the feedback is in the reply's `late` or comes from poll(); never both.
        seen = (r.late + "\n" + c.poll()).count("PLUGIN SAYS hi")
        assert seen == 1
        assert c.poll() == ""


def test_poll_does_not_repeat_late_text():
    with FakeMA2(late={"Plugin 5": "PLUGIN SAYS hi\n\r [Channel]>"}) as fake:
        c = MA2Client("127.0.0.1", fake.port, timeout=3, idle=0.3)  # long enough to catch the feedback
        c.connect()
        c.login("toolkit", "s3cret")
        r = c.send("Plugin 5")
        assert "PLUGIN SAYS hi" in r.late
        assert c.poll() == ""
        c.close()


def test_batch_shows_late_feedback():
    lines: list[str] = []
    with FakeMA2(late={"Plugin 5": "PLUGIN SAYS hi\n\r [Channel]>"}, responses={"List": ""}) as fake, _client(fake) as c:
        results = batch.run(c, batch.parse("Plugin 5\nwait 0.2\nList\n"), echo=lines.append)
    assert any("PLUGIN SAYS hi" in l for l in lines)
    assert "PLUGIN SAYS hi" in results[0].output


def test_reference_plugins_are_read_only_sources():
    plugins = {p.name: p for p in source_plugins()}
    for name in ("ma2kit_api_dump", "ma2kit_inspect"):
        assert name in plugins and "Read-only" in plugins[name].description
        body = plugins[name].path.read_text(encoding="utf-8")
        assert "gma.cmd" not in body  # they only read
