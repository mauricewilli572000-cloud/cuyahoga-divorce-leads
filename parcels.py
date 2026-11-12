"""Find Cuyahoga County parcels a divorcing spouse owns (county GIS Open_Data_Parcels)."""
from __future__ import annotations

import logging
import re
import time

import requests

import config
from addr import normalize_address

log = logging.getLogger(__name__)
S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0 (cuyahoga-divorce-leads)"


# ----------------------------------------------------------------- names
def is_entity(name: str) -> bool:
    n = f" {re.sub(r'[^A-Z0-9 ]', ' ', (name or '').upper())} "
    return bool(re.search(r"\d", n)) or any(f" {w} " in n for w in config.ENTITY_WORDS)


def _tokens(s: str) -> list[str]:
    return [t for t in re.sub(r"[^A-Z ]", " ", (s or "").upper()).split() if t not in config.NAME_SUFFIXES]


def party_person(name: str) -> dict | None:
    """Court party 'IMAN  MOUSTAFA' / 'KENNETH CHASE EASTERLING' -> first, middle initial, last."""
    if is_entity(name):
        return None
    t = _tokens(name)
    if len(t) < 2:
        return None
    return {"first": t[0], "middle": t[1][0] if len(t) > 2 else "", "last": t[-1]}


def owner_people(owner: str) -> list[dict]:
    """Deeded owner -> people.  'MORRIS, KATHERINE A & JURINA, DONOVAN', 'SMIALEK, MARIA R & CHARLES A',
    'HUGHES HART W & ALMA' (older records, no comma: LAST FIRST M)."""
    if not owner:
        return []
    owner = re.sub(r"\s*-\s*(TRS?|TRUSTEES?|ET AL|ETAL)\b.*$", "", owner.upper())
    people, last = [], ""
    for i, seg in enumerate(s for s in re.split(r"\s*&\s*|\s+AND\s+", owner) if s.strip()):
        if is_entity(seg):
            continue
        if "," in seg:
            l, _, rest = seg.partition(",")
            lt, rt = _tokens(l), _tokens(rest)
            if not lt or not rt:
                continue
            last = lt[-1]
            people.append({"last": last, "first": rt[0], "middle": rt[1][0] if len(rt) > 1 else ""})
        else:
            t = _tokens(seg)
            if not t:
                continue
            if i == 0:          # LAST FIRST [M]
                if len(t) < 2:
                    continue
                last = t[0]
                people.append({"last": t[0], "first": t[1], "middle": t[2][0] if len(t) > 2 else ""})
            elif last:          # '& CHARLES A' shares the previous last name
                people.append({"last": last, "first": t[0], "middle": t[1][0] if len(t) > 1 and len(t[1]) == 1 else ""})
    return people


def same_person(party: dict, owner: dict) -> bool:
    if party["last"] != owner["last"] or party["first"] != owner["first"]:
        return False
    return not (party["middle"] and owner["middle"] and party["middle"] != owner["middle"])


def name_key(p: dict) -> tuple[str, str]:
    return (p["last"], p["first"])


# ----------------------------------------------------------------- GIS
class Gis:
    def __init__(self, budget: int):
        self.left = budget

    def query(self, where: str) -> list[dict]:
        if self.left <= 0:
            raise RuntimeError("GIS query budget used up")
        self.left -= 1
        params = {"where": where, "outFields": config.PARCEL_FIELDS, "returnGeometry": "false", "f": "json",
                  "resultRecordCount": 200}
        last = None
        for attempt in range(3):
            try:
                r = S.get(config.PARCELS_QUERY, params=params, timeout=90)
                d = r.json()
                if "error" in d:
                    raise RuntimeError(str(d["error"])[:200])
                return [f.get("attributes") or {} for f in d.get("features") or []]
            except Exception as e:  # noqa: BLE001
                last = e
                time.sleep(3 * (attempt + 1))
        log.warning("GIS query failed (%s): %s", last, where[:120])
        return []


def _q(s: str) -> str:
    return s.replace("'", "''")


def _num(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def parcel_info(a: dict) -> dict:
    addr = re.sub(r"\s+", " ", str(a.get("par_addr_all") or "")).strip()
    street = re.sub(r"\s+", " ", re.split(r",", addr)[0]).strip()
    mail = ", ".join(p for p in (re.sub(r"\s+", " ", str(a.get("mail_addr_street") or "")).strip(),
                                 " ".join(str(a.get(k) or "").strip() for k in ("mail_city", "mail_state", "mail_zip")).strip())
                     if p)
    return {
        "parcel": re.sub(r"\D", "", str(a.get("parcelpin") or "")),
        "address": street,
        "keys": [k for k in {normalize_address(street)} if k],
        "city": str(a.get("par_city") or "").title(),
        "zip": str(a.get("par_zip") or "").split(".")[0][:5],
        "owner_name": re.sub(r"\s+", " ", str(a.get("deeded_owner") or "")).strip(),
        "owners": owner_people(str(a.get("deeded_owner") or "")),
        "mailing_address": mail,
        # county values are assessed (35% of market); convert to an estimated market value
        "market_value": round(_num(a.get("gross_certified_total") or a.get("certified_tax_total")) / 0.35),
        "land_use": str(a.get("tax_luc_description") or ""),
        "in_foreclosure": False,
        "delinquent_taxes": 0.0,
    }


def by_name(gis: Gis, person: dict) -> list[dict]:
    """Parcels whose deeded owner names this person (any owner format)."""
    rows = gis.query(f"UPPER(deeded_owner) LIKE '%{_q(person['last'])}%{_q(person['first'])}%'")
    out = []
    for a in rows:
        info = parcel_info(a)
        if any(same_person(person, o) for o in info["owners"]):
            out.append(info)
    return out


def by_address(gis: Gis, street: str, zipc: str) -> list[dict]:
    m = re.match(r"^(\d+)[A-Z]?\s+(.+)$", (street or "").upper())
    if not m:
        return []
    key = normalize_address(street)
    words = [w for w in re.sub(r"[^A-Z0-9 ]", " ", m.group(2)).split()
             if w not in {"N", "S", "E", "W", "NORTH", "SOUTH", "EAST", "WEST", "APT", "UNIT", "STE"}]
    if not words:
        return []
    core = max(words, key=len)
    where = f"par_addr = '{_q(m.group(1))}' AND UPPER(par_street) LIKE '%{_q(core)}%'"
    hits = [i for i in (parcel_info(a) for a in gis.query(where)) if key and key in i["keys"]]
    if zipc and len(hits) > 1:      # same street name in two suburbs: keep the one in the right ZIP
        hits = [i for i in hits if i["zip"] == zipc] or hits
    return hits
