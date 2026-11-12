"""Read Domestic Relations cases from the Cuyahoga County Clerk of Courts docket, one case number at a time."""
from __future__ import annotations

import logging
import re
import time

from bs4 import BeautifulSoup

import config
from cpdocket import CASE_TAB_PARTIES, SEARCH_TYPE_RADIO_NAME, CuyahogaDocketSession

log = logging.getLogger(__name__)

P = "ctl00$SheetContentPlaceHolder$civilCaseSearch$"
RADIO_TARGET = "ctl00$SheetContentPlaceHolder$rbCivilCase"
ROLES = {"PLAINTIFF", "DEFENDANT", "PETITIONER", "CO-PETITIONER", "RESPONDENT"}
CSZ_RE = re.compile(r"^(.*?),\s*([A-Z]{2})\s+(\d{5})(?:-\d{0,4})?$")
SUMMARY = "SheetContentPlaceHolder_caseSummary_"


def case_number(year: int, n: int) -> str:
    return f"DR-{year % 100:02d}-{n:06d}"


def is_kept_type(case_type: str) -> bool:
    t = (case_type or "").upper()
    return any(w in t for w in config.KEEP_TYPE_WORDS) and not any(w in t for w in config.SKIP_TYPE_WORDS)


FIELDS = {"case number": "case_number", "case title": "caption", "case designation": "case_type",
          "filing date": "filed_date", "judge": "judge", "last status": "status", "last disposition": "disposition"}


def parse_summary(html: str) -> dict | None:
    """Case summary page -> fields (read from the 'Label: | value' text, which works for every case type)."""
    if "Filing Date" not in html:
        return None
    toks = [re.sub(r"\s+", " ", t).strip() for t in BeautifulSoup(html, "html.parser").get_text(" | ", strip=True).split("|")]
    toks = [t for t in toks if t]
    info = {}
    for i, t in enumerate(toks[:-1]):
        key = FIELDS.get(t.rstrip(":").strip().lower())
        if key and t.endswith(":") and key not in info:
            nxt = toks[i + 1]
            info[key] = "" if nxt.endswith(":") else nxt
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", info.get("filed_date", ""))
    if not m:
        return None
    info["filed_date"] = f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return info


def parse_parties(html: str) -> list[dict]:
    """Spouses from the Parties tab: role, name, street, city, state, zip (attorneys skipped)."""
    text = BeautifulSoup(html, "html.parser").get_text(" | ", strip=True)
    if "Case Parties" in text:
        text = text.split("Case Parties", 1)[1]
    toks = [re.sub(r"\s+", " ", t).strip() for t in text.split("|")]
    toks = [t for t in toks if t]
    out, i = [], 0
    while i < len(toks):
        if toks[i].upper() in ROLES and i + 2 < len(toks) and re.fullmatch(r"\(\d+\)", toks[i + 1]):
            role, name, j, street = toks[i].upper(), toks[i + 2], i + 3, []
            city = state = zipc = ""
            while j < len(toks) and j < i + 8 and toks[j].upper() not in ROLES and toks[j].upper() != "ATTORNEY":
                m = CSZ_RE.match(toks[j].upper())
                if m:
                    city, state, zipc = m.group(1).title(), m.group(2), m.group(3)
                    j += 1
                    break
                street.append(toks[j])
                j += 1
            out.append({"role": role, "name": name, "street": " ".join(street).upper(), "city": city,
                        "state": state, "zip": zipc})
            i = j
        else:
            i += 1
    return out


class Docket:
    """One browser-like session on the clerk's docket; every page request is counted and spaced out."""

    def __init__(self):
        self.s = CuyahogaDocketSession()
        self.requests = 0

    def _pause(self):
        self.requests += 1
        time.sleep(config.REQUEST_DELAY)

    def fetch(self, cn: str) -> dict | None:
        """Summary (+ parties for divorce-type cases). None = no such case (or hidden, e.g. DV)."""
        m = re.fullmatch(r"DR-(\d{2})-(\d{6})", cn)
        year, num = 2000 + int(m.group(1)), m.group(2)
        self.s.load_search_page(); self._pause()
        self.s._async_postback(RADIO_TARGET, extra_fields={SEARCH_TYPE_RADIO_NAME: "cvcase"}); self._pause()
        html, _ = self.s._async_postback(P + "btnSubmitCase", extra_fields={
            SEARCH_TYPE_RADIO_NAME: "cvcase", P + "ddlCaseType": "DR", P + "ddlCaseYear": str(year),
            P + "txtCaseNum": num, P + "btnSubmitCase": "Submit Search"})
        self._pause()
        info = parse_summary(html)
        if not info:
            if self.requests < 12:
                log.info("%s: no case (%s)", cn, (self.s.current_url or "")[-60:])
            return None
        if is_kept_type(info["case_type"]):
            info["parties"] = parse_parties(self.s.click_case_tab(CASE_TAB_PARTIES))
            self._pause()
        return info


def find_newest(exists, lo: int, hi: int) -> int:
    """Highest existing number in [lo, hi), where exists(lo) is known true. Gaps of hidden cases are
    stepped over by also checking a few numbers above each miss."""
    def any_near(n):
        return any(exists(n + k) for k in (0, 1, 2))
    while hi - lo > 3:
        mid = (lo + hi) // 2
        if any_near(mid):
            lo = mid
        else:
            hi = mid
    best = lo
    for n in range(lo + 1, hi + 3):
        if exists(n):
            best = n
    return best
