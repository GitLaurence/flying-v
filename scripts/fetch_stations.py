#!/usr/bin/env python3
"""
fetch_stations.py — Fetch Flying V stations from OpenStreetMap + Google Places.

Sources
-------
1. OpenStreetMap (Overpass API) — free, no key needed
2. Google Places Text Search  — optional; set GOOGLE_MAPS_API_KEY env var
   or pass --google-key. Adds stations missing from OSM. Requires a Google
   Cloud project with the Places API enabled.
   Add the key as a GitHub Secret named GOOGLE_MAPS_API_KEY.

Usage
-----
    python3 scripts/fetch_stations.py --update-locations
    python3 scripts/fetch_stations.py --update-locations --google-key YOUR_KEY
    python3 scripts/fetch_stations.py --csv
    python3 scripts/fetch_stations.py --json

No third-party dependencies — uses stdlib only.
"""

import argparse
import csv
import html
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone

# ── constants ─────────────────────────────────────────────────────────────────

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
GOOGLE_PLACES_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"

OSM_QUERY = """
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

# Spread queries across regions so Google returns localised results
GOOGLE_QUERIES = [
    "Flying V gas station Metro Manila Philippines",
    "Flying V gas station Quezon City Philippines",
    "Flying V gas station Caloocan Valenzuela Philippines",
    "Flying V gas station Pasig Marikina Philippines",
    "Flying V gas station Makati Taguig Philippines",
    "Flying V gas station Pampanga Bulacan Philippines",
    "Flying V gas station Batangas Laguna Cavite Philippines",
    "Flying V gas station Rizal Quezon Province Philippines",
    "Flying V gas station Tarlac Nueva Ecija Philippines",
    "Flying V gas station Pangasinan La Union Philippines",
    "Flying V gas station Ilocos Philippines",
    "Flying V gas station Cagayan Isabela Philippines",
    "Flying V gas station Albay Camarines Sur Philippines",
    "Flying V gas station Bataan Zambales Philippines",
    "Flying V gas station Cebu Philippines",
    "Flying V gas station Iloilo Bacolod Philippines",
    "Flying V gas station Leyte Samar Philippines",
    "Flying V gas station Bohol Dumaguete Philippines",
    "Flying V gas station Davao Philippines",
    "Flying V gas station Cagayan de Oro Iligan Philippines",
    "Flying V gas station General Santos Koronadal Philippines",
    "Flying V gas station Zamboanga Philippines",
    "Flying V gas station Butuan Surigao Philippines",
]

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
    "Legazpi City": "luzon", "Naga City": "luzon", "Tuguegarao": "luzon",
    "Angeles": "luzon", "San Fernando": "luzon", "Subic": "luzon",
    "Lucena": "luzon", "Lipa": "luzon", "Antipolo": "luzon",
    "Biñan": "luzon", "Santa Rosa": "luzon", "Calamba": "luzon",
    "Bacoor": "luzon", "Dasmariñas": "luzon", "Imus": "luzon",
    "Quezon": "luzon", "Marinduque": "luzon", "Occidental Mindoro": "luzon",
    "Oriental Mindoro": "luzon", "Palawan": "luzon", "Romblon": "luzon",
    # Visayas
    "Cebu": "visayas", "Cebu City": "visayas", "Mandaue": "visayas",
    "Lapu-Lapu": "visayas", "Talisay": "visayas", "Liloan": "visayas",
    "Iloilo": "visayas", "Bacolod": "visayas", "Dumaguete": "visayas",
    "Tacloban": "visayas", "Ormoc": "visayas", "Palo": "visayas",
    "Bohol": "visayas", "Tagbilaran": "visayas",
    "Negros Occidental": "visayas", "Negros Oriental": "visayas",
    "Southern Leyte": "visayas", "Leyte": "visayas",
    "Eastern Samar": "visayas", "Western Samar": "visayas",
    "Roxas City": "visayas", "Kabankalan": "visayas",
    "Capiz": "visayas", "Aklan": "visayas", "Antique": "visayas",
    "Guimaras": "visayas", "Siquijor": "visayas",
    "Carcar": "visayas", "Catmon": "visayas", "Maasin": "visayas",
    "Oton": "visayas", "San Enrique": "visayas", "Ayungon": "visayas",
    # Mindanao
    "Davao": "mindanao", "Davao City": "mindanao",
    "Cagayan de Oro": "mindanao", "Iligan": "mindanao",
    "Zamboanga": "mindanao", "General Santos": "mindanao",
    "Butuan": "mindanao", "Cotabato": "mindanao",
    "Surigao": "mindanao", "Tagum": "mindanao",
    "Digos": "mindanao", "Koronadal": "mindanao",
    "Kidapawan": "mindanao", "Pagadian": "mindanao",
    "Dipolog": "mindanao", "Ozamiz": "mindanao",
    "Mati": "mindanao", "Bislig": "mindanao",
    "Bukidnon": "mindanao", "Malaybalay": "mindanao", "Valencia City": "mindanao",
    "Misamis Oriental": "mindanao", "Misamis Occidental": "mindanao",
    "Lanao del Norte": "mindanao", "Lanao del Sur": "mindanao",
    "Zamboanga del Norte": "mindanao", "Zamboanga del Sur": "mindanao",
    "Sultan Kudarat": "mindanao", "South Cotabato": "mindanao", "Sarangani": "mindanao",
    "Agusan del Norte": "mindanao", "Agusan del Sur": "mindanao",
    "Surigao del Norte": "mindanao", "Surigao del Sur": "mindanao",
    "Davao del Sur": "mindanao", "Davao del Norte": "mindanao",
    "Davao Oriental": "mindanao", "Davao Occidental": "mindanao",
    "Davao de Oro": "mindanao",
    "Basilan": "mindanao", "Sulu": "mindanao", "Tawi-Tawi": "mindanao",
}

# Longest key first, so e.g. "Quezon City" (ncr) is checked before the more
# generic "Quezon" (luzon province), and "Southern Leyte" (visayas) before
# "San Juan" (ncr) — plain dict order previously let the first *any* substring
# hit win, which meant short/generic keys silently shadowed more specific ones.
REGION_MAP_BY_SPECIFICITY = sorted(REGION_MAP.items(), key=lambda kv: -len(kv[0]))

OSM_SERVICE_TAGS = {
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

GENERIC_NAMES = {"flying v", "flying-v", "flyingv", "flying v gasoline station",
                 "flying v gas station", "flying v petroleum"}

# ── helpers ───────────────────────────────────────────────────────────────────

def guess_region(text):
    t = text.lower()
    for key, region in REGION_MAP_BY_SPECIFICITY:
        if key.lower() in t:
            return region
    return "luzon"


def make_display_name(raw_name, street="", barangay="", city="", province=""):
    """Give generic/unbranded entries (e.g. a raw OSM name like 'Gasoline
    Station' that carries no 'Flying V' branding) a location-based title."""
    normalized = re.sub(
        r'\s+(gas(oline)?\s+)?station\s*$', '', raw_name, flags=re.IGNORECASE
    ).strip()

    if normalized.lower() not in GENERIC_NAMES and "flying v" in normalized.lower():
        return raw_name

    location = city or province
    if street and location:
        suffix = f"{street}, {location}"
    elif street:
        suffix = street
    elif barangay and location:
        suffix = f"{barangay}, {location}"
    elif location:
        suffix = location
    else:
        return raw_name  # nothing to add

    return f"Flying V – {suffix}"


def is_complete(s):
    """Return False for entries with no usable address information."""
    addr = s["address"].strip()
    # Address is missing or just the country name
    if not addr or addr.lower() == "philippines":
        return False
    # make_display_name couldn't find any location — still fully generic
    if s["name"].strip().lower() in GENERIC_NAMES:
        return False
    return True


def are_nearby(s1, s2, threshold=0.002):
    """True if two stations are within ~200 m of each other."""
    try:
        return (abs(float(s1["lat"]) - float(s2["lat"])) < threshold and
                abs(float(s1["lon"]) - float(s2["lon"])) < threshold)
    except (TypeError, ValueError):
        return False


# ── OSM source ────────────────────────────────────────────────────────────────

def _osm_build_address(tags):
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


def _osm_get_services(tags):
    services = []
    for fuel in ("fuel:octane_91", "fuel:octane_95", "fuel:diesel"):
        if tags.get(fuel) == "yes":
            label = fuel.replace("fuel:octane_", "RON ").replace("fuel:diesel", "Diesel")
            services.append(label)
    for osm_key, label in OSM_SERVICE_TAGS.items():
        if tags.get(osm_key) == "yes" or tags.get("service:" + osm_key) == "yes":
            services.append(label)
    return services or ["Gasoline", "Diesel"]


def fetch_osm():
    print("OSM: querying Overpass API…", file=sys.stderr)
    data = urllib.parse.urlencode({"data": OSM_QUERY}).encode()
    req = urllib.request.Request(
        OVERPASS_URL, data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "User-Agent": "FlyingVStationFetcher/1.0"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = json.load(resp)

    elements = raw.get("elements", [])
    print(f"OSM: {len(elements)} elements returned.", file=sys.stderr)

    stations, seen = [], set()
    for el in elements:
        tags = el.get("tags", {})
        lat = el.get("lat") or el.get("center", {}).get("lat")
        lon = el.get("lon") or el.get("center", {}).get("lon")
        key = (round(float(lat), 4), round(float(lon), 4)) if (lat and lon) else id(el)
        if key in seen:
            continue
        seen.add(key)

        street   = tags.get("addr:street", "")
        barangay = tags.get("addr:barangay", "")
        city     = tags.get("addr:city") or tags.get("addr:municipality") or ""
        province = tags.get("addr:province", "")
        # Prefer whichever of name/brand actually carries the "Flying V"
        # branding — some OSM nodes have a generic name (e.g. "Gasoline
        # Station") but a correctly branded `brand` tag, or vice versa.
        name_tag, brand_tag = tags.get("name", ""), tags.get("brand", "")
        if "flying" in name_tag.lower():
            raw_name = name_tag
        elif "flying" in brand_tag.lower():
            raw_name = brand_tag
        else:
            raw_name = name_tag or brand_tag or "Flying V"
        raw_name = raw_name.strip()

        stations.append({
            "name":     make_display_name(raw_name, street, barangay, city, province),
            "address":  _osm_build_address(tags),
            "city":     city,
            "province": province,
            "region":   guess_region(" ".join([city, province, tags.get("addr:region", "")])),
            "services": _osm_get_services(tags),
            "hours":    tags.get("opening_hours", ""),
            "phone":    tags.get("phone", tags.get("contact:phone", "")),
            "lat":      lat,
            "lon":      lon,
            "source":   "osm",
            "osm_id":   f"{el['type']}/{el['id']}",
        })

    before = len(stations)
    stations = [s for s in stations if is_complete(s)]
    print(f"OSM: {before - len(stations)} incomplete entries removed, "
          f"{len(stations)} kept.", file=sys.stderr)
    return stations


# ── Google Places source ──────────────────────────────────────────────────────

def _google_fetch_page(query, api_key, page_token=None):
    params = {"query": query, "key": api_key, "language": "en"}
    if page_token:
        params["pagetoken"] = page_token
    url = GOOGLE_PLACES_URL + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as resp:
        return json.load(resp)


def _station_from_google_place(place):
    raw_name = place.get("name", "Flying V").strip()
    formatted = place.get("formatted_address", "Philippines")
    # Strip trailing ", Philippines"
    addr = re.sub(r",?\s*Philippines\s*$", "", formatted).strip()

    # Extract city as the last meaningful component before the country
    parts = [p.strip() for p in addr.split(",")]
    city = parts[-1] if len(parts) > 1 else ""

    loc = place.get("geometry", {}).get("location", {})
    lat, lon = loc.get("lat"), loc.get("lng")

    region = guess_region(formatted)
    name = make_display_name(raw_name, city=city)

    return {
        "name":     name,
        "address":  addr,
        "city":     city,
        "province": "",
        "region":   region,
        "services": ["Gasoline", "Diesel"],
        "hours":    "",
        "phone":    "",
        "lat":      lat,
        "lon":      lon,
        "source":   "google",
        "osm_id":   f"google/{place.get('place_id', '')}",
    }


def fetch_google(api_key):
    print(f"Google Places: running {len(GOOGLE_QUERIES)} queries…", file=sys.stderr)
    stations, seen_ids = [], set()

    for i, query in enumerate(GOOGLE_QUERIES, 1):
        print(f"  [{i}/{len(GOOGLE_QUERIES)}] {query}", file=sys.stderr)
        page_token = None
        for page in range(3):           # max 3 pages = 60 results per query
            if page > 0:
                time.sleep(2)           # Google requires a short delay before next_page_token
            try:
                data = _google_fetch_page(query, api_key, page_token)
            except Exception as exc:
                print(f"    WARNING: {exc}", file=sys.stderr)
                break

            status = data.get("status")
            if status not in ("OK", "ZERO_RESULTS"):
                print(f"    WARNING: status={status}", file=sys.stderr)
                break

            for place in data.get("results", []):
                pid = place.get("place_id", "")
                if pid in seen_ids:
                    continue
                seen_ids.add(pid)
                s = _station_from_google_place(place)
                if is_complete(s):
                    stations.append(s)

            page_token = data.get("next_page_token")
            if not page_token:
                break

        time.sleep(0.3)                 # polite delay between queries

    print(f"Google Places: {len(stations)} complete stations found.", file=sys.stderr)
    return stations


# ── merge ─────────────────────────────────────────────────────────────────────

def merge_sources(primary, secondary):
    """Add secondary stations that aren't already represented in primary."""
    result = list(primary)
    added = 0
    for s2 in secondary:
        if not any(are_nearby(s2, s1) for s1 in result):
            result.append(s2)
            added += 1
    print(f"Merge: +{added} stations from secondary source "
          f"({len(result)} total).", file=sys.stderr)
    return result


# ── output ────────────────────────────────────────────────────────────────────

def print_table(stations):
    print(f"\n{'#':<4} {'Name':<40} {'Address':<45} {'City':<18} {'Src':<6} {'Region'}")
    print("-" * 122)
    for i, s in enumerate(stations, 1):
        src = s.get("source", "")[:6]
        print(f"{i:<4} {s['name'][:39]:<40} {s['address'][:44]:<45} "
              f"{s['city'][:17]:<18} {src:<6} {s['region']}")
    print(f"\nTotal: {len(stations)} stations")


def write_csv(stations, path="scripts/flying_v_stations.csv"):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "name", "address", "city", "province", "region",
            "services", "hours", "phone", "lat", "lon", "source", "osm_id",
        ])
        writer.writeheader()
        for s in stations:
            row = dict(s)
            row["services"] = ", ".join(s["services"])
            writer.writerow(row)
    print(f"CSV saved → {path}", file=sys.stderr)


