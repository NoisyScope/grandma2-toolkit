"""Plugin bundling, backups, monitor parsing, config and the show guard."""
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from ma2kit import backup, cli, monitor
from ma2kit.client import MA2Error
from ma2kit.config import load_config
from ma2kit.plugins import LIB_FILE, SourcePlugin, bundle, plugin_xml, source_plugins


def test_repo_plugins_have_descriptions():
    plugins = {p.name: p for p in source_plugins()}
    assert "ma2kit_info" in plugins
    assert plugins["ma2kit_info"].description


def test_bundle_wraps_plugin_and_reports_line_offset(tmp_path):
    src = tmp_path / "demo.lua"
    src.write_text("local function Start()\n    error('boom')\nend\nreturn Start\n", encoding="utf-8")
    lib = LIB_FILE.read_text(encoding="utf-8")
    text = bundle(SourcePlugin("demo", src, ""), lib)
    lines = text.splitlines()
    offset = int(lines[1].split("subtract ")[1].split(" ")[0])
    assert lines[offset] == "local function Start()"  # line 1 of the source
    assert 'ma2kit._run("demo", __ma2kit_start, ...)' in text
    assert "local ma2kit = " in text


def test_error_lines_map_to_source(tmp_path):
    from ma2kit.plugins import body_offset, map_error_lines

    lib = LIB_FILE.read_text(encoding="utf-8")
    installed_line = body_offset(lib) + 4
    err = f'error: [string "plugin_101_demo_plugin"]:{installed_line}: boom'
    assert map_error_lines(err, lib) == "error: lua/plugins/demo_plugin.lua:4: boom"


def test_plugin_xml_points_to_lua_file():
    xml = plugin_xml("demo")
    assert 'name="demo" luafile="demo.lua"' in xml


def test_backup_rotation(tmp_path):
    source = tmp_path / "show.show.gz"
    source.write_bytes(b"x")
    dest = tmp_path / "backups"
    start = datetime(2026, 1, 1, 12, 0, 0)
    for i in range(5):
        backup.copy_with_rotation(source, dest, "my show", keep=3, now=start + timedelta(minutes=i))
    names = sorted(p.name for p in dest.iterdir())
    assert names == [
        "my show_20260101-120200.show.gz",
        "my show_20260101-120300.show.gz",
        "my show_20260101-120400.show.gz",
    ]


def test_saved_regex():
    assert backup.SAVED_RE.search('Show successfully saved as "demo".').group(1) == "demo"


def test_monitor_parse_line():
    assert monitor.parse_line("22h12m16.121s : [ma2kit] hello") == ("22h12m16.121s", "[ma2kit] hello")
    assert monitor.parse_line("no time") == (None, "no time")


def test_config_sections(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(
        '[console]\npassword = "pw"\n[safety]\nallowed_shows = ["test show"]\n'
        '[pools]\ngroup_start = 700\nplugin_start = 50\n[backup]\ndir = "bk"\nkeep = 3\n',
        encoding="utf-8",
    )
    cfg = load_config(cfg_file)
    assert cfg.allowed_shows == ["test show"]
    assert (cfg.group_start, cfg.plugin_start, cfg.backup_keep) == (700, 50, 3)
    assert cfg.backup_dir == (tmp_path / "bk").resolve()
    assert "pw" not in repr(cfg)


class _FakeModel:
    def __init__(self, show):
        self.show = show

    def var(self, name):
        return self.show if name == "SHOWFILE" else None


def test_show_guard(tmp_path):
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text('[safety]\nallowed_shows = ["test"]\n', encoding="utf-8")
    cfg = load_config(cfg_file)
    assert cli._guard_write(cfg, _FakeModel("test")) == "test"
    with pytest.raises(MA2Error, match="allowed_shows"):
        cli._guard_write(cfg, _FakeModel("real show"))
    cfg.allowed_shows = []
    assert cli._guard_write(cfg, _FakeModel("anything")) == "anything"


def test_menu_quits(monkeypatch, capsys):
    from ma2kit.menu import run_menu

    answers = iter(["99", "0"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    calls = []
    assert run_menu(lambda argv: calls.append(argv) or 0) == 0
    assert calls == []
    assert "Unknown choice" in capsys.readouterr().out


def test_menu_runs_status(monkeypatch):
    from ma2kit.menu import run_menu

    answers = iter(["1", "", "0"])  # status, press Enter, quit
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    calls = []
    run_menu(lambda argv: calls.append(argv) or 0)
    assert calls == [["doctor"]]
