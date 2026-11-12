import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import court  # noqa: E402
import leads as L  # noqa: E402
import parcels as P  # noqa: E402

TOKENS = ["Case Parties", "PLAINTIFF", "(1)", "IMAN  MOUSTAFA", "3549 WEST 136TH STREET", "CLEVELAND, OH 44111",
          "ATTORNEY", "NADIA R ZAIEM (0090575)", "1701 EAST 12TH STREET, SUITE 3G", "CLEVELAND, OH 44114-0000",
          "Ph: 216-928-1500", "Answer Filed: N/A", "DEFENDANT", "(1)", "MOUSTAFA  ANTER", "23885 DAVID DRIVE",
          "NORTH OLMSTED, OH 44070", "ATTORNEY", "LILA DAWUD RASLAN (0073256)", "1701 EAST 12TH STREET SUITE 3GW",
          "CLEVELAND, OH 44114-0000", "Print Page"]
PARTIES_HTML = "<table>" + "".join(f"<tr><td>{t}</td></tr>" for t in TOKENS) + "</table>"
SUMMARY_HTML = "<table>" + "".join(f"<tr><td>{a}</td><td>{b}</td></tr>" for a, b in [
    ("Case Number:", "DR-26-410000"), ("Case Title:", "IMAN MOUSTAFA vs. MOUSTAFA ANTER"),
    ("Case Designation:", "DISSOLUTION-CHILDREN"), ("Filing Date:", "11/02/2026"), ("Judge:", "FRANCINE B GOLDBERG"),
    ("Hearing Officer:", "N/A"), ("Last Status:", "ACTIVE"), ("Last Disposition:", "N/A")]) + "</table>"
TODAY = dt.date(2026, 11, 11)


def gis_row(addr, owner, pin="12131022", **kw):
    num, _, street = addr.partition(" ")
    r = {"parcelpin": pin, "deeded_owner": owner, "par_addr_all": f"{num}  {street}, CLEVELAND, OH, 44111",
         "par_city": "CLEVELAND", "par_zip": 44111, "gross_certified_total": 35000,
         "mail_addr_street": addr, "mail_city": "Cleveland", "mail_state": "OH", "mail_zip": "44111"}
    r.update(kw)
    return P.parcel_info(r)


def case(cands):
    c = {"found": True, "first_seen": "2026-11-11", **court.parse_summary(SUMMARY_HTML),
         "parties": court.parse_parties(PARTIES_HTML)}
    sp = L.spouses(c)
    c["cands"] = cands
    c["name_counts"] = {"|".join(P.name_key(s)): 1 for s in sp}
    return {"DR-26-410000": c}


def test_summary_and_parties():
    s = court.parse_summary(SUMMARY_HTML)
    assert s["filed_date"] == "2026-11-02" and s["case_type"] == "DISSOLUTION-CHILDREN"
    assert court.parse_summary("<html>Error</html>") is None
    p = court.parse_parties(PARTIES_HTML)
    assert [x["role"] for x in p] == ["PLAINTIFF", "DEFENDANT"]
    assert p[0]["street"] == "3549 WEST 136TH STREET" and p[0]["zip"] == "44111" and p[0]["city"] == "Cleveland"
    assert p[1]["name"] == "MOUSTAFA ANTER" and p[1]["city"] == "North Olmsted"


def test_case_types_and_numbers():
    assert court.case_number(2026, 410000) == "DR-26-410000"
    assert court.is_kept_type("DIVORCE-NO CHILDREN") and court.is_kept_type("DISSOLUTION-CHILDREN")
    assert not court.is_kept_type("DOMESTIC VIOLENCE")
    assert L.case_label("DISSOLUTION-CHILDREN") == "Dissolution with children"
    assert L.case_label("DIVORCE-NO CHILDREN") == "Divorce"


def test_find_newest_with_gaps():
    newest = 412345
    hidden = {412000, 412001, 412340}
    assert court.find_newest(lambda n: n <= newest and n not in hidden, 410000, 430000) == newest


def test_owner_formats():
    names = lambda o: [(p["last"], p["first"]) for p in P.owner_people(o)]
    assert names("MORRIS, KATHERINE A & JURINA, DONOVAN") == [("MORRIS", "KATHERINE"), ("JURINA", "DONOVAN")]
    assert names("SMIALEK, MARIA R & CHARLES A") == [("SMIALEK", "MARIA"), ("SMIALEK", "CHARLES")]
    assert names("HUGHES HART W & ALMA") == [("HUGHES", "HART"), ("HUGHES", "ALMA")]
    assert names("CHEN, BING WONG & CHEN, SHA LIH PAN -TRS") == [("CHEN", "BING"), ("CHEN", "SHA")]
    assert names("L & S WEINBERG PROPERTIES, LC") == []
    assert P.party_person("IMAN  MOUSTAFA") == {"first": "IMAN", "middle": "", "last": "MOUSTAFA"}


def test_home_at_spouse_address():
    home = gis_row("3549 W 136TH ST", "MOUSTAFA, IMAN")
    out = L.build_leads(case([home]), TODAY)
    assert len(out) == 1 and out[0]["match"] == "home at spouse's address"
    assert out[0]["tier"] == "HOT" and out[0]["market_value"] == 100000
    assert out[0]["case_label"] == "Dissolution with children"


def test_renter_dropped():
    out = L.build_leads(case([gis_row("3549 W 136TH ST", "SOME LANDLORD LLC")]), TODAY)
    assert out == []


def test_joint_owner_elsewhere():
    out = L.build_leads(case([gis_row("77 ELM ST", "ANTER, MOUSTAFA & IMAN", pin="99999999")]), TODAY)
    assert out and out[0]["match"] == "owned by both spouses"
