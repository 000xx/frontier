"""Refresh the safely managed drinking water frontier from Our World in Data's copy of WHO/UNICEF JMP estimates.

The World rows of the OWID grapher CSV give, per year from 2000, the share of the population using safely managed
drinking water services, as a percentage. Values are stored as the source gives them.
"""
from . import _owid

FRONTIER = "data/frontiers/development/safe-water.yaml"
SOURCE_ID = "owid-proportion-using-safely-managed-drinking-water"
URL = "https://ourworldindata.org/grapher/proportion-using-safely-managed-drinking-water.csv?country=OWID_WRL"
COLUMN = "Share of the population using safely managed drinking water"

SPECS = [
    _owid.Spec(series="world", source=SOURCE_ID, url=URL, entity="World", column=COLUMN,
               first_year=2000),
]


def fetch():
    return _owid.refresh(FRONTIER, SPECS)
