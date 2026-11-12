"""Batch files, macros, show checks, free slots and the shared menu session."""
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from fake_ma2 import FakeMA2
from ma2kit import batch, checks, cli
from ma2kit.client import MA2Client, MA2Error
from ma2kit.macros import macro_xml, parse_source, source_macros
from ma2kit.model import Fixture, FixtureType

NS = "{http://schemas.malighting.de/grandma2/xml/MA}"


# -- batch -------------------------------------------------------------------
def test_batch_parse():
    steps = batch.parse("# comment\n\nList Group\nwait 1.5\nDelete Group 9\n")
    assert [(s.line_no, s.command, s.wait) for s in steps] == [(3, "List Group", 0), (4, None, 1.5), (5, "Delete Group 9", 0)]
    assert steps[2].risky and not steps[0].risky


def _client(fake):
    c = MA2Client("127.0.0.1", fake.port, timeout=3, idle=0.1)
    c.connect()
    c.login("toolkit", "s3cret")
    return c


def test_batch_stops_at_first_error():
    with FakeMA2(responses={"List Group": "ok\n\r"}) as fake, _client(fake) as c:
        results = batch.run(c, batch.parse("List Group\nList Nonsense\nList Group\n"), echo=lambda *_: None)
        assert [r.ok for r in results] == [True, False]
        assert fake.received[-1] == "List Nonsense"


def test_batch_keep_going_and_strict_warnings():
    responses = {"Label Group 999 \"x\"": "WARNING, NO OBJECTS FOUND FOR LABEL\n\r", "List Group": "ok\n\r"}
    text = 'Label Group 999 "x"\nList Group\n'
    with FakeMA2(responses=responses) as fake, _client(fake) as c:
        lenient = batch.run(c, batch.parse(text), echo=lambda *_: None)
        assert [(r.ok, r.warned) for r in lenient] == [(True, True), (True, False)]
        strict = batch.run(c, batch.parse(text), strict=True, echo=lambda *_: None)
        assert [r.ok for r in strict] == [False]


def test_cli_batch_preview_sends_nothing(tmp_path, capsys):
    f = tmp_path / "cmds.txt"
    f.write_text("Store Group 600\n", encoding="utf-8")
    assert cli.main(["batch", str(f)]) == 0
    assert "Nothing was sent" in capsys.readouterr().out


# -- macros ------------------------------------------------------------------
def test_macro_source_and_xml():
    m = parse_source("demo", '# description: Demo\nClearAll\nwait 0.5\nLabel Group 1 "A&B"\n')
    assert m.description == "Demo"
    assert [(l.text, l.delay) for l in m.lines] == [("ClearAll", 0.5), ('Label Group 1 "A&B"', 0.0)]
    root = ET.fromstring(macro_xml(m))
    macro = root.find(f"{NS}Macro")
    assert macro.get("name") == "demo"
    lines = macro.findall(f"{NS}Macroline")
    assert lines[0].get("delay") == "0.5" and lines[1].get("delay") is None
    assert lines[1].find(f"{NS}text").text == 'Label Group 1 "A&B"'


def test_macro_source_errors():
    with pytest.raises(MA2Error):
        parse_source("x", "# only comments\n")
    with pytest.raises(MA2Error):
        parse_source("x", "wait 1\nClearAll\n")


def test_repo_macros_parse():
    names = {m.name for m in source_macros()}
    assert {"ma2kit_clear_all", "ma2kit_save_show"} <= names


# -- checks ------------------------------------------------------------------
def _fx(fid, name, type_no, universe, address):
    return Fixture(fid, name, type_no, "", universe, address)


def test_patch_checks():
    types = [FixtureType(1, "Wash", "W", "", 16, "16CH", 0), FixtureType(2, "Dim", "D", "", 1, "", 0)]
    fixtures = [
        _fx(1, "A", 1, 1, 1),  # 1-16
        _fx(2, "B", 1, 1, 10),  # 10-25 overlaps 1
        _fx(3, "C", 1, 1, 500),  # 500-515 overflows
        _fx(4, "A", 2, 2, 1),  # duplicate name
        _fx(5, "E", 2, None, None),  # unpatched
    ]
    issues = checks.run_all(fixtures, types)
    kinds = sorted(i.check for i in issues)
    assert kinds == ["duplicate-name", "overflow", "overlap", "unpatched"]
    assert "fixture 1 (1-16) overlaps fixture 2 (10-25)" in next(i.message for i in issues if i.check == "overlap")


def test_no_issues_for_clean_patch():
    types = [FixtureType(1, "Wash", "W", "", 16, "16CH", 0)]
    assert checks.run_all([_fx(1, "A", 1, 1, 1), _fx(2, "B", 1, 1, 17)], types) == []


def test_show_free_rejects_zero_count(capsys):
    with pytest.raises(SystemExit):
        cli.main(["show", "free", "Group", "--count", "0"])
    assert "must be 1 or more" in capsys.readouterr().err


def test_free_numbers():
    assert checks.free_numbers({1, 2, 3, 5}, 1, 1) == 4
    assert checks.free_numbers({1, 2, 3, 5}, 1, 2) == 6
    assert checks.free_numbers({500, 501}, 500, 3) == 502
    assert checks.free_numbers({1}, 1, 1, limit=1) is None


# -- menu session --------------------------------------------------------------
def test_menu_session_reuses_one_connection(tmp_path, monkeypatch):
    with FakeMA2(responses={"List Group": "x\n\r"}) as fake:
        cfg_file = tmp_path / "config.toml"
        cfg_file.write_text(f'[console]\nport = {fake.port}\npassword = "s3cret"\ntimeout = 3\n', encoding="utf-8")
        answers = iter(["4", "Group", "", "4", "Group", "", "0"])  # browse pool twice, then quit
        monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
        monkeypatch.setattr("sys.stdin.isatty", lambda: True, raising=False)
        assert cli.main(["--config", str(cfg_file), "menu"]) == 0
        assert fake.connections == 1
        assert sum(1 for c in fake.received if c.startswith("Login")) == 1
    assert cli._Session.client is None and not cli._Session.active
