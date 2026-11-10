"""Refresh the DTP3 vaccination frontier from Our World in Data's copy of WHO and UNICEF coverage estimates.

The World rows of the OWID grapher CSV give, per year from 1980, the share of one-year-olds who received three
doses of the diphtheria, tetanus and pertussis vaccine. Values are whole percentages, stored as the source gives them.
"""
from . import _owid

FRONTIER = "data/frontiers/health/dtp3-vaccination.yaml"
SOURCE_ID = "owid-share-of-children-immunized-dtp3"
URL = "https://ourworldindata.org/grapher/share-of-children-immunized-dtp3.csv?country=OWID_WRL"
COLUMN = "Diphtheria/tetanus/pertussis (DTP3)"

SPECS = [
    _owid.Spec(series="world", source=SOURCE_ID, url=URL, entity="World", column=COLUMN,
               decimals=0, first_year=1980),
]


def fetch():
    return _owid.refresh(FRONTIER, SPECS)