def station_card_html(s):
    name = html.escape(s["name"])
    address = html.escape(s["address"])
    hours = html.escape(s["hours"]) if s["hours"] else ""
    phone = html.escape(s["phone"]) if s["phone"] else ""
    region = html.escape(s["region"])

    services_html = "".join(
        f'<span class="station-card__service">{html.escape(svc)}</span>'
        for svc in s["services"]
    )
    hours_part = (
        f'\n              <span class="station-card__hours">&#x1F552; {hours}</span>'
        if hours else ""
    )
    phone_part = (
        f'\n              <a href="tel:{phone}" class="station-card__phone">'
        f'&#x260E; {phone}</a>'
        if phone else ""
    )
    region_label = html.escape(REGION_LABELS.get(s["region"], s["region"].upper()))
    footer_part = (
        f'            <div class="station-card__footer">{hours_part}{phone_part}\n'
        f'            </div>\n'
        if hours or phone else ""
    )
    return (
        f'          <article class="station-card" data-region="{region}">\n'
        f'            <div class="station-card__header">\n'
        f'              <span class="station-card__region-badge">{region_label}</span>\n'
        f'              <h3 class="station-card__name">{name}</h3>\n'
        f'            </div>\n'
        f'            <div class="station-card__body">\n'
        f'              <p class="station-card__address">&#x1F4CD; {address}</p>\n'
        f'              <div class="station-card__services">{services_html}</div>\n'
        f'            </div>\n'
        f'{footer_part}'
        f'          </article>'
    )


