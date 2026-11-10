"""Refresh the objects-in-orbit frontier from Our World in Data's copy of the UNOOSA launch index.

The World row of the yearly-number-of-objects-launched-into-outer-space grapher gives the number of objects
launched into space in each year, 1957 onward. Values are whole numbers and are written as they appear.
"""
from . import common, _owid

FRONTIER = "data/frontiers/space/objects-in-orbit.yaml"
SPECS = [
    _owid.Spec(
        series="world",
        source="owid-objects-launched",
        url="https://ourworldindata.org/grapher/yearly-number-of-objects-launched-into-outer-space.csv?country=OWID_WRL",
        column="Annual number of objects launched into outer space",
        entity="World",
        decimals=0,
        first_year=1957,
        min_rows=40,
    ),
]


def fetch():
    return _owid.refresh(FRONTIER, SPECS)
