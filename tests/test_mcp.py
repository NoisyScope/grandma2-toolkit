"""MCP server: protocol handshake, tool catalogue, safety refusals and command building (offline)."""
import json
import socket

import pytest
from fake_ma2 import FakeMA2
from ma2kit import mcp_server
from ma2kit.config import Config
from ma2kit.mcp_guide import GUIDE
from ma2kit.mcp_server import Server, ToolError, Tools, cd_commands, help_text, is_read_only, quote

UNIVERSES = (
    "             No.  Name      Granted  Info  \n\r"
    "Universe   1 1    Universe  {g}       \n\r"
)


def _responses(show="demo", modules=0, granted="No", **extra):
    base = {
        "ListVar": f"Global : $SHOWFILE = {show}\n\rGlobal : $USER = toolkit\n\rGlobal : $VERSION = 3.9.61.5\n\r",
        "ListFaderModules": f"Found {modules} internal and 0 external fader modules mask=0\n\r",
        "List DmxUniverse": UNIVERSES.format(g=granted),
    }
    return {**base, **extra}


def _cfg(fake, **kw):
    return Config(host="127.0.0.1", port=fake.port, user="toolkit", password="s3cret", timeout=3, **kw)


def _text(reply):
    return reply["result"]["content"][0]["text"]


def test_handshake_and_catalogue():
    server = Server(Config(port=1))
    init = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}})
    assert init["result"]["protocolVersion"] == "2024-11-05"
    assert init["result"]["capabilities"] == {"tools": {}}
    assert "ma2_status" in init["result"]["instructions"]
    newer = server.handle({"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {"protocolVersion": "2099-01-01"}})
    assert newer["result"]["protocolVersion"] == mcp_server.PROTOCOLS[0]
    assert server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    assert server.handle({"jsonrpc": "2.0", "id": 3, "method": "ping"})["result"] == {}
    assert server.handle({"jsonrpc": "2.0", "id": 4, "method": "resources/list"})["error"]["code"] == -32601
    tools = server.handle({"jsonrpc": "2.0", "id": 5, "method": "tools/list"})["result"]["tools"]
    assert len(tools) == 11
    for tool in tools:
        assert callable(getattr(Tools, tool["name"]))  # every advertised tool is implemented
        assert tool["inputSchema"]["type"] == "object" and tool["description"]
    json.dumps(tools)  # serialisable


def test_guide_and_bad_calls_need_no_console():
    server = Server(Config(port=1))
    topics = json.loads(_text(server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                             "params": {"name": "ma2_guide", "arguments": {}}})))
    assert set(topics["topics"]) == set(GUIDE) and {"patch", "presets", "executors", "timecode"} <= set(GUIDE)
    reply = server.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                           "params": {"name": "ma2_guide", "arguments": {"topic": "nope"}}})
    assert reply["result"]["isError"] and "unknown topic" in _text(reply)
    reply = server.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                           "params": {"name": "ma2_command", "arguments": {"wrong": 1}}})
    assert reply["result"]["isError"] and "bad arguments" in _text(reply)
    reply = server.handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "os_system"}})
    assert reply["result"]["isError"]


def test_helpers():
    assert is_read_only("List Group") and is_read_only('cd "EditSetup"') and is_read_only('Export Group 1 "x"')
    assert not is_read_only("Store Group 5") and not is_read_only("Fixture 1 At 50")
    assert quote(0.5) == "0.5" and quote("ClearAll") == '"ClearAll"' and quote(True) == '"On"'
    with pytest.raises(ToolError):
        quote('a"b')
    assert cd_commands(["EditSetup", "Layers", "4", ".."]) == ["cd /", 'cd "EditSetup"', 'cd "Layers"', "cd 4", "cd .."]
    assert cd_commands(None) == []


def test_help_text(tmp_path):
    page = tmp_path / "key_keyword_x.html"
    page.write_text("<html><head><title>t</title></head><body><h1>X Keyword</h1><p>Use &amp; enjoy</p>"
                    "<table><tr><td>a</td><td>b</td></tr></table></body></html>", encoding="utf-8")
    assert help_text(page) == "X Keyword\nUse & enjoy\na | b |"


