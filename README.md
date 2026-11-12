# Cuyahoga County divorce leads

Homeowners in Cuyahoga County (Cleveland), Ohio who just filed for divorce, dissolution or legal separation.

**Dashboard:** https://mauricewilli572000-cloud.github.io/cuyahoga-divorce-leads/

## How it works

1. **Cases**: reads new Domestic Relations cases from the Cuyahoga County Clerk of Courts docket
   (cpdocket.cp.cuyahogacounty.gov). DR case numbers run in order (`DR-26-410000`), so each day it checks
   only the numbers after the last one it saw. The case summary shows the case type; the Parties tab
   (both spouses' names and addresses) is opened only for divorce, dissolution, legal separation and
   annulment. Domestic violence cases are not online and are never read; no names are kept for other case types.
2. **Homes**: looks each spouse up in the county GIS parcel data (by name, and by the address they gave the court):
   - **home at spouse's address**: a spouse owns the parcel at the address they gave the court (strongest)
   - **owned by both spouses**: both are on the deed (including a wife listed under her married name)
   - **name match**: one spouse's name is on a parcel elsewhere, kept only for rare names
   Spouses who rent are dropped.
3. **Score**: 50 base, +20 owns the home they live in, +10 joint owners, +10 already living apart,
   +5 a spouse out of state, +10 filed in the last 30 days. HOT is 85+, WARM is 65+.
   Values are the county's assessed value divided by 0.35 (an estimate of market value).

## Light on the court site

The clerk's site does not allow bulk downloads, so this scraper stays small: at most 60 cases a run
(3-4 page requests each), 2.5 seconds between requests. A one-time back-fill of the last 30 days is spread
over the first couple of weeks of runs; after that it only reads the new cases filed each day.

## Files

- `docs/cuyahoga_divorce.json`: dashboard data (also read by `ohio-lead-stacker`)
- `docs/ghl_cuyahoga_divorce.csv`: GoHighLevel import, one row per spouse on the deed
- `data/cases.json`, `data/state.json`: cases already read and where the scan left off

Runs daily at about 8:29 AM Eastern (GitHub Actions). Run it by hand from the Actions tab: **Run workflow**.
