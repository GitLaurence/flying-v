#!/usr/bin/env python3
"""
fetch_stations.py — Query OpenStreetMap for all Flying V stations in the Philippines.

Usage:
    python3 fetch_stations.py                        # table + CSV + HTML snippet
    python3 fetch_stations.py --update-locations     # inject directly into locations.html
    python3 fetch_stations.py --csv                  # CSV only
    python3 fetch_stations.py --html                 # HTML snippet file only
    python3 fetch_stations.py --json                 # raw JSON to stdout

No third-party dependencies — uses stdlib only.
"""

import argparse
import csv
import json
import os
import re
import sys
import urllib.request
import urllib.parse
from datetime import datetime, timezone

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

QUERY = """
[out:json][timeout:90];
area["name"="Philippines"]["admin_level"="2"]->.ph;
(
  node["amenity"="fuel"]["name"~"Flying.?V",i](area.ph);
  way["amenity"="fuel"]["name"~"Flying.?V",i](area.ph);
  relation["amenity"="fuel"]["name"~"Flying.?V",i](area.ph);
  node["amenity"="fuel"]["brand"~"Flying.?V",i](area.ph);
  way["amenity"="fuel"]["brand"~"Flying.?V",i](area.ph);
);
out center body;
"""

REGION_MAP = {
    # NCR
    "Manila": "ncr", "Quezon City": "ncr", "Caloocan": "ncr", "Las Piñas": "ncr",
    "Makati": "ncr", "Malabon": "ncr", "Mandaluyong": "ncr", "Marikina": "ncr",
    "Muntinlupa": "ncr", "Navotas": "ncr", "Parañaque": "ncr", "Pasay": "ncr",
    "Pasig": "ncr", "Pateros": "ncr", "San Juan": "ncr", "Taguig": "ncr",
    "Valenzuela": "ncr",
    # Luzon
    "Batangas": "luzon", "Laguna": "luzon", "Cavite": "luzon", "Rizal": "luzon",
    "Bulacan": "luzon", "Pampanga": "luzon", "Tarlac": "luzon", "Zambales": "luzon",
    "Nueva Ecija": "luzon", "Bataan": "luzon", "Aurora": "luzon",
    "Ilocos Norte": "luzon", "Ilocos Sur": "luzon", "La Union": "luzon",
    "Pangasinan": "luzon", "Cagayan": "luzon", "Isabela": "luzon",
    "Nueva Vizcaya": "luzon", "Quirino": "luzon",
    "Albay": "luzon", "Camarines Norte": "luzon", "Camarines Sur": "luzon",
    "Catanduanes": "luzon", "Masbate": "luzon", "Sorsogon": "luzon",
    "Legazpi": "luzon", "Naga": "luzon", "Tuguegarao": "luzon",
    "Angeles": "luzon", "San Fernando": "luzon",
    # Visayas
    "Cebu": "visayas", "Cebu City": "visayas", "Mandaue": "visayas",
    "Lapu-Lapu": "visayas", "Talisay": "visayas",
    "Iloilo": "visayas", "Bacolod": "visayas", "Dumaguete": "visayas",
    "Tacloban": "visayas", "Ormoc": "visayas",
    "Bohol": "visayas", "Negros Occidental": "visayas", "Negros Oriental": "visayas",
    "Leyte": "visayas", "Eastern Samar": "visayas", "Western Samar": "visayas",
    # Mindanao
    "Davao": "mindanao", "Davao City": "mindanao",
    "Cagayan de Oro": "mindanao", "Iligan": "mindanao",
    "Zamboanga": "mindanao", "General Santos": "mindanao",
    "Butuan": "mindanao", "Cotabato": "mindanao",
    "Surigao": "mindanao", "Tagum": "mindanao",
    "Digos": "mindanao", "Koronadal": "mindanao",
}

