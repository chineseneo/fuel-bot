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

# 1. Scrape real-time fuel prices for Wantirna South from PetrolSpy

CACHE_FILE = "fuel_cache.json"
HISTORY_DAYS = 14

def get_cached_data():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_cache(data):
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f)

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
        return [{"brand": "Error", "name": "PetrolSpy fetch failed", "suburb": str(e), "price": 0.0, "address": ""}]

    target_stations = [
        "Coles Express Wantirna South",
        "7-Eleven Wantirna South",
        "BP Wantirna South"
    ]

    stations = []
    today_str = datetime.date.today().isoformat()
    cache = get_cached_data()
    if today_str not in cache:
        cache[today_str] = {}

    for station in data.get("message").get("list", []):
        name = station.get("name", "")
        brand = station.get("brand", "").strip()
        suburb = station.get("suburb", "")
        address = station.get("address", "")

        if name in target_stations and "U98" in station.get("prices", {}):
            amount = station["prices"]["U98"].get("amount")
            if amount:
                stations.append({
                    "brand": brand,
                    "name": name,
                    "suburb": suburb,
                    "address": address,
                    "price": float(amount),
                })
                cache[today_str][name] = float(amount)

    save_cache(cache)
    stations = sorted(stations, key=lambda x: x['price'])
    return stations, cache

def generate_chart(cache):
    plt.figure(figsize=(8, 4))
    station_names = [
        "Coles Express Wantirna South",
        "7-Eleven Wantirna South",
        "BP Wantirna South"
    ]
    date_keys = sorted(cache.keys())[-HISTORY_DAYS:]

    for name in station_names:
        prices = [cache.get(day, {}).get(name, None) for day in date_keys]
        print(f"plt.plot(data_keys: {data_keys}, prices: {prices}, label: {name})")
        plt.plot(date_keys, prices, label=name)

    plt.xticks(rotation=45)
    plt.title("U98 Fuel Price Trend (Last 2 Weeks)")
    plt.ylabel("¢/L")
    plt.legend()
    plt.tight_layout()
    plt.savefig("trend.png")
    plt.close()

# 2. Send email

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

# 3. Compose and send message

if __name__ == "__main__":
    stations, cache = get_u98_prices()
    generate_chart(cache)

    if stations:
        body = "Prices of U98 fuel for selected stations in Wantirna South today:\n\n" + "\n".join(
            [f"{s['brand']} - {s['name']}, {s['address']} ({s['suburb']}): {s['price']} ¢/L" for s in stations]
        )
    else:
        body = "No matching U98 prices found today."

    send_email(body)
