"""Refresh the adult literacy frontier from Our World in Data's copy of UNESCO Institute for Statistics data.

The World rows of the OWID grapher CSV give, per year from 1975, the adult literacy rate (aged 15 and over),
as a percentage. Values are stored as the source gives them.
"""
from . import _owid

FRONTIER = "data/frontiers/development/literacy.yaml"
SOURCE_ID = "owid-literacy-rate-adults"
URL = "https://ourworldindata.org/grapher/literacy-rate-adults.csv?country=OWID_WRL"
COLUMN = "Literacy rate among adults"

SPECS = [
    _owid.Spec(series="world", source=SOURCE_ID, url=URL, entity="World", column=COLUMN,
               first_year=1975),
]


def fetch():
    return _owid.refresh(FRONTIER, SPECS)