def test_command_session_returns_to_root():
    with FakeMA2(responses=_responses(List="row\n\r")) as fake:
        tools = Tools(_cfg(fake))
        out = tools.ma2_command(['cd "EditSetup"', "List"])
        assert out["failed"] == [] and out["results"][1]["output"] == "row"
        assert fake.received[-1] == "cd /"  # the patch lock is always released
        tools.console.drop()


def test_refusals_send_nothing():
    with FakeMA2(responses=_responses()) as fake:
        tools = Tools(_cfg(fake))
        with pytest.raises(ToolError, match="allow_destructive"):
            tools.ma2_command(["Delete Group 5"])
        with pytest.raises(ToolError, match="Login"):
            tools.ma2_command(['Login "a" "b"'])
        with pytest.raises(ToolError, match="allow_destructive"):
            tools.ma2_command(["Store Group 5 /nc"])
        assert fake.received == []


def test_show_guard_blocks_writes_but_not_reads():
    with FakeMA2(responses=_responses(show="real_show", **{"List Group": "x\n\r", "Store Group 5": ""})) as fake:
        tools = Tools(_cfg(fake, allowed_shows=["test_show"]))
        assert tools.ma2_command(["List Group"])["failed"] == []
        with pytest.raises(ToolError, match="allowed_shows"):
            tools.ma2_command(["Store Group 5"])
        assert "Store Group 5" not in fake.received
        tools.console.drop()


def test_live_hardware_needs_confirmation():
    with FakeMA2(responses=_responses(modules=1, **{"Store Group 5": ""})) as fake:
        tools = Tools(_cfg(fake))
        with pytest.raises(ToolError, match="confirm_live"):
            tools.ma2_command(["Store Group 5"])
        assert tools.ma2_command(["Store Group 5"], confirm_live=True)["failed"] == []
        tools.console.drop()
    with FakeMA2(responses=_responses(granted="Yes")) as fake:
        tools = Tools(_cfg(fake))
        assert tools.console.hardware() == {"fader_modules": 0, "granted_universes": [1], "live_output": True}
        tools.console.drop()


def test_set_assigns_inside_the_tree():
    assign = 'Assign 1 /CMD="ClearAll" /Wait=0.5'
    with FakeMA2(responses=_responses(**{assign: "", "List 1": "row\n\r"})) as fake:
        tools = Tools(_cfg(fake))
        out = tools.ma2_set(["Macros", "1", "900"], "1", {"CMD": "ClearAll", "Wait": 0.5})
        assert out["ok"] and out["command"] == assign
        tail = fake.received[-7:]
        assert tail == ["cd /", 'cd "Macros"', "cd 1", "cd 900", assign, "List 1", "cd /"]
        with pytest.raises(ToolError, match="bad property name"):
            tools.ma2_set(["Macros"], "1", {"a b": 1})
        tools.console.drop()


def test_failed_command_stops_the_batch():
    with FakeMA2(responses=_responses(**{"Store Group 5": ""})) as fake:
        tools = Tools(_cfg(fake))
        out = tools.ma2_command(["Nonsense 1", "Store Group 5"])
        assert out["stopped_early"] and out["failed"] == ["Nonsense 1"] and out["sent"] == 1
        assert "OBJECT DOES NOT EXIST" in " ".join(out["results"][0]["errors"])
        out = tools.ma2_command(["Nonsense 1", "Store Group 5"], keep_going=True)
        assert out["sent"] == 2 and out["failed"] == ["Nonsense 1"]
        tools.console.drop()


def test_status_when_console_is_off():
    with socket.socket() as s:  # a port nothing listens on
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    status = Tools(Config(host="127.0.0.1", port=port, password="x")).ma2_status()
    assert status["reachable"] is False and status["connected"] is False
    assert "ma2_command" in status["tools"] and "patch" in status["guide_topics"]


def test_status_reports_show_and_hardware():
    with FakeMA2(responses=_responses(show="demo")) as fake:
        tools = Tools(_cfg(fake, allowed_shows=["demo"]))
        status = tools.ma2_status()
        assert status["connected"] and status["show"] == "demo" and status["show_may_be_changed"]
        assert status["hardware"]["live_output"] is False and status["software_version"] == "3.9.61.5"
        assert "s3cret" not in json.dumps(status)
        tools.console.drop()