SERVICE_LABELS = {
    "car_wash": "Car Wash",
    "oil_change": "Oil Change",
    "air": "Tire Inflation",
    "toilet": "Restroom",
    "atm": "ATM",
    "shop": "Convenience Store",
}

REGION_LABELS = {
    "ncr": "NCR",
    "luzon": "Luzon",
    "visayas": "Visayas",
    "mindanao": "Mindanao",
}


# ── helpers ──────────────────────────────────────────────────────────────────

def guess_region(tags):
    for field in ("addr:city", "addr:municipality", "addr:province", "addr:region"):
        val = tags.get(field, "")
        for key, region in REGION_MAP.items():
            if key.lower() in val.lower():
                return region
    return "luzon"


def build_address(tags):
    addr = tags.get("addr:full", "")
    if not addr:
        parts = [
            tags.get("addr:housenumber", ""),
            tags.get("addr:street", ""),
            tags.get("addr:barangay", ""),
            tags.get("addr:suburb", ""),
            tags.get("addr:city", tags.get("addr:municipality", "")),
            tags.get("addr:province", ""),
        ]
        addr = ", ".join(p for p in parts if p)
    return addr or "Philippines"


def get_services(tags):
    services = []
    for fuel in ("fuel:octane_91", "fuel:octane_95", "fuel:diesel"):
        if tags.get(fuel) == "yes":
            label = fuel.replace("fuel:octane_", "RON ").replace("fuel:diesel", "Diesel")
            services.append(label)
    for osm_key, label in SERVICE_LABELS.items():
        if tags.get(osm_key) == "yes" or tags.get("service:" + osm_key) == "yes":
            services.append(label)
    return services or ["Gasoline", "Diesel"]


# ── fetch ─────────────────────────────────────────────────────────────────────

def fetch_stations():
    print("Querying OpenStreetMap Overpass API…", file=sys.stderr)
    data = urllib.parse.urlencode({"data": QUERY}).encode()
    req = urllib.request.Request(
        OVERPASS_URL, data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "FlyingVStationFetcher/1.0 (flyingv.com.ph)",
        }
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = json.load(resp)

    elements = raw.get("elements", [])
    print(f"OSM returned {len(elements)} elements.", file=sys.stderr)

    stations = []
    seen = set()

    for el in elements:
        tags = el.get("tags", {})
        name = (tags.get("name") or tags.get("brand") or "Flying V").strip()

        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        coord_key = (round(float(lat), 4), round(float(lon), 4)) if lat and lon else name
        if coord_key in seen:
            continue
        seen.add(coord_key)

        region = guess_region(tags)
        stations.append({
            "name": name,
            "address": build_address(tags),
            "city": tags.get("addr:city") or tags.get("addr:municipality") or "",
            "province": tags.get("addr:province", ""),
            "region": region,
            "services": get_services(tags),
            "hours": tags.get("opening_hours", ""),
            "phone": tags.get("phone", tags.get("contact:phone", "")),
            "lat": lat,
            "lon": lon,
            "osm_id": f"{el['type']}/{el['id']}",
        })

    stations.sort(key=lambda s: (s["region"], s["city"], s["name"]))
    print(f"Deduplicated to {len(stations)} unique stations.", file=sys.stderr)
    return stations


# ── output formatters ─────────────────────────────────────────────────────────

def print_table(stations):
    print(f"\n{'#':<4} {'Name':<35} {'Address':<50} {'City':<20} {'Region':<10}")
    print("-" * 125)
    for i, s in enumerate(stations, 1):
        print(f"{i:<4} {s['name']:<35} {s['address'][:49]:<50} {s['city'][:19]:<20} {s['region']:<10}")
    print(f"\nTotal: {len(stations)} stations")


def write_csv(stations, path="scripts/flying_v_stations.csv"):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "name", "address", "city", "province", "region",
            "services", "hours", "phone", "lat", "lon", "osm_id",
        ])
        writer.writeheader()
        for s in stations:
            row = dict(s)
            row["services"] = ", ".join(s["services"])
            writer.writerow(row)
    print(f"CSV saved → {path}", file=sys.stderr)


