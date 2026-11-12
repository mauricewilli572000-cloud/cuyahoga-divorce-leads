"""Cuyahoga County (Cleveland), OH divorce leads - homeowners going through a divorce or dissolution.

Cases:  Cuyahoga County Clerk of Courts docket (cpdocket.cp.cuyahogacounty.gov), Civil search by case,
        case type DR. Numbers run in order across years (DR-26-410000 was filed 06/16/2026).
        Per case: search page + pick "search by case" + submit (the summary shows the case type),
        then the Parties tab only for divorce / dissolution / legal separation / annulment cases.
Owners: Cuyahoga County GIS Open_Data_Parcels (deeded owner, site and mailing address).

The clerk's site forbids bulk data mining, so this scraper stays small on purpose:
a capped number of case lookups per run, a few seconds apart, new cases first.
"""
from pathlib import Path

MAX_LOOKUPS_PER_RUN = 60    # cases per run (about 3-4 page requests each)
REQUEST_DELAY = 2.5         # seconds between page requests
MISSES_TO_STOP = 15         # missing numbers in a row = reached the newest case (hidden/sealed cases leave gaps of 10+)
BACKFILL_DAYS = 30          # on first run, also read cases filed in the last 30 days (spread over several runs)
KEEP_DAYS = 365             # leads older than this drop off the dashboard

# Countywide Fiscal Officer appraisal parcels (Open_Data_Parcels is Cleveland-only).
# Layer 2 = standard parcels (houses, lots), layer 0 = condos.
PARCELS_BASE = "https://gis.cuyahogacounty.gov/server/rest/services/CCFO/Current_Year_Appraisal_Parcels/MapServer"
PARCEL_LAYERS = [2, 0]
PARCEL_FIELDS = ("PARCELPIN,parcel_owner,second_owner,par_addr_all,parcel_addr,parcel_street,parcel_city,parcel_zip,"
                 "mail_addr_street,mail_city,mail_state,mail_zip,tax_luc_description,tax_market_total,"
                 "total_net_delq_balance,foreclosure_flag,homestead_flag")
MATCH_VERSION = 2           # bump to re-match every stored case against the parcel data
MAX_GIS_QUERIES_PER_RUN = 1200
CASE_URL = "https://cpdocket.cp.cuyahogacounty.gov/Search.aspx"
AUDITOR_URL = "https://myplace.cuyahogacounty.gov/"

KEEP_TYPE_WORDS = ["DIVORCE", "DISSOLUTION", "SEPARATION", "ANNULMENT"]
SKIP_TYPE_WORDS = ["VIOLENCE", "STALKING", "PROTECTION"]

NAME_ONLY_MAX_PARCELS = 3

ENTITY_WORDS = ["LLC", "L L C", "INC", "CORP", "COMPANY", "LTD", "TRUST", "TRUSTEE", "TRS", "PROPERTIES", "HOLDINGS",
                "INVESTMENTS", "BANK", "CHURCH", "ASSOCIATION", "PARTNERS", "LP", "CITY OF", "BOARD OF",
                "ESTATE OF", "HOUSING", "AUTHORITY", "MINISTRIES", "FOUNDATION", "VILLAGE OF", "TOWNSHIP",
                "AGENCY", "DEPARTMENT", "COUNTY", "STATE OF", "ENTERPRISE", "ENTERPRIZE", "GROUP", "REALTY"]
NAME_SUFFIXES = {"JR", "SR", "II", "III", "IV", "V"}

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
CASES_JSON = DATA_DIR / "cases.json"
STATE_JSON = DATA_DIR / "state.json"
DASHBOARD_JSON = DOCS_DIR / "cuyahoga_divorce.json"
GHL_CSV = DATA_DIR / "ghl_cuyahoga_divorce.csv"
DOCS_CSV = DOCS_DIR / "ghl_cuyahoga_divorce.csv"
