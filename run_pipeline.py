"""Daily run: read new Domestic Relations cases, find homes the spouses own, write the dashboard + GHL CSV."""
from __future__ import annotations

import csv
import datetime as dt
import json
import logging
import sys

import config
import court
import leads as L
from parcels import Gis

log = logging.getLogger("cuyahoga_divorce")
KNOWN_NUMBER = 412000            # DR-26-412000 was filed 10/28/2026 - where the first run starts reading forward


class Reader:
    def __init__(self, cases: dict, today: dt.date):
        self.cases, self.today = cases, today
        self.left = config.MAX_LOOKUPS_PER_RUN
        self.failed = False
        self.docket = court.Docket()

    def years(self):
        y = self.today.year
        return [y, y - 1] if self.today.month == 1 else [y]   # January: new numbers may still be last year's

    def lookup(self, n: int):
        """Return the case for number n (trying this year, and last year in January), or None."""
        for y in self.years():
            cn = court.case_number(y, n)
            if cn in self.cases:
                return self.cases[cn]
            if self.left <= 0 or self.failed:
                return None
            self.left -= 1
            try:
                info = self.docket.fetch(cn)
            except Exception as e:  # noqa: BLE001
                log.warning("%s lookup failed (%s) - stopping lookups for this run", cn, e)
                self.failed = True
                return None
            if info:
                rec = {"found": True, "number": n, "first_seen": self.today.isoformat(), **info}
                if not court.is_kept_type(info.get("case_type", "")):    # store no names for other case types
                    rec = {k: rec[k] for k in ("found", "number", "first_seen", "filed_date", "case_type")}
                self.cases[cn] = rec
                return rec
        return None


def read_cases(state: dict, cases: dict, today: dt.date) -> None:
    r = Reader(cases, today)
    if "high" not in state:
        # Numbers have gaps (hidden/sealed cases), so no guessing: read forward from a known recent case,
        # and back-fill downward from it until cases are older than the back-fill window.
        state.update({"high": KNOWN_NUMBER - 1, "backfill_next": KNOWN_NUMBER - 1,
                      "backfill_until": (today - dt.timedelta(days=config.BACKFILL_DAYS)).isoformat()})

    new, n, misses = 0, state["high"] + 1, 0
    while r.left > 0 and not r.failed and misses < config.MISSES_TO_STOP:
        if r.lookup(n):
            state["high"], misses, new = n, 0, new + 1
        else:
            misses += 1
        n += 1

    back = 0
    while r.left > 0 and not r.failed and state.get("backfill_next", 0) > 0:
        n = state["backfill_next"]
        rec = r.lookup(n)
        back += 1
        state["backfill_next"] = n - 1
        if rec and rec.get("filed_date", "9999") < state["backfill_until"]:
            state["backfill_next"] = 0          # reached cases older than the back-fill window
    log.info("Cases: %d new, %d back-fill numbers checked, %d lookups used, %d page requests, back-fill %s",
             new, back, config.MAX_LOOKUPS_PER_RUN - r.left, r.docket.requests,
             "done" if not state.get("backfill_next") else f"continues at {state['backfill_next']}")


def find_homes(cases: dict, today: dt.date) -> None:
    gis = Gis(config.MAX_GIS_QUERIES_PER_RUN)
    todo = [c for c in cases.values() if c.get("found") and court.is_kept_type(c.get("case_type", ""))
            and c.get("parties") and c.get("match_version") != config.MATCH_VERSION]
    done = 0
    for c in sorted(todo, key=lambda c: c.get("filed_date", ""), reverse=True):
        if gis.left < 6:
            break
        L.lookup_parcels(c, gis)
        c["matched_on"] = today.isoformat()
        c["match_version"] = config.MATCH_VERSION
        done += 1
    log.info("Homes: looked up %d cases (%d still waiting), %d GIS queries used",
             done, len(todo) - done, config.MAX_GIS_QUERIES_PER_RUN - gis.left)


def write_outputs(leads: list[dict], cases: dict) -> None:
    kept = [c for c in cases.values() if c.get("found") and court.is_kept_type(c.get("case_type", ""))]
    meta = {"updated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M"),
            "divorce_cases": len(kept), "homeowner_leads": len(leads),
            "hot": sum(1 for l in leads if l["tier"] == "HOT")}
    config.DOCS_DIR.mkdir(exist_ok=True)
    config.DASHBOARD_JSON.write_text(json.dumps({"meta": meta, "leads": leads}, separators=(",", ":")),
                                     encoding="utf-8")
    for path in (config.GHL_CSV, config.DOCS_CSV):
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh)
            w.writerow(["First Name", "Last Name", "Mailing Address", "City", "State", "Postal Code",
                        "Spouse", "Property Address", "Property City", "Property Zip", "Parcel", "Est. Market Value",
                        "Lead Type", "Case Type", "Case Number", "Filed Date", "Score", "Tier", "Match", "Tags"])
            for l in leads:
                owners = set(l["properties"][0]["owned_by"])
                for s in l["spouses"]:
                    if s["name"] not in owners:
                        continue
                    other = ", ".join(o["name"] for o in l["spouses"] if o["name"] != s["name"])
                    parts = s["name"].split()
                    w.writerow([" ".join(parts[:-1]), parts[-1] if parts else "", s["street"], s["city"], s["state"],
                                s["zip"], other, l["property_address"], l["city"], l["zip"], l["parcel"],
                                round(l["market_value"]), "Divorce", l["case_label"], l["case_number"],
                                l["filed_date"], l["score"], l["tier"], l["match"],
                                f"divorce,cuyahoga,{l['tier'].lower()}"])
    log.info("Leads: %d homeowner leads from %d divorce cases (%d hot)", len(leads), len(kept), meta["hot"])


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    today = dt.date.today()
    config.DATA_DIR.mkdir(exist_ok=True)
    cases = json.loads(config.CASES_JSON.read_text()) if config.CASES_JSON.exists() else {}
    state = json.loads(config.STATE_JSON.read_text()) if config.STATE_JSON.exists() else {}

    read_cases(state, cases, today)
    find_homes(cases, today)
    config.CASES_JSON.write_text(json.dumps(cases, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    config.STATE_JSON.write_text(json.dumps(state, indent=1), encoding="utf-8")
    write_outputs(L.build_leads(cases, today), cases)
    return 0


if __name__ == "__main__":
    sys.exit(main())
