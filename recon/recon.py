import json, requests
B = "https://gis.cuyahogacounty.gov/server/rest/services/CCFO/Current_Year_Appraisal_Parcels/MapServer"
for layer, where in [(2, "UPPER(parcel_owner) LIKE '%STUPNICKI%'"), (0, "1=1")]:
    r = requests.get(f"{B}/{layer}/query", params={"where": where, "outFields": "*", "f": "json", "resultRecordCount": 2, "returnGeometry": "false"}, timeout=60).json()
    print("@@layer@@", json.dumps({"layer": layer, "error": r.get("error"), "rows": [f["attributes"] for f in r.get("features", [])]})[:6000])
