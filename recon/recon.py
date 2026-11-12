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
for num in ["300000", "350000", "355000", "000100"]:
    html = lookup(2026, num)
    sp = BeautifulSoup(html, "html.parser")
    out("case", {"num": num, "url": s.current_url, "head": s.last_postback_raw_head[:300],
                 "text": sp.get_text(" ", strip=True)[:2500]})
    if "lblCaseNumber" in html:
        time.sleep(2)
        ph = s.click_case_tab(CASE_TAB_PARTIES)
        out("parties", {"num": num, "url": s.current_url, "text": BeautifulSoup(ph, "html.parser").get_text(" | ", strip=True)[:5000]})
        break
    time.sleep(3)
