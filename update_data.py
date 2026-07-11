#!/usr/bin/env python3
"""Fetch the latest Thai lottery draw from GLO and update draws.json + index.html.

Exits 0 with "no change" when the site already has the latest draw, so the
scheduled workflow can simply retry on the next run.
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

API = "https://www.glo.or.th/api/lottery/getLatestLottery"
ROOT = Path(__file__).parent
THAI_MONTHS = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
               "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]


def fetch_latest():
    req = urllib.request.Request(
        API, data=b"{}", method="POST",
        headers={"Content-Type": "application/json",
                 "User-Agent": "Mozilla/5.0 (thai-lottery-stats updater)"})
    body = json.load(urllib.request.urlopen(req, timeout=30))
    r = body["response"]
    data = r["data"]
    draw = {
        "d": r["date"],
        "by": int(r["date"][:4]) + 543,
        "th": "",
        "p1": data["first"]["number"][0]["value"],
        "f3": [x["value"] for x in sorted(data["last3f"]["number"], key=lambda x: x["round"])],
        "l3": [x["value"] for x in sorted(data["last3b"]["number"], key=lambda x: x["round"])],
        "l2": data["last2"]["number"][0]["value"].zfill(2),
    }
    y, m, day = draw["d"].split("-")
    draw["th"] = f"{int(day)} {THAI_MONTHS[int(m) - 1]} {draw['by']}"

    # sanity checks — abort loudly rather than publish garbage
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", draw["d"]), f"bad date: {draw['d']}"
    assert re.fullmatch(r"\d{6}", draw["p1"]), f"bad first prize: {draw['p1']}"
    assert len(draw["f3"]) == 2 and all(re.fullmatch(r"\d{3}", n) for n in draw["f3"]), draw["f3"]
    assert len(draw["l3"]) == 2 and all(re.fullmatch(r"\d{3}", n) for n in draw["l3"]), draw["l3"]
    assert re.fullmatch(r"\d{2}", draw["l2"]), f"bad last2: {draw['l2']}"
    return draw


def main():
    draws = json.loads((ROOT / "draws.json").read_text(encoding="utf-8"))
    latest = fetch_latest()

    if latest["d"] == draws[0]["d"]:
        print(f"no change — site already has draw {latest['d']}")
        return

    if latest["d"] < draws[0]["d"]:
        sys.exit(f"GLO returned {latest['d']} which is older than current {draws[0]['d']} — aborting")

    draws.insert(0, latest)
    (ROOT / "draws.json").write_text(
        json.dumps(draws, ensure_ascii=False), encoding="utf-8")

    payload = json.dumps(draws, ensure_ascii=False).replace("</", "<\\/")
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    new_html, n = re.subn(
        r'(<script id="lottery-data" type="application/json">).*?(</script>)',
        lambda m: m.group(1) + payload + m.group(2),
        html, count=1, flags=re.S)
    if n != 1:
        sys.exit("could not find lottery-data script block in index.html")
    (ROOT / "index.html").write_text(new_html, encoding="utf-8")
    print(f"updated: added draw {latest['d']} ({latest['th']}) — total {len(draws)} draws")


if __name__ == "__main__":
    main()
