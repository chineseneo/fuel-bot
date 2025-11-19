# daily_fuel_email.py
import smtplib
import requests
import json
import os
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import matplotlib.pyplot as plt

CACHE_FILE = "fuel_cache.json"
HISTORY_DAYS = 84
PZT3_API_URL = "https://projectzerothree.info/api.php?format=json"

# Display name mapping
DISPLAY_NAME_MAP = {
    "Coles Express Wantirna South": "Coles",
    "Reddy Express Wantirna South": "Coles",   # new name maps to Coles
    "BP Wantirna South": "BP",
    ("7-Eleven Wantirna South", "1247 High Street Road "): "711 M3",
    ("7-Eleven Wantirna South", "401 Burwood Highway & Stud Road "): "711 Westfield",
}

def get_display_name(name, address):
    if name in DISPLAY_NAME_MAP:
        return DISPLAY_NAME_MAP[name]
    if (name, address) in DISPLAY_NAME_MAP:
        return DISPLAY_NAME_MAP[(name, address)]
    return name

def get_cached_data():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_cache(data):
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f)

def prune_cache(cache):
    today = datetime.date.today()
    cutoff = today - datetime.timedelta(days=HISTORY_DAYS)
    return {
        day: data
        for day, data in cache.items()
        if datetime.date.fromisoformat(day) >= cutoff
    }

def get_u98_prices():
    params = {
        "neLat": -37.85, "neLng": 145.26,
        "swLat": -37.90, "swLng": 145.18,
    }

    url = "https://petrolspy.com.au/webservice-1/station/box"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"PetrolSpy API error: {e}")
        return [{"brand": "Error", "name": "PetrolSpy fetch failed", "price": 0.0}], {}

    target_stations = [
        "Coles Express Wantirna South",
        "Reddy Express Wantirna South",
        "7-Eleven Wantirna South",
        "BP Wantirna South"
    ]

    stations = []
    today_str = datetime.date.today().isoformat()
    cache = get_cached_data()
    cache = prune_cache(cache)
    if today_str not in cache:
        cache[today_str] = {}

    for station in data.get("message", {}).get("list", []):
        name = station.get("name", "")
        brand = station.get("brand", "").strip()
        address = station.get("address", "")

        if name in target_stations and "U98" in station.get("prices", {}):
            amount = station["prices"]["U98"].get("amount")
            if amount:
                display_name = get_display_name(name, address)
                price_val = float(amount)
                stations.append({
                    "brand": brand,
                    "name": display_name,
                    "price": price_val,
                })
                cache[today_str][display_name] = price_val

    save_cache(cache)
    stations = sorted(stations, key=lambda x: x['price'])
    return stations, cache

def get_vic_lowest_from_pzt3(fuel_type="U98"):
    """
    Query ProjectZeroThree and return the cheapest fuel station in VIC
    for the given fuel_type (default U98).

    Returns a dict like:
    {
        "price": 134.7,
        "name": "11-Seven Newcomb",
        "suburb": "Newcomb",
        "type": "U98",
        "postcode": "3219",
        "lat": -38.173687,
        "lng": 144.401947,
    }
    or None if nothing found / API error.
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(PZT3_API_URL, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"ProjectZeroThree API error: {e}")
        return None

    lowest = None

    for region in data.get("regions", []):
        for p in region.get("prices", []):
            try:
                if p.get("state") != "VIC":
                    continue
                if p.get("type") != fuel_type:
                    continue

                price_val = float(p.get("price"))
            except (TypeError, ValueError):
                continue

            if lowest is None or price_val < lowest["price"]:
                lowest = {
                    "price": price_val,
                    "name": p.get("name"),
                    "suburb": p.get("suburb"),
                    "type": p.get("type"),
                    "postcode": p.get("postcode"),
                    "lat": p.get("lat"),
                    "lng": p.get("lng"),
                }

    return lowest

def generate_chart(cache):
    plt.figure(figsize=(8, 4))

    # Add "VIC Lowest" as a series in the chart
    station_names = ["Coles", "711 M3", "711 Westfield", "BP", "VIC Lowest"]
    date_keys = sorted(cache.keys())[-HISTORY_DAYS:]

    # Use integer x positions so we can thin out labels
    x_vals = list(range(len(date_keys)))

    for name in station_names:
        prices = [cache.get(day, {}).get(name, None) for day in date_keys]
        plt.plot(x_vals, prices, marker="o", label=name)

    # Show at most ~8 date labels on the x-axis
    if len(x_vals) > 0:
        step = max(1, len(x_vals) // 8)
        tick_idx = list(range(0, len(x_vals), step))
        plt.xticks(tick_idx, [date_keys[i] for i in tick_idx], rotation=45)

    plt.title("U98 Fuel Price Trend (Last 2 Weeks)")
    plt.ylabel("¢/L")
    plt.legend()
    plt.tight_layout()
    plt.savefig("trend.png")
    plt.close()

def send_email(content):
    sender_email = os.environ['EMAIL_SENDER']
    receiver_email = os.environ['EMAIL_RECEIVER']
    app_password = os.environ['EMAIL_APP_PASSWORD']

    msg = MIMEMultipart()
    msg['Subject'] = 'Daily U98 Fuel Prices - Wantirna South'
    msg['From'] = sender_email
    msg['To'] = receiver_email

    msg.attach(MIMEText(content, "plain"))

    with open("trend.png", "rb") as f:
        img = MIMEImage(f.read())
        img.add_header('Content-ID', '<chart>')
        msg.attach(img)

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(sender_email, app_password)
        smtp.send_message(msg)

if __name__ == "__main__":
    stations, cache = get_u98_prices()

    # Get VIC-wide lowest U98 and store in cache for today's date as "VIC Lowest"
    vic_lowest = get_vic_lowest_from_pzt3("U98")
    if vic_lowest:
        today_str = datetime.date.today().isoformat()
        if today_str not in cache:
            cache[today_str] = {}
        cache[today_str]["VIC Lowest"] = vic_lowest["price"]
        # Persist the updated cache
        cache = prune_cache(cache)
        save_cache(cache)

    # Now generate chart including VIC Lowest series
    generate_chart(cache)

    # Build email body
    if stations:
        body_lines = [
            "Prices of U98 fuel today (Wantirna South area):",
            "",
        ]
        body_lines += [
            f"{s['name']}: {s['price']} ¢/L"
            for s in stations
        ]
    else:
        body_lines = ["No matching U98 prices found today in Wantirna South."]

    if vic_lowest:
        body_lines += [
            "",
            "Cheapest U98 in VIC (ProjectZeroThree):",
            f"{vic_lowest['price']} ¢/L at {vic_lowest['name']} "
            f"({vic_lowest['suburb']} {vic_lowest.get('postcode', '')})"
        ]
    else:
        body_lines += [
            "",
            "Cheapest U98 in VIC (ProjectZeroThree): unavailable (API error or no VIC U98 entries)."
        ]

    body = "\n".join(body_lines)
    send_email(body)
