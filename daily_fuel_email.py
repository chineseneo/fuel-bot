# daily_fuel_email.py
import smtplib
import requests
from email.mime.text import MIMEText
import os

# 1. Scrape real-time fuel prices for Wantirna South from PetrolSpy

def get_u98_prices():
    # Coordinates for Wantirna South bounding box
    params = {
        "neLat": -37.85, "neLng": 145.27,
        "swLat": -37.88, "swLng": 145.2,
    }

    url = "https://petrolspy.com.au/webservice-1/station/box"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        print(f"response.json(): {data}")
        print(f"Total stations fetched: {len(data.get('message').get('list', []))}")
    except Exception as e:
        print(f"Exception: {str(e)}")
        return [{"brand": "Error", "name": "PetrolSpy fetch failed", "suburb": str(e), "price": 0.0}]

    stations = []
    for station in data.get("message").get("list", []):
        name = station.get("name", "")
        brand = station.get("brand", "").strip()
        suburb = station.get("suburb", "")

        # Debug: Print station name and prices
        print(f"Checking station: {name} ({brand})")
        for ftype, fdata in station.get("prices", {}).items():
            print(f"  Fuel type: {ftype}, Price: {fdata.get('amount')}")

        if name in target_stations and "U98" in station.get("prices", {}):
            amount = station["prices"]["U98"].get("amount")
            if amount:
                stations.append({
                    "brand": brand,
                    "name": name,
                    "suburb": suburb,
                    "price": float(amount),
                })

    stations = sorted(stations, key=lambda x: x['price'])
    return stations

# 2. Send email

def send_email(content):
    sender_email = os.environ['EMAIL_SENDER']
    receiver_email = os.environ['EMAIL_RECEIVER']
    app_password = os.environ['EMAIL_APP_PASSWORD']

    msg = MIMEText(content)
    msg['Subject'] = 'Daily U98 Fuel Prices - Wantirna South'
    msg['From'] = sender_email
    msg['To'] = receiver_email

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(sender_email, app_password)
        smtp.send_message(msg)

# 3. Compose and send message

if __name__ == "__main__":
    stations = get_u98_prices()
    if stations:
        body = "Cheapest U98 in Wantirna South today:\n\n" + "\n".join(
            [f"{s['brand']} - {s['name']} ({s['suburb']}): {s['price']} ¢/L" for s in stations]
        )
    else:
        body = "No matching U98 prices found today."

    send_email(body)
