import json, re, sys, time
sys.path.insert(0, "recon")
from bs4 import BeautifulSoup
from cpdocket import CuyahogaDocketSession, SEARCH_TYPE_RADIO_NAME
def out(t, o): print(f"@@{t}@@ " + json.dumps(o)[:9000], flush=True)
s = CuyahogaDocketSession()
html = s.load_search_page()
soup = BeautifulSoup(html, "html.parser")
radios = [{"id": r.get("id"), "value": r.get("value"), "onclick": (r.get("onclick") or "")[:150],
           "label": (soup.find("label", {"for": r.get("id")}).get_text(" ", strip=True) if soup.find("label", {"for": r.get("id")}) else "")}
          for r in soup.find_all("input", {"type": "radio"})]
out("radios", radios)
out("selects", [{"name": x.get("name"), "opts": [(o.get("value"), o.get_text(strip=True)) for o in x.find_all("option")][:40]} for x in soup.find_all("select")])
picks = [r for r in radios if r["value"] and re.search(r"case", (r["label"] or "") + (r["id"] or ""), re.I)]
for r in picks[:3]:
    time.sleep(3)
    target = r["id"].replace("SheetContentPlaceHolder_", "ctl00$SheetContentPlaceHolder$")
    content, _ = s._async_postback(target, extra_fields={SEARCH_TYPE_RADIO_NAME: r["value"]})
    sp = BeautifulSoup(content, "html.parser")
    out("panel", {"radio": r, "inputs": [(i.get("name"), i.get("type"), i.get("value")) for i in sp.find_all("input")][:40],
                  "selects": [{"name": x.get("name"), "opts": [(o.get("value"), o.get_text(strip=True)) for o in x.find_all("option")][:30]} for x in sp.find_all("select")],
                  "text": sp.get_text(" ", strip=True)[:1500]})