def station_card_html(s):
    services_html = "".join(
        f'<span class="station-card__service">{svc}</span>'
        for svc in s["services"]
    )
    hours_part = (
        f'\n              <span class="station-card__hours">&#x1F552; {s["hours"]}</span>'
        if s["hours"] else ""
    )
    phone_part = (
        f'\n              <a href="tel:{s["phone"]}" class="station-card__phone">&#x260E; {s["phone"]}</a>'
        if s["phone"] else ""
    )
    region_label = REGION_LABELS.get(s["region"], s["region"].upper())

    return (
        f'          <article class="station-card" data-region="{s["region"]}">\n'
        f'            <div class="station-card__header">\n'
        f'              <span class="station-card__region-badge">{region_label}</span>\n'
        f'              <h3 class="station-card__name">{s["name"]}</h3>\n'
        f'            </div>\n'
        f'            <div class="station-card__body">\n'
        f'              <p class="station-card__address">&#x1F4CD; {s["address"]}</p>\n'
        f'              <div class="station-card__services">{services_html}</div>\n'
        f'            </div>\n'
        f'            <div class="station-card__footer">{hours_part}{phone_part}\n'
        f'            </div>\n'
        f'          </article>'
    )


def build_grid_html(stations):
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    groups = {r: [s for s in stations if s["region"] == r]
              for r in ("ncr", "luzon", "visayas", "mindanao")}

    lines = [f"          <!-- STATIONS:START — {len(stations)} stations, fetched {timestamp} -->"]
    for region, label in [("ncr", "NCR — Metro Manila"), ("luzon", "Luzon"),
                           ("visayas", "Visayas"), ("mindanao", "Mindanao")]:
        grp = groups[region]
        if not grp:
            continue
        lines.append(f"\n          <!-- ── {label} ({len(grp)}) ── -->")
        lines.extend(station_card_html(s) for s in grp)
    lines.append("          <!-- STATIONS:END -->")
    return "\n".join(lines)


def write_html_snippet(stations, path="scripts/station_cards.html"):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(build_grid_html(stations))
    print(f"HTML snippet saved → {path}", file=sys.stderr)


def update_locations_html(stations, path="locations.html"):
    with open(path, encoding="utf-8") as f:
        content = f.read()

    new_block = build_grid_html(stations)
    updated, count = re.subn(
        r"<!-- STATIONS:START -->.*?<!-- STATIONS:END -->",
        new_block,
        content,
        flags=re.DOTALL,
    )
    if count == 0:
        print(
            f"ERROR: Could not find <!-- STATIONS:START --> … <!-- STATIONS:END --> markers in {path}",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(path, "w", encoding="utf-8") as f:
        f.write(updated)
    print(f"locations.html updated with {len(stations)} stations.", file=sys.stderr)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Fetch Flying V stations from OpenStreetMap")
    parser.add_argument("--update-locations", action="store_true",
                        help="Inject station cards directly into locations.html")
    parser.add_argument("--locations-path", default="locations.html",
                        help="Path to locations.html (default: locations.html)")
    parser.add_argument("--csv",  action="store_true", help="Save CSV to scripts/flying_v_stations.csv")
    parser.add_argument("--html", action="store_true", help="Save HTML snippet to scripts/station_cards.html")
    parser.add_argument("--json", action="store_true", help="Print raw JSON to stdout")
    args = parser.parse_args()

    stations = fetch_stations()

    if args.json:
        print(json.dumps(stations, indent=2, ensure_ascii=False))
        return

    if args.update_locations:
        update_locations_html(stations, args.locations_path)
        write_csv(stations)
        return

    # Default: table + both output files
    print_table(stations)
    write_csv(stations)
    write_html_snippet(stations)


if __name__ == "__main__":
    main()
