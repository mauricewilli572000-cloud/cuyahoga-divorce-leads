import json, sys, time, logging
sys.path.insert(0, ".")
logging.basicConfig(level=logging.INFO)
from bs4 import BeautifulSoup
import court
from cpdocket import SEARCH_TYPE_RADIO_NAME
def out(t, o): print(f"@@{t}@@ " + json.dumps(o)[:9000], flush=True)
d = court.Docket()
for n in [411260, 411300, 411500, 412000, 413000, 414000, 416000, 418000]:
    info = d.fetch(court.case_number(2026, n))
    out("probe", {"n": n, "found": bool(info), "filed": (info or {}).get("filed_date"), "type": (info or {}).get("case_type")})
s = d.s
s.load_search_page(); time.sleep(2)
html, _ = s._async_postback("ctl00$SheetContentPlaceHolder$rbCivilName", extra_fields={SEARCH_TYPE_RADIO_NAME: "cvname"})
sp = BeautifulSoup(html, "html.parser")
out("namepanel", {"inputs": [(i.get("name"), i.get("type"), i.get("value")) for i in sp.find_all("input")][8:40],
                  "selects": [{"name": x.get("name"), "opts": [(o.get("value"), o.get_text(strip=True)) for o in x.find_all("option")][:25]} for x in sp.find_all("select")],
                  "text": sp.get_text(" ", strip=True)[300:1500]})
