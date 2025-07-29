# daily_fuel_email.py
import smtplib
import requests
from email.mime.text import MIMEText
import os

# 1. Scrape real-time fuel prices for Wantirna South from PetrolSpy

def get_u98_prices():
    # Coordinates for Wantirna South bounding box
    params = {
        "neLat": -37.85, "neLng": 145.26,
        "swLat": -37.90, "swLng": 145.18,
    }

    url = "https://petrolspy.com.au/webservice-1/station/box"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        print(f"Total stations fetched: {len(data.get('stations', []))}")
    except Exception as e:
        print(f"Exception: {str(e)}")
        return [{"brand": "Error", "name": "PetrolSpy fetch failed", "suburb": str(e), "price": 0.0}]

    stations = []
    for station in data.get("stations", []):
        brand = station.get("brand", "").strip()
        price = station.get("price")
        fuel_type = station.get("fuelType", "")
        name = station.get("name", "")
        suburb = station.get("suburb", "")

        print(brand, fuel_type, price)  # Debugging line

        if (
            brand in ['7-Eleven', 'BP', 'Coles Express']
            and "98" in fuel_type.upper()
            and price is not None
        ):
            stations.append({
                "brand": brand,
                "name": name,
                "suburb": suburb,
                "price": float(price),
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
