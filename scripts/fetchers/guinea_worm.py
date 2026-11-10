"""Refresh the guinea worm frontier's human case counts from Our World in Data's CSV export.

The World row of OWID's grapher "Reported cases of guinea worm disease" (WHO data, processed by
Our World in Data) gives the reported human cases per year, copied as whole numbers.
"""
from . import common, _owid

FRONTIER = "data/frontiers/health/guinea-worm.yaml"
SPECS = [
    _owid.Spec(series="cases", source="owid-guinea-worm",
               url="https://ourworldindata.org/grapher/number-of-reported-guinea-worm-dracunculiasis-cases.csv?country=OWID_WRL",
               column="Reported cases of guinea worm disease in humans", decimals=0, first_year=1980, min_rows=20),
]


def fetch():
    return _owid.refresh(FRONTIER, SPECS)
