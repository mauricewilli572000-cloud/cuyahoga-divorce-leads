import json, re, sys, time
sys.path.insert(0, "recon")
from bs4 import BeautifulSoup
from cpdocket import CuyahogaDocketSession, SEARCH_TYPE_RADIO_NAME, CASE_TAB_PARTIES
def out(t, o): print(f"@@{t}@@ " + json.dumps(o)[:9000], flush=True)
P = "ctl00$SheetContentPlaceHolder$civilCaseSearch$"
s = CuyahogaDocketSession()
def lookup(year, num):
    s.load_search_page(); time.sleep(2)
    s._async_postback("ctl00$SheetContentPlaceHolder$rbCivilCase", extra_fields={SEARCH_TYPE_RADIO_NAME: "cvcase"}); time.sleep(2)
    html, _ = s._async_postback(P + "btnSubmitCase", extra_fields={
        SEARCH_TYPE_RADIO_NAME: "cvcase", P + "ddlCaseType": "DR", P + "ddlCaseYear": str(year),
        P + "txtCaseNum": num, P + "btnSubmitCase": "Submit Search"})
    return html
for num in [str(n) for n in range(380000, 451000, 10000)] + ["100000", "200000", "500000", "600000", "800000", "900000"]:
    html = lookup(2026, num)
    sp = BeautifulSoup(html, "html.parser")
    out("case", {"num": num, "url": s.current_url, "found": "lblCaseNumber" in html,
                 "text": sp.get_text(" ", strip=True)[:300] if "lblCaseNumber" not in html else sp.get_text(" | ", strip=True)[:3000]})
    if "lblCaseNumber" in html and not globals().get("did"):
        did = True
        time.sleep(2)
        ph = s.click_case_tab(CASE_TAB_PARTIES)
        out("parties", {"num": num, "url": s.current_url, "text": BeautifulSoup(ph, "html.parser").get_text(" | ", strip=True)[:5000]})
    time.sleep(3)
