"""Replies captured from onPC 3.9.61 (trimmed). Column alignment is exactly as the console sent it."""

LIST_FIXTURETYPE = (
    "              No.  LongName              ShortName             Manufacturer  ShortManu  DMXFootprint  Instances  Mode  Used  XYZ  Model        RDMFixtureType  \n"
    "FixtureType 1 1    Universal Attributes  Universal Attributes  AutoMA        AutoMA     0             1                0          [automatic]                   (7)\n"
    "FixtureType 2 2    Dimmer                Dim                   Generic       Generic    1             1          00    0          [automatic]                   (7)\n"
    "FixtureType 3 3    PAR280 SLIM           PAR280SL              SUPER BRIGHT  SUPERBRI   9             1          9CH   20         [automatic]                   (7)\n"
    "FixtureType 4 4    BEAM 8R + RING        BEAM8R_RING           SUPER BRIGHT             24            1          24CH  12         [automatic]                   (7)\n"
)

LIST_FIXTURE = (
    "            Name           FixId  ChaId  FixtureType            Patch   NoParameters  PosX  PosY  PosZ  RotX  RotY  RotZ  Info  RDMID  \n"
    "Fixture 100 BEAM8R_RING 1  100    100    4 BEAM 8R + RING 24CH   1.001  No            0.00  0.00  0.00  0.00  0.00  0.00                (1)\n"
    "Fixture 101 BEAM8R_RING 2  101    101    4 BEAM 8R + RING 24CH   1.025  No            0.00  0.00  0.00  0.00  0.00  0.00                (1)\n"
    "Fixture 102 BEAM8R_RING 3  102    102    4 BEAM 8R + RING 24CH   1.049  No            0.00  0.00  0.00  0.00  0.00  0.00                (1)\n"
    "Fixture 103 BEAM8R_RING 4  103    103    4 BEAM 8R + RING 24CH   1.073  No            0.00  0.00  0.00  0.00  0.00  0.00                (1)\n"
    "Fixture 200 PAR280SL 1     200    200    3 PAR280 SLIM 9CH       2.001  No            0.00  0.00  0.00  0.00  0.00  0.00                (1)\n"
    "Fixture 201 PAR280SL 2     201    201    3 PAR280 SLIM 9CH       2.010  No            0.00  0.00  0.00  0.00  0.00  0.00                (1)\n"
    "Fixture 202 PAR280SL 3     202    202    3 PAR280 SLIM 9CH       2.019  No            0.00  0.00  0.00  0.00  0.00  0.00                (1)\n"
)

LIST_GROUP = (
    "        No.  Name         Info  \n"
    "Group 1 1    ALL\n"
    "Group 5 5    PAR_ALL\n"
)

LIST_EFFECT = (
    "          No.  Name        Info  \n"
    "Effect  1 1    PAR_E1             (1)\n"
    "Effect 17 17   SYM_PAR_E1         (1)\n"
)

LIST_PRESET = (
    "          No.  Name  Special  Info  \n"
    "Focus 6.1 6.1  100   Normal\n"
)

EMPTY = "WARNING, NO OBJECTS FOUND FOR LIST"

NS = 'xmlns="http://schemas.malighting.de/grandma2/xml/MA"'

GROUP_XML = f"""<?xml version="1.0" encoding="utf-8"?>
<MA {NS} major_vers="3" minor_vers="9" stream_vers="61">
  <Info datetime="2026-11-11T21:35:38" showfile="test" />
  <Group index="899" name="probe">
    <Subfixtures>
      <Subfixture fix_id="103" />
      <Subfixture fix_id="100" />
      <Subfixture fix_id="102" />
    </Subfixtures>
  </Group>
</MA>"""

FIXTURES_XML = f"""<?xml version="1.0" encoding="utf-8"?>
<MA {NS} major_vers="3" minor_vers="9" stream_vers="61">
  <Info datetime="2026-11-11T21:35:39" showfile="test" />
  <Fixture index="0" name="BEAM8R_RING 1" fixture_id="100" channel_id="100">
    <FixtureType name="4 BEAM 8R + RING 24CH"><No>4</No></FixtureType>
    <SubFixture index="0" react_to_grandmaster="true" color="ffffff">
      <Patch><Address>1</Address></Patch>
      <AbsolutePosition>
        <Location x="-4.5" y="-4" z="4" />
        <Rotation x="-0" y="0" z="-90" />
      </AbsolutePosition>
    </SubFixture>
  </Fixture>
  <Fixture index="1" name="BEAM8R_RING 2" fixture_id="101" channel_id="101">
    <FixtureType name="4 BEAM 8R + RING 24CH"><No>4</No></FixtureType>
    <SubFixture index="0">
      <Patch><Address>25</Address></Patch>
      <AbsolutePosition><Location x="-4.5" y="-2.4" z="4" /></AbsolutePosition>
    </SubFixture>
  </Fixture>
</MA>"""
