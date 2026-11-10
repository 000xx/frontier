"""Refresh the maternal mortality frontier from Our World in Data's CSV export of the UN MMEIG estimates.

The World rows of OWID's grapher "Maternal mortality ratio" give deaths per 100 000 live births
from 2000 on, as published by the UN Maternal Mortality Estimation Inter-Agency Group and processed
by Our World in Data. Values are copied exactly as the source gives them.
"""
from . import common, _owid

FRONTIER = "data/frontiers/development/maternal-mortality.yaml"
SPECS = [
    _owid.Spec(series="world", source="owid-maternal-mortality",
               url="https://ourworldindata.org/grapher/maternal-mortality.csv?country=OWID_WRL",
               column="Maternal mortality ratio", first_year=2000, min_rows=10),
]


def fetch():
    return _owid.refresh(FRONTIER, SPECS)
