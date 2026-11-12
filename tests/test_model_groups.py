import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

import samples
from fake_ma2 import FakeMA2
from ma2kit import cli, groups
from ma2kit.client import MA2Client
from ma2kit.model import (
    ShowModel,
    compress_ids,
    parse_fixtures_xml,
    parse_group_xml,
    parse_list,
    parse_patch,
)

RESPONSES = {
    "List Fixture": samples.LIST_FIXTURE,
    "List FixtureType": samples.LIST_FIXTURETYPE,
    "List Group": samples.LIST_GROUP,
}


def test_parse_list_fixture_columns():
    rows = parse_list(samples.LIST_FIXTURE)
    assert len(rows) == 7
    first = rows[0]
    assert (first.cls, first.no) == ("Fixture", "100")
    assert first["Name"] == "BEAM8R_RING 1"
    assert first["FixtureType"] == "4 BEAM 8R + RING 24CH"
    assert first["Patch"] == "1.001"


def test_parse_list_fixturetype_and_pools():
    types = parse_list(samples.LIST_FIXTURETYPE)
    beam = types[3]
    assert beam["ShortName"] == "BEAM8R_RING"
    assert beam["DMXFootprint"] == "24"
    assert beam["Mode"] == "24CH"
    effects = parse_list(samples.LIST_EFFECT)
    assert [(r.no, r["Name"]) for r in effects] == [("1", "PAR_E1"), ("17", "SYM_PAR_E1")]
    presets = parse_list(samples.LIST_PRESET)
    assert (presets[0].cls, presets[0].no) == ("Focus", "6.1")
    assert parse_list(samples.EMPTY) == []


def test_patch_and_compress():
    assert parse_patch("2.019") == (2, 19)
    assert parse_patch("-") is None
    assert compress_ids([5, 1, 2, 3, 9]) == "1-3, 5, 9"


def test_xml_parsers():
    assert parse_group_xml(ET.fromstring(samples.GROUP_XML)) == [103, 100, 102]
    data = parse_fixtures_xml(ET.fromstring(samples.FIXTURES_XML))
    assert data[100] == {"address": 1, "position": (-4.5, -4.0, 4.0)}
    assert data[101]["address"] == 25


def test_model_against_fake_console():
    with FakeMA2(responses=RESPONSES) as fake:
        with MA2Client("127.0.0.1", fake.port, timeout=3, idle=0.1) as c:
            c.connect()
            c.login("toolkit", "s3cret")
            model = ShowModel(c)
            fixtures = model.fixtures()
            types = model.fixture_types()
            assert model.used_numbers("Group") == {1, 5}
    assert [f.fid for f in fixtures] == [100, 101, 102, 103, 200, 201, 202]
    assert fixtures[4].patch == "2.001" and fixtures[4].type_no == 3
    assert {t.no: t.short_name for t in types}[4] == "BEAM8R_RING"


@pytest.fixture
def rig():
    with FakeMA2(responses=RESPONSES) as fake:
        with MA2Client("127.0.0.1", fake.port, timeout=3, idle=0.1) as c:
            c.connect()
            c.login("toolkit", "s3cret")
            model = ShowModel(c)
            yield model.fixtures(), model.fixture_types()


def test_plan_auto_groups(rig):
    fixtures, types = rig
    plans = groups.plan_auto_groups(fixtures, types, start=500)
    names = {p.name: p for p in plans}
    assert plans[0].no == 500 and plans[0].name == "ALL FIXTURES"
    assert [p.no for p in plans] == list(range(500, 500 + len(plans)))
    assert names["BEAM8R_RING ALL"].fixtures == [100, 101, 102, 103]
    assert names["BEAM8R_RING ODD"].fixtures == [100, 102]
    assert names["BEAM8R_RING EVEN"].fixtures == [101, 103]
    assert names["BEAM8R_RING 1ST HALF"].fixtures == [100, 101]
    assert names["BEAM8R_RING OUT>IN"].fixtures == [100, 103, 101, 102]
    assert names["BEAM8R_RING IN>OUT"].fixtures == [102, 101, 103, 100]
    assert names["PAR280SL OUT>IN"].fixtures == [200, 202, 201]
    assert "PAR280SL 1ST HALF" not in names  # only 3 PARs in the sample


def test_plan_filters(rig):
    fixtures, types = rig
    plans = groups.plan_auto_groups(fixtures, types, 10, variants=("all", "odd"), only_types={"PAR280SL"})
    assert [p.name for p in plans] == ["PAR280SL ALL", "PAR280SL ODD"]
    with pytest.raises(ValueError):
        groups.plan_auto_groups(fixtures, types, 10, variants=("bogus",))


def test_selection_command_keeps_order():
    assert groups.selection_command([100, 101, 102, 103]) == "Fixture 100 Thru 103"
    assert groups.selection_command([100, 103, 101, 102]) == "Fixture 100 + 103 + 101 + 102"
    assert groups.selection_command([1, 2, 5, 6, 7]) == "Fixture 1 + 2 + 5 Thru 7"


def test_commands_and_free_check():
    plans = [groups.GroupPlan(500, "A ALL", [1, 2, 3]), groups.GroupPlan(501, "A ODD", [1, 3])]
    assert groups.commands_for(plans) == [
        "ClearSelection", "Fixture 1 Thru 3", "Store Group 500", 'Label Group 500 "A ALL"',
        "ClearSelection", "Fixture 1 + 3", "Store Group 501", 'Label Group 501 "A ODD"',
        "ClearSelection",
    ]
    assert groups.check_free(plans, {1, 501}) == [501]


def test_apply_in_dry_run_sends_nothing():
    c = MA2Client(dry_run=True)
    groups.apply(c, [groups.GroupPlan(500, "A ALL", [1, 2])])
    assert c.sent_log[2] == "Store Group 500"


def _config(tmp_path: Path, port: int) -> Path:
    cfg = tmp_path / "config.toml"
    cfg.write_text(f'[console]\nport = {port}\npassword = "s3cret"\ntimeout = 3\n', encoding="utf-8")
    return cfg


def test_cli_groups_auto_preview_changes_nothing(tmp_path, capsys):
    with FakeMA2(responses=RESPONSES) as fake:
        assert cli.main(["--config", str(_config(tmp_path, fake.port)), "groups", "auto"]) == 0
        assert not any(cmd.startswith("Store") for cmd in fake.received)
    out = capsys.readouterr().out
    assert "BEAM8R_RING OUT>IN" in out and "Nothing was changed" in out


def test_cli_groups_auto_refuses_occupied_slots(tmp_path, capsys):
    with FakeMA2(responses=RESPONSES) as fake:
        assert cli.main(["--config", str(_config(tmp_path, fake.port)), "groups", "auto", "--start", "1", "--apply"]) == 1
        assert not any(cmd.startswith("Store") for cmd in fake.received)
    assert "already used" in capsys.readouterr().err
