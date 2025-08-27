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
HISTORY_DAYS = 14

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
    return {day: data for day, data in cache.items() if datetime.date.fromisoformat(day) >= cutoff}

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
                stations.append({
                    "brand": brand,
                    "name": display_name,
                    "price": float(amount),
                })
                cache[today_str][display_name] = float(amount)

    save_cache(cache)
    stations = sorted(stations, key=lambda x: x['price'])
    return stations, cache

def generate_chart(cache):
    plt.figure(figsize=(8, 4))
    station_names = ["Coles", "711 M3", "711 Westfield", "BP"]
    date_keys = sorted(cache.keys())[-HISTORY_DAYS:]

    for name in station_names:
        prices = [cache.get(day, {}).get(name, None) for day in date_keys]
        plt.plot(date_keys, prices, marker="o", label=name)

    plt.xticks(rotation=45)
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
    generate_chart(cache)

    if stations:
        body = "Prices of U98 fuel today:\n\n" + "\n".join(
            [f"{s['name']}: {s['price']} ¢/L" for s in stations]
        )
    else:
        body = "No matching U98 prices found today."

    send_email(body)
