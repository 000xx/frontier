"""Refresh the measles frontier from Our World in Data's CSV exports of WHO data.

Two World series are read: reported measles cases (WHO Global Health Observatory) and the
share of children vaccinated with the first dose (WHO and UNICEF estimates). Cases are whole
numbers; coverage is kept to one decimal place, as the source gives it.
"""
from . import common, _owid

FRONTIER = "data/frontiers/health/measles.yaml"
SPECS = [
    _owid.Spec(series="cases", source="owid-measles-cases",
               url="https://ourworldindata.org/grapher/reported-cases-of-measles.csv?country=OWID_WRL",
               column="Measles - number of reported cases", decimals=0, first_year=2000, min_rows=10),
    _owid.Spec(series="coverage", source="owid-measles-coverage",
               url="https://ourworldindata.org/grapher/share-of-children-vaccinated-against-measles.csv?country=OWID_WRL",
               column="Share of children vaccinated against measles", decimals=1, first_year=2000, min_rows=10),
]


def fetch():
    return _owid.refresh(FRONTIER, SPECS)
