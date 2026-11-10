"""Refresh the tuberculosis frontier from Our World in Data's CSV exports of WHO estimates.

The World rows of two grapher exports are read: deaths ("Tuberculosis deaths") and cases
("Tuberculosis cases"), both WHO data processed by Our World in Data. Each year is copied as a
whole number.
"""
from . import common, _owid

FRONTIER = "data/frontiers/health/tuberculosis.yaml"
SPECS = [
    _owid.Spec(series="deaths", source="owid-tb-deaths",
               url="https://ourworldindata.org/grapher/tuberculosis-deaths-who.csv?country=OWID_WRL",
               column="Estimated number of deaths from all forms of tuberculosis", decimals=0, first_year=2000, min_rows=10),
    _owid.Spec(series="cases", source="owid-tb-cases",
               url="https://ourworldindata.org/grapher/number-of-tuberculosis-cases.csv?country=OWID_WRL",
               column="Tuberculosis cases", decimals=0, first_year=2000, min_rows=10),
]


def fetch():
    return _owid.refresh(FRONTIER, SPECS)