def build_grid_html(stations):
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    sources = set(s.get("source", "osm") for s in stations)
    groups = {r: [s for s in stations if s["region"] == r]
              for r in ("ncr", "luzon", "visayas", "mindanao")}

    lines = [f"          <!-- STATIONS:START — {len(stations)} stations "
             f"({', '.join(sorted(sources))}), fetched {timestamp} -->"]
    for region, label in [("ncr", "NCR — Metro Manila"), ("luzon", "Luzon"),
                           ("visayas", "Visayas"), ("mindanao", "Mindanao")]:
        grp = groups[region]
        if not grp:
            continue
        lines.append(f"\n          <!-- ── {label} ({len(grp)}) ── -->")
        lines.extend(station_card_html(s) for s in grp)
    lines.append("          <!-- STATIONS:END -->")
    return "\n".join(lines)


def update_locations_html(stations, path="locations.html"):
    with open(path, encoding="utf-8") as f:
        content = f.read()

    new_block = build_grid_html(stations)
    updated, count = re.subn(
        r"<!-- STATIONS:START.*?-->.*?<!-- STATIONS:END -->",
        new_block,
        content,
        flags=re.DOTALL,
    )
    if count == 0:
        print(f"ERROR: STATIONS markers not found in {path}", file=sys.stderr)
        sys.exit(1)

    with open(path, "w", encoding="utf-8") as f:
        f.write(updated)
    print(f"locations.html updated → {len(stations)} stations.", file=sys.stderr)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Fetch Flying V stations from OpenStreetMap (+ optionally Google Places)"
    )
    parser.add_argument("--update-locations", action="store_true",
                        help="Inject cards directly into locations.html")
    parser.add_argument("--locations-path", default="locations.html")
    parser.add_argument("--google-key", default=os.environ.get("GOOGLE_MAPS_API_KEY", ""),
                        help="Google Maps API key (or set GOOGLE_MAPS_API_KEY env var)")
    parser.add_argument("--csv",  action="store_true")
    parser.add_argument("--html", action="store_true",
                        help="Save HTML snippet to scripts/station_cards.html")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    # ── fetch ──
    stations = fetch_osm()

    if args.google_key:
        google_stations = fetch_google(args.google_key)
        stations = merge_sources(stations, google_stations)
    else:
        print("Google Places: skipped (no API key). "
              "Set GOOGLE_MAPS_API_KEY for fuller coverage.", file=sys.stderr)

    stations.sort(key=lambda s: (s["region"], s["city"], s["name"]))

    # ── output ──
    if args.json:
        print(json.dumps(stations, indent=2, ensure_ascii=False))
        return

    if args.update_locations:
        update_locations_html(stations, args.locations_path)
        write_csv(stations)
        return

    print_table(stations)
    write_csv(stations)

    if args.html:
        path = "scripts/station_cards.html"
        os.makedirs("scripts", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(build_grid_html(stations))
        print(f"HTML snippet saved → {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
