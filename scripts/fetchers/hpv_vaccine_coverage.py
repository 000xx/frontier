"""Refresh the HPV vaccine coverage frontier from Our World in Data's copy of WHO/UNICEF coverage estimates.

The World rows of the OWID grapher CSV give, per year from 2010, the share of girls vaccinated
against human papillomavirus by age 15, last dose (WUENIC, WHO and UNICEF). Values are stored as the source gives them.
"""
from . import _owid

FRONTIER = "data/frontiers/health/hpv-vaccine-coverage.yaml"
SOURCE_ID = "owid-coverage-of-the-human-papillomavirus-vaccine"
URL = "https://ourworldindata.org/grapher/coverage-of-the-human-papillomavirus-vaccine.csv?country=OWID_WRL"
COLUMN = "HPV Vaccination coverage by age 15, last dose, females"

SPECS = [
    _owid.Spec(series="world", source=SOURCE_ID, url=URL, entity="World", column=COLUMN,
               decimals=2, first_year=2010),
]


def fetch():
    return _owid.refresh(FRONTIER, SPECS)
