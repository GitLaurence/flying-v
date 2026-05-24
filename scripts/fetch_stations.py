#!/usr/bin/env python3
"""
fetch_stations.py — Query OpenStreetMap for all Flying V stations in the Philippines.

Usage:
    python3 fetch_stations.py                  # prints table + saves CSV + saves HTML snippet
    python3 fetch_stations.py --csv            # CSV only
    python3 fetch_stations.py --html           # HTML station cards only
    python3 fetch_stations.py --json           # raw JSON only

Requirements:
    pip install requests
"""

import argparse
import csv
import json
import sys
import time
import urllib.request
import urllib.parse

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
    # Luzon provinces / cities (non-exhaustive — add more as needed)
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

SERVICE_ICONS = {
    "car_wash": "Car Wash",
    "oil_change": "Oil Change",
    "air": "Tire Inflation",
    "toilet": "Restroom",
    "atm": "ATM",
    "shop": "Convenience Store",
}


def guess_region(tags):
    for field in ("addr:city", "addr:municipality", "addr:province", "addr:region"):
        val = tags.get(field, "")
        for key, region in REGION_MAP.items():
            if key.lower() in val.lower():
                return region
    return "luzon"  # default fallback


def build_address(tags):
    parts = [
        tags.get("addr:housenumber", ""),
        tags.get("addr:street", ""),
        tags.get("addr:barangay", ""),
        tags.get("addr:suburb", ""),
        tags.get("addr:city", tags.get("addr:municipality", "")),
        tags.get("addr:province", ""),
    ]
    addr = tags.get("addr:full", "")
    if not addr:
        addr = ", ".join(p for p in parts if p)
    return addr or "Philippines"


def get_services(tags):
    services = []
    # OSM fuel types
    for fuel in ("fuel:octane_91", "fuel:octane_95", "fuel:diesel"):
        if tags.get(fuel) == "yes":
            label = fuel.replace("fuel:octane_", "RON ").replace("fuel:", "").replace("diesel", "Diesel")
            services.append(label)
    # Other amenities
    for osm_key, label in SERVICE_ICONS.items():
        if tags.get(osm_key) == "yes" or tags.get("service:" + osm_key) == "yes":
            services.append(label)
    if not services:
        services = ["Gasoline", "Diesel"]
    return services


def fetch_stations():
    print("Querying OpenStreetMap Overpass API…", file=sys.stderr)
    data = urllib.parse.urlencode({"data": QUERY}).encode()
    req = urllib.request.Request(OVERPASS_URL, data=data,
                                  headers={"Content-Type": "application/x-www-form-urlencoded",
                                           "User-Agent": "FlyingVStationFetcher/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = json.load(resp)

    elements = raw.get("elements", [])
    print(f"Found {len(elements)} elements.", file=sys.stderr)

    stations = []
    seen = set()

    for el in elements:
        tags = el.get("tags", {})
        name = tags.get("name") or tags.get("brand") or "Flying V"

        # Deduplicate by coordinates (ways include a `center` key)
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        key = (round(float(lat), 4), round(float(lon), 4)) if lat and lon else name
        if key in seen:
            continue
        seen.add(key)

        city = tags.get("addr:city") or tags.get("addr:municipality") or tags.get("addr:province", "")
        province = tags.get("addr:province", "")
        region = guess_region(tags)

        stations.append({
            "name": name.strip(),
            "address": build_address(tags),
            "city": city,
            "province": province,
            "region": region,
            "services": get_services(tags),
            "hours": tags.get("opening_hours", ""),
            "phone": tags.get("phone", tags.get("contact:phone", "")),
            "lat": lat,
            "lon": lon,
            "osm_id": f"{el['type']}/{el['id']}",
        })

    stations.sort(key=lambda s: (s["region"], s["city"], s["name"]))
    return stations


def print_table(stations):
    print(f"\n{'#':<4} {'Name':<35} {'Address':<50} {'City':<20} {'Region':<10}")
    print("-" * 125)
    for i, s in enumerate(stations, 1):
        print(f"{i:<4} {s['name']:<35} {s['address'][:49]:<50} {s['city'][:19]:<20} {s['region']:<10}")
    print(f"\nTotal: {len(stations)} stations")


def write_csv(stations, path="flying_v_stations.csv"):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "name", "address", "city", "province", "region",
            "services", "hours", "phone", "lat", "lon", "osm_id"
        ])
        writer.writeheader()
        for s in stations:
            row = dict(s)
            row["services"] = ", ".join(s["services"])
            writer.writerow(row)
    print(f"CSV saved to {path}", file=sys.stderr)


def station_card_html(s):
    services_html = "".join(
        f'<span class="station-card__service">{svc}</span>'
        for svc in s["services"]
    )
    hours_html = f'<p class="station-card__hours">&#x1F552; {s["hours"]}</p>' if s["hours"] else ""
    phone_html = (f'<p class="station-card__phone">'
                  f'<a href="tel:{s["phone"]}">{s["phone"]}</a></p>') if s["phone"] else ""

    return f"""
          <article class="station-card" data-region="{s['region']}">
            <div class="station-card__header">
              <h3 class="station-card__name">{s['name']}</h3>
              <span class="station-card__region-badge">{s['region'].upper()}</span>
            </div>
            <div class="station-card__body">
              <p class="station-card__address">&#x1F4CD; {s['address']}</p>
              {hours_html}
              {phone_html}
              <div class="station-card__services">{services_html}</div>
            </div>
          </article>"""


def write_html(stations, path="station_cards.html"):
    ncr = [s for s in stations if s["region"] == "ncr"]
    luzon = [s for s in stations if s["region"] == "luzon"]
    visayas = [s for s in stations if s["region"] == "visayas"]
    mindanao = [s for s in stations if s["region"] == "mindanao"]

    lines = [
        f"<!-- AUTO-GENERATED: {len(stations)} Flying V stations from OpenStreetMap -->",
        f'<div class="station-grid" id="station-grid">',
    ]
    for group, label in [(ncr, "NCR"), (luzon, "Luzon"), (visayas, "Visayas"), (mindanao, "Mindanao")]:
        if group:
            lines.append(f"\n          <!-- ── {label} ({len(group)} stations) ── -->")
            lines.extend(station_card_html(s) for s in group)
    lines.append("\n        </div>")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"HTML snippet saved to {path}", file=sys.stderr)
    print(f"Paste the contents of {path} into the <div id='station-grid'> in locations.html", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Fetch Flying V stations from OpenStreetMap")
    parser.add_argument("--csv",  action="store_true", help="Save CSV")
    parser.add_argument("--html", action="store_true", help="Save HTML station card snippet")
    parser.add_argument("--json", action="store_true", help="Print raw JSON to stdout")
    args = parser.parse_args()

    stations = fetch_stations()

    if args.json:
        print(json.dumps(stations, indent=2, ensure_ascii=False))
        return

    if not args.csv and not args.html:
        # Default: print table + save both files
        print_table(stations)
        write_csv(stations)
        write_html(stations)
    else:
        if args.csv:
            write_csv(stations)
        if args.html:
            write_html(stations)


if __name__ == "__main__":
    main()
