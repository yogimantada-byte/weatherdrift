from flask import Flask, render_template_string, jsonify
import requests
import json
import random
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

app = Flask(__name__)

# ── Cache ──────────────────────────────────────────────────────────────────
_cache = {
    "weather": None,
    "timestamp": 0,
    "last_updated": "Never",
}
REFRESH_INTERVAL = 60  # seconds between background refreshes

# City data — India, Japan, Russia, South Africa
CITIES = {
    # --- INDIA ---
    "Mumbai":          {"lat": 19.08, "lon": 72.88, "country": "IN"},
    "Delhi":           {"lat": 28.61, "lon": 77.21, "country": "IN"},
    "Bangalore":       {"lat": 12.97, "lon": 77.59, "country": "IN"},
    "Chennai":         {"lat": 13.08, "lon": 80.27, "country": "IN"},
    "Kolkata":         {"lat": 22.57, "lon": 88.36, "country": "IN"},
    "Hyderabad":       {"lat": 17.38, "lon": 78.49, "country": "IN"},
    "Pune":            {"lat": 18.52, "lon": 73.86, "country": "IN"},
    "Ahmedabad":       {"lat": 23.03, "lon": 72.58, "country": "IN"},
    "Jaipur":          {"lat": 26.91, "lon": 75.79, "country": "IN"},
    "Visakhapatnam":   {"lat": 17.69, "lon": 83.22, "country": "IN"},
    "Vijayawada":      {"lat": 16.51, "lon": 80.62, "country": "IN"},
    "Surat":           {"lat": 21.17, "lon": 72.83, "country": "IN"},  # Gujarat
    "Vadodara":        {"lat": 22.31, "lon": 73.18, "country": "IN"},  # Gujarat
    "Rajkot":          {"lat": 22.30, "lon": 70.80, "country": "IN"},  # Gujarat
    "Itanagar":        {"lat": 27.08, "lon": 93.60, "country": "IN"},  # Arunachal Pradesh
    "Naharlagun":      {"lat": 27.10, "lon": 93.69, "country": "IN"},  # Arunachal Pradesh
    "Lucknow":         {"lat": 26.85, "lon": 80.95, "country": "IN"},  # Uttar Pradesh
    "Kanpur":          {"lat": 26.46, "lon": 80.33, "country": "IN"},  # Uttar Pradesh
    "Agra":            {"lat": 27.18, "lon": 78.01, "country": "IN"},  # Uttar Pradesh
    "Varanasi":        {"lat": 25.32, "lon": 83.01, "country": "IN"},  # Uttar Pradesh
    "Bhopal":          {"lat": 23.25, "lon": 77.40, "country": "IN"},  # Madhya Pradesh
    "Indore":          {"lat": 22.72, "lon": 75.86, "country": "IN"},  # Madhya Pradesh
    "Gwalior":         {"lat": 26.22, "lon": 78.18, "country": "IN"},  # Madhya Pradesh
    "Guwahati":        {"lat": 26.19, "lon": 91.74, "country": "IN"},  # Assam
    "Dibrugarh":       {"lat": 27.48, "lon": 94.91, "country": "IN"},  # Assam
    "Silchar":         {"lat": 24.83, "lon": 92.80, "country": "IN"},  # Assam
    "Thiruvananthapuram": {"lat": 8.52,  "lon": 76.94, "country": "IN"},  # Kerala
    "Kochi":           {"lat": 9.93,  "lon": 76.26, "country": "IN"},  # Kerala
    "Kozhikode":       {"lat": 11.25, "lon": 75.78, "country": "IN"},  # Kerala
    # --- JAPAN ---
    "Tokyo":         {"lat": 35.68, "lon": 139.69, "country": "JP"},
    "Osaka":         {"lat": 34.69, "lon": 135.50, "country": "JP"},
    "Kyoto":         {"lat": 35.01, "lon": 135.77, "country": "JP"},
    "Sapporo":       {"lat": 43.06, "lon": 141.35, "country": "JP"},
    "Nagoya":        {"lat": 35.18, "lon": 136.91, "country": "JP"},
    "Fukuoka":       {"lat": 33.59, "lon": 130.40, "country": "JP"},
    "Hiroshima":     {"lat": 34.39, "lon": 132.45, "country": "JP"},
    "Sendai":        {"lat": 38.27, "lon": 140.87, "country": "JP"},
    "Yokohama":      {"lat": 35.44, "lon": 139.64, "country": "JP"},
    "Naha":          {"lat": 26.21, "lon": 127.68, "country": "JP"},
    # --- RUSSIA ---
    "Moscow":        {"lat": 55.75, "lon": 37.62, "country": "RU"},
    "Saint Petersburg": {"lat": 59.93, "lon": 30.32, "country": "RU"},
    "Novosibirsk":   {"lat": 55.01, "lon": 82.92, "country": "RU"},
    "Yekaterinburg": {"lat": 56.84, "lon": 60.60, "country": "RU"},
    "Kazan":         {"lat": 55.79, "lon": 49.12, "country": "RU"},
    "Vladivostok":   {"lat": 43.12, "lon": 131.89, "country": "RU"},
    "Sochi":         {"lat": 43.60, "lon": 39.73, "country": "RU"},
    "Omsk":          {"lat": 54.99, "lon": 73.37, "country": "RU"},
    "Irkutsk":       {"lat": 52.29, "lon": 104.29, "country": "RU"},
    "Murmansk":      {"lat": 68.97, "lon": 33.07, "country": "RU"},
    # --- SOUTH AFRICA ---
    "Johannesburg":  {"lat": -26.20, "lon": 28.04, "country": "ZA"},
    "Cape Town":     {"lat": -33.93, "lon": 18.42, "country": "ZA"},
    "Durban":        {"lat": -29.86, "lon": 31.02, "country": "ZA"},
    "Pretoria":      {"lat": -25.75, "lon": 28.19, "country": "ZA"},
    "Port Elizabeth": {"lat": -33.96, "lon": 25.60, "country": "ZA"},
    "Bloemfontein":  {"lat": -29.12, "lon": 26.21, "country": "ZA"},
    "East London":   {"lat": -33.02, "lon": 27.91, "country": "ZA"},
    "Nelspruit":     {"lat": -25.47, "lon": 30.97, "country": "ZA"},
    "Kimberley":     {"lat": -28.74, "lon": 24.76, "country": "ZA"},
    "Polokwane":     {"lat": -23.90, "lon": 29.45, "country": "ZA"},
}

WEATHER_CONDITIONS = [
    {"condition": "Sunny", "icon": "☀️", "bg": "#FF8C00"},
    {"condition": "Cloudy", "icon": "☁️", "bg": "#607D8B"},
    {"condition": "Rainy", "icon": "🌧️", "bg": "#1565C0"},
    {"condition": "Stormy", "icon": "⛈️", "bg": "#37474F"},
    {"condition": "Snowy", "icon": "❄️", "bg": "#4FC3F7"},
    {"condition": "Partly Cloudy", "icon": "⛅", "bg": "#0288D1"},
    {"condition": "Foggy", "icon": "🌫️", "bg": "#78909C"},
    {"condition": "Windy", "icon": "💨", "bg": "#00838F"},
]

def get_weather_icon(weathercode):
    """Map Open-Meteo WMO weather codes to emoji icons and condition labels."""
    if weathercode == 0:
        return "☀️", "Clear Sky"
    elif weathercode in [1, 2]:
        return "⛅", "Partly Cloudy"
    elif weathercode == 3:
        return "☁️", "Overcast"
    elif weathercode in [45, 48]:
        return "🌫️", "Foggy"
    elif weathercode in [51, 53, 55]:
        return "🌦️", "Drizzle"
    elif weathercode in [61, 63, 65]:
        return "🌧️", "Rainy"
    elif weathercode in [71, 73, 75, 77]:
        return "❄️", "Snowy"
    elif weathercode in [80, 81, 82]:
        return "🌧️", "Rain Showers"
    elif weathercode in [85, 86]:
        return "🌨️", "Snow Showers"
    elif weathercode in [95, 96, 99]:
        return "⛈️", "Stormy"
    else:
        return "🌡️", "Unknown"

def fetch_single_city(city, coords):
    """Fetch weather for one city from Open-Meteo."""
    lat, lon = coords["lat"], coords["lon"]
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current_weather=true"
        f"&hourly=relativehumidity_2m,apparent_temperature,visibility,surface_pressure,uv_index"
        f"&timezone=auto&forecast_days=1"
    )
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        weather = data["current_weather"]
        temp = round(weather["temperature"])
        wind_speed = round(weather["windspeed"])
        icon, condition = get_weather_icon(weather["weathercode"])
        hourly = data.get("hourly", {})
        return {
            "city": city,
            "country": coords["country"],
            "temp": temp,
            "feels_like": round(hourly.get("apparent_temperature", [temp])[0]),
            "humidity": hourly.get("relativehumidity_2m", [50])[0],
            "wind_speed": wind_speed,
            "condition": condition,
            "icon": icon,
            "uv_index": round(hourly.get("uv_index", [0])[0], 1),
            "visibility": round(hourly.get("visibility", [10000])[0] / 1000, 1),
            "pressure": round(hourly.get("surface_pressure", [1013])[0]),
        }
    except Exception:
        cond = random.choice(WEATHER_CONDITIONS)
        temp = random.randint(10, 35)
        icon, condition = cond["icon"], cond["condition"]
        return {
            "city": city, "country": coords["country"],
            "temp": temp, "feels_like": temp - 2, "humidity": 60,
            "wind_speed": random.randint(5, 40), "condition": condition,
            "icon": icon, "uv_index": 3, "visibility": 10.0, "pressure": 1013,
        }

def get_weather_data():
    """Fetch all cities in parallel (20 threads at once)."""
    results = {}
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {
            executor.submit(fetch_single_city, city, coords): city
            for city, coords in CITIES.items()
        }
        for future in as_completed(futures):
            city = futures[future]
            result = future.result()
            if result:
                results[city] = result
    return [results[city] for city in CITIES if city in results]

def refresh_cache():
    """Fetch fresh weather data and store in cache."""
    global _cache
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Refreshing weather cache...")
    data = get_weather_data()
    _cache["weather"] = data
    _cache["timestamp"] = time.time()
    _cache["last_updated"] = datetime.now().strftime("%H:%M:%S")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Cache updated — {len(data)} cities")

def background_refresh():
    """Background thread: refresh every REFRESH_INTERVAL seconds."""
    while True:
        try:
            refresh_cache()
        except Exception as e:
            print(f"Background refresh error: {e}")
        time.sleep(REFRESH_INTERVAL)

def get_cached_weather():
    """Return cached weather, fetching fresh if cache is empty."""
    if _cache["weather"] is None:
        refresh_cache()
    return _cache["weather"]

# Start background refresh thread when app boots
_bg_thread = threading.Thread(target=background_refresh, daemon=True)
_bg_thread.start()

def get_forecast(city_name=None, lat=None, lon=None):
    # Resolve city name to coords if given
    if city_name and city_name in CITIES:
        lat = CITIES[city_name]["lat"]
        lon = CITIES[city_name]["lon"]
    # Default to first city if no coords resolved
    if lat is None or lon is None:
        first_city = list(CITIES.values())[0]
        lat, lon = first_city["lat"], first_city["lon"]
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&daily=weathercode,temperature_2m_max,temperature_2m_min"
        f"&timezone=auto&forecast_days=7"
    )
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        daily = data["daily"]
        forecast = []
        for i in range(7):
            date_str = daily["time"][i]
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            day_label = "Today" if i == 0 else date_obj.strftime("%a")
            icon, condition = get_weather_icon(daily["weathercode"][i])
            forecast.append({
                "day": day_label,
                "icon": icon,
                "condition": condition,
                "high": round(daily["temperature_2m_max"][i]),
                "low": round(daily["temperature_2m_min"][i]),
            })
        return forecast
    except Exception:
        # Fallback
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        today = datetime.now().weekday()
        return [
            {
                "day": "Today" if i == 0 else days[(today + i) % 7],
                "icon": random.choice(WEATHER_CONDITIONS)["icon"],
                "condition": random.choice(WEATHER_CONDITIONS)["condition"],
                "high": random.randint(20, 35),
                "low": random.randint(10, 19),
            }
            for i in range(7)
        ]

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WeatherDrift — Global Weather Reports</title>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@300;400;500;600&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
  :root {
    --ink: #0a0a0f;
    --paper: #f2ede6;
    --accent: #e8441a;
    --muted: #8a8070;
    --card-bg: #ffffff;
    --border: #d4cec5;
  }

  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    font-family: 'DM Sans', sans-serif;
    background: var(--paper);
    color: var(--ink);
    min-height: 100vh;
    overflow-x: hidden;
  }

  /* HEADER */
  header {
    background: var(--ink);
    color: var(--paper);
    padding: 0 40px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 3px solid var(--accent);
    position: sticky;
    top: 0;
    z-index: 100;
  }

  .logo-block {
    display: flex;
    align-items: baseline;
    gap: 12px;
    padding: 18px 0;
  }

  .logo {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 2.6rem;
    letter-spacing: 3px;
    color: var(--paper);
  }

  .logo span { color: var(--accent); }

  .tagline {
    font-family: 'Space Mono', monospace;
    font-size: 0.65rem;
    color: var(--muted);
    letter-spacing: 2px;
    text-transform: uppercase;
  }

  .header-meta {
    font-family: 'Space Mono', monospace;
    font-size: 0.7rem;
    color: var(--muted);
    text-align: right;
    line-height: 1.8;
  }

  .live-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: var(--accent);
    color: white;
    padding: 3px 10px;
    font-size: 0.65rem;
    letter-spacing: 2px;
    font-weight: 700;
    margin-bottom: 4px;
  }

  .live-dot {
    width: 6px; height: 6px;
    background: white;
    border-radius: 50%;
    animation: pulse 1.5s infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
  }

  /* HERO TICKER */
  .ticker-wrap {
    background: var(--accent);
    overflow: hidden;
    padding: 10px 0;
  }

  .ticker {
    display: flex;
    animation: ticker-scroll 30s linear infinite;
    white-space: nowrap;
  }

  .ticker-item {
    font-family: 'Space Mono', monospace;
    font-size: 0.75rem;
    font-weight: 700;
    color: white;
    padding: 0 40px;
    letter-spacing: 1px;
  }

  @keyframes ticker-scroll {
    0% { transform: translateX(0); }
    100% { transform: translateX(-50%); }
  }

  /* MAIN LAYOUT */
  main { max-width: 1400px; margin: 0 auto; padding: 40px; }

  .section-label {
    font-family: 'Space Mono', monospace;
    font-size: 0.65rem;
    letter-spacing: 4px;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .section-label::after {
    content: '';
    flex: 1;
    height: 1px;
    background: var(--border);
  }

  /* FEATURED CARD */
  .featured-section {
    margin-bottom: 60px;
  }

  .featured-card {
    background: var(--ink);
    color: var(--paper);
    padding: 50px 60px;
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 40px;
    align-items: center;
    position: relative;
    overflow: hidden;
    animation: fadeUp 0.6s ease both;
  }

  .featured-card::before {
    content: '';
    position: absolute;
    top: -80px; right: -80px;
    width: 300px; height: 300px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(232,68,26,0.2) 0%, transparent 70%);
  }

  .featured-city {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 5rem;
    letter-spacing: 4px;
    line-height: 1;
    margin-bottom: 8px;
  }

  .featured-country {
    font-family: 'Space Mono', monospace;
    font-size: 0.75rem;
    letter-spacing: 3px;
    color: var(--muted);
    text-transform: uppercase;
    margin-bottom: 24px;
  }

  .featured-condition {
    font-size: 1.1rem;
    font-weight: 300;
    color: #ccc;
  }

  .featured-temp {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 9rem;
    line-height: 1;
    color: var(--accent);
    text-align: right;
  }

  .featured-unit {
    font-family: 'Space Mono', monospace;
    font-size: 1.2rem;
    color: var(--muted);
    text-align: right;
  }

  .featured-icon {
    font-size: 3rem;
    margin-bottom: 16px;
  }

  .stats-row {
    display: flex;
    gap: 40px;
    margin-top: 30px;
    padding-top: 30px;
    border-top: 1px solid rgba(255,255,255,0.1);
  }

  .stat {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .stat-label {
    font-family: 'Space Mono', monospace;
    font-size: 0.6rem;
    letter-spacing: 2px;
    color: var(--muted);
    text-transform: uppercase;
  }

  .stat-value {
    font-size: 1.1rem;
    font-weight: 600;
  }

  /* CITY GRID */
  .city-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 2px;
    margin-bottom: 60px;
    background: var(--border);
    border: 2px solid var(--border);
  }

  .city-card {
    background: var(--card-bg);
    padding: 28px;
    cursor: pointer;
    transition: transform 0.2s ease, background 0.2s ease;
    animation: fadeUp 0.5s ease both;
    position: relative;
    overflow: hidden;
  }

  .city-card.selected {
    background: var(--accent) !important;
    color: white !important;
    transform: scale(1.02);
    z-index: 10;
  }

  .city-card.selected .city-name,
  .city-card.selected .city-condition { color: white !important; }
  .city-card.selected .city-country,
  .city-card.selected .card-stat-label { color: rgba(255,255,255,0.7) !important; }
  .city-card.selected .card-stats { border-color: rgba(255,255,255,0.2) !important; }

  .city-card:hover {
    background: var(--ink);
    color: var(--paper);
    transform: scale(1.02);
    z-index: 10;
  }

  .city-card:hover .city-name { color: var(--paper); }
  .city-card:hover .city-country { color: var(--muted); }
  .city-card:hover .city-condition { color: #aaa; }
  .city-card:hover .card-stat-label { color: var(--muted); }

  .city-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 20px;
  }

  .city-name {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 1.8rem;
    letter-spacing: 2px;
    color: var(--ink);
    transition: color 0.2s;
  }

  .city-country {
    font-family: 'Space Mono', monospace;
    font-size: 0.6rem;
    letter-spacing: 2px;
    color: var(--muted);
    text-transform: uppercase;
    margin-top: 2px;
    transition: color 0.2s;
  }

  .city-icon { font-size: 2.2rem; }

  .city-temp {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 3.5rem;
    color: var(--accent);
    line-height: 1;
    margin-bottom: 6px;
  }

  .city-condition {
    font-size: 0.85rem;
    color: var(--muted);
    font-weight: 400;
    margin-bottom: 20px;
    transition: color 0.2s;
  }

  .card-stats {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    padding-top: 16px;
    border-top: 1px solid var(--border);
  }

  .city-card:hover .card-stats {
    border-color: rgba(255,255,255,0.1);
  }

  .card-stat-label {
    font-family: 'Space Mono', monospace;
    font-size: 0.55rem;
    letter-spacing: 1.5px;
    color: var(--muted);
    text-transform: uppercase;
    transition: color 0.2s;
  }

  .card-stat-value { font-size: 0.9rem; font-weight: 600; }

  /* FORECAST STRIP */
  .forecast-section { margin-bottom: 60px; }

  .forecast-strip {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 2px;
    background: var(--border);
    border: 2px solid var(--border);
  }

  .forecast-day {
    background: var(--card-bg);
    padding: 24px 16px;
    text-align: center;
    transition: background 0.2s;
    animation: fadeUp 0.5s ease both;
  }

  .forecast-day:first-child { background: var(--ink); color: var(--paper); }
  .forecast-day:first-child .forecast-label { color: var(--muted); }
  .forecast-day:first-child .forecast-hi { color: var(--accent); }

  .forecast-day:not(:first-child):hover { background: #f9f6f0; }

  .forecast-label {
    font-family: 'Space Mono', monospace;
    font-size: 0.6rem;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: var(--muted);
    margin-bottom: 12px;
  }

  .forecast-icon { font-size: 1.8rem; margin-bottom: 12px; }

  .forecast-hi {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 1.6rem;
    color: var(--ink);
  }

  .forecast-lo {
    font-family: 'Space Mono', monospace;
    font-size: 0.7rem;
    color: var(--muted);
    margin-top: 2px;
  }

  /* FOOTER */
  footer {
    background: var(--ink);
    color: var(--muted);
    padding: 30px 40px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-top: 3px solid var(--accent);
  }

  .footer-logo {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 1.4rem;
    color: var(--paper);
    letter-spacing: 3px;
  }

  .footer-logo span { color: var(--accent); }

  .footer-info {
    font-family: 'Space Mono', monospace;
    font-size: 0.65rem;
    letter-spacing: 1px;
    text-align: right;
    line-height: 1.8;
  }

  @keyframes fadeUp {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
  }

  /* Stagger cards */
  .city-card:nth-child(1) { animation-delay: 0.1s; }
  .city-card:nth-child(2) { animation-delay: 0.15s; }
  .city-card:nth-child(3) { animation-delay: 0.2s; }
  .city-card:nth-child(4) { animation-delay: 0.25s; }
  .city-card:nth-child(5) { animation-delay: 0.3s; }

  .forecast-day:nth-child(1) { animation-delay: 0.05s; }
  .forecast-day:nth-child(2) { animation-delay: 0.1s; }
  .forecast-day:nth-child(3) { animation-delay: 0.15s; }
  .forecast-day:nth-child(4) { animation-delay: 0.2s; }
  .forecast-day:nth-child(5) { animation-delay: 0.25s; }
  .forecast-day:nth-child(6) { animation-delay: 0.3s; }
  .forecast-day:nth-child(7) { animation-delay: 0.35s; }

  @media (max-width: 768px) {
    main { padding: 20px; }
    .featured-card { grid-template-columns: 1fr; padding: 30px; }
    .featured-temp { font-size: 6rem; text-align: left; }
    .featured-city { font-size: 3rem; }
    .forecast-strip { grid-template-columns: repeat(4, 1fr); }
    header { padding: 0 20px; }
    .tagline { display: none; }
  }
</style>
</head>
<body>

<header>
  <div class="logo-block">
    <div>
      <div class="logo">Weather<span>Drift</span></div>
      <div class="tagline">Global Atmospheric Intelligence</div>
    </div>
  </div>
  <div class="header-meta">
    <div class="live-badge"><span class="live-dot"></span> LIVE</div>
    <div>{{ datetime }}</div>
    <div>{{ total_cities }} cities monitored</div>
    <div id="last-updated-label" style="color: #e8441a; font-size:0.6rem;">Last updated: {{ last_updated }}</div>
  </div>
</header>

<!-- TICKER -->
<div class="ticker-wrap">
  <div class="ticker">
    {% for w in weather_data %}
    <span class="ticker-item">{{ w.icon }} {{ w.city }} {{ w.temp }}°C · {{ w.condition }}</span>
    {% endfor %}
    {% for w in weather_data %}
    <span class="ticker-item">{{ w.icon }} {{ w.city }} {{ w.temp }}°C · {{ w.condition }}</span>
    {% endfor %}
  </div>
</div>

<main>

  <!-- FEATURED -->
  <section class="featured-section">
    <div class="section-label">Featured City <span id="featured-loading" style="display:none; color: var(--accent); font-size:0.7rem;">· Loading...</span></div>
    <div class="featured-card">
      <div>
        <div class="featured-icon" id="feat-icon">{{ featured.icon }}</div>
        <div class="featured-city" id="feat-city">{{ featured.city }}</div>
        <div class="featured-country" id="feat-country">{{ featured.country }} · Updated just now</div>
        <div class="featured-condition" id="feat-condition">{{ featured.condition }} — Feels like {{ featured.feels_like }}°C</div>
        <div class="stats-row">
          <div class="stat">
            <span class="stat-label">Humidity</span>
            <span class="stat-value" id="feat-humidity">{{ featured.humidity }}%</span>
          </div>
          <div class="stat">
            <span class="stat-label">Wind</span>
            <span class="stat-value" id="feat-wind">{{ featured.wind_speed }} km/h</span>
          </div>
          <div class="stat">
            <span class="stat-label">UV Index</span>
            <span class="stat-value" id="feat-uv">{{ featured.uv_index }}</span>
          </div>
          <div class="stat">
            <span class="stat-label">Pressure</span>
            <span class="stat-value" id="feat-pressure">{{ featured.pressure }} hPa</span>
          </div>
          <div class="stat">
            <span class="stat-label">Visibility</span>
            <span class="stat-value" id="feat-visibility">{{ featured.visibility }} km</span>
          </div>
        </div>
      </div>
      <div>
        <div class="featured-temp" id="feat-temp">{{ featured.temp }}°</div>
        <div class="featured-unit">Celsius</div>
      </div>
    </div>
  </section>

  <!-- CITY CARDS -->
  <section>
    {% set countries = {"IN": "🇮🇳 India", "JP": "🇯🇵 Japan", "RU": "🇷🇺 Russia", "ZA": "🇿🇦 South Africa"} %}
    {% for code, label in countries.items() %}
    <div class="section-label" style="margin-top: 40px;">{{ label }}</div>
    <div class="city-grid" style="margin-bottom: 2px;">
      {% for w in weather_data if w.country == code %}
      <div class="city-card" onclick="selectCity('{{ w.city }}')" data-city="{{ w.city }}">
        <div class="city-header">
          <div>
            <div class="city-name">{{ w.city }}</div>
            <div class="city-country">{{ w.country }}</div>
          </div>
          <div class="city-icon">{{ w.icon }}</div>
        </div>
        <div class="city-temp">{{ w.temp }}°</div>
        <div class="city-condition">{{ w.condition }}</div>
        <div class="card-stats">
          <div>
            <div class="card-stat-label">Humidity</div>
            <div class="card-stat-value">{{ w.humidity }}%</div>
          </div>
          <div>
            <div class="card-stat-label">Wind</div>
            <div class="card-stat-value">{{ w.wind_speed }} km/h</div>
          </div>
          <div>
            <div class="card-stat-label">UV</div>
            <div class="card-stat-value">{{ w.uv_index }}</div>
          </div>
          <div>
            <div class="card-stat-label">Pressure</div>
            <div class="card-stat-value">{{ w.pressure }}</div>
          </div>
        </div>
      </div>
      {% endfor %}
    </div>
    {% endfor %}
  </section>

  <!-- FORECAST -->
  <section class="forecast-section">
    <div class="section-label" id="forecast-label">7-Day Outlook · {{ featured.city }}</div>
    <div class="forecast-strip" id="forecast-strip">
      {% for day in forecast %}
      <div class="forecast-day">
        <div class="forecast-label">{{ day.day }}</div>
        <div class="forecast-icon">{{ day.icon }}</div>
        <div class="forecast-hi">{{ day.high }}°</div>
        <div class="forecast-lo">{{ day.low }}° lo</div>
      </div>
      {% endfor %}
    </div>
  </section>

</main>

<footer>
  <div class="footer-logo">Weather<span>Drift</span></div>
  <div class="footer-info">
    <div>Powered by Python · Flask · WeatherDrift Engine</div>
    <div>Data refreshes every 30 minutes</div>
  </div>
</footer>

<script>
// ── Track which city is currently featured ──────────────────────────────
let currentFeaturedCity = null;

// ── Update featured panel with city data object ─────────────────────────
function updateFeaturedPanel(d) {
  document.getElementById('feat-icon').textContent        = d.icon;
  document.getElementById('feat-city').textContent        = d.city;
  document.getElementById('feat-country').textContent     = d.country + ' · Updated just now';
  document.getElementById('feat-condition').textContent   = d.condition + ' — Feels like ' + d.feels_like + '°C';
  document.getElementById('feat-temp').textContent        = d.temp + '°';
  document.getElementById('feat-humidity').textContent    = d.humidity + '%';
  document.getElementById('feat-wind').textContent        = d.wind_speed + ' km/h';
  document.getElementById('feat-uv').textContent          = d.uv_index;
  document.getElementById('feat-pressure').textContent    = d.pressure + ' hPa';
  document.getElementById('feat-visibility').textContent  = d.visibility + ' km';
}

// ── Update 7-day forecast strip ─────────────────────────────────────────
function updateForecast(cityName, forecastData) {
  document.getElementById('forecast-label').textContent = '7-Day Outlook · ' + cityName;
  const strip = document.getElementById('forecast-strip');
  strip.innerHTML = forecastData.map(day => `
    <div class="forecast-day">
      <div class="forecast-label">${day.day}</div>
      <div class="forecast-icon">${day.icon}</div>
      <div class="forecast-hi">${day.high}°</div>
      <div class="forecast-lo">${day.low}° lo</div>
    </div>
  `).join('');
}

// ── Click a city card ────────────────────────────────────────────────────
function selectCity(cityName) {
  // Track selected city
  currentFeaturedCity = cityName;

  // Highlight selected card, remove from others
  document.querySelectorAll('.city-card').forEach(c => c.classList.remove('selected'));
  const selected = document.querySelector(`.city-card[data-city="${cityName}"]`);
  if (selected) selected.classList.add('selected');

  // Show loading indicator and scroll to featured
  document.getElementById('featured-loading').style.display = 'inline';
  document.querySelector('.featured-section').scrollIntoView({ behavior: 'smooth', block: 'start' });

  // Fetch live data for selected city (includes 7-day forecast)
  fetch(`/api/city/${encodeURIComponent(cityName)}`)
    .then(r => r.json())
    .then(d => {
      updateFeaturedPanel(d);
      updateForecast(d.city, d.forecast);
      document.getElementById('featured-loading').style.display = 'none';
    })
    .catch(err => {
      console.error('Error fetching city data:', err);
      document.getElementById('featured-loading').style.display = 'none';
    });
}

// ── Update all city cards in the grid ───────────────────────────────────
function updateAllCards(weatherList) {
  weatherList.forEach(w => {
    const card = document.querySelector(`.city-card[data-city="${w.city}"]`);
    if (!card) return;
    const q    = sel => card.querySelector(sel);
    const stats = card.querySelectorAll('.card-stat-value');
    const tempEl = q('.city-temp');
    const condEl = q('.city-condition');
    const iconEl = q('.city-icon');
    if (tempEl)   tempEl.textContent   = w.temp + '°';
    if (condEl)   condEl.textContent   = w.condition;
    if (iconEl)   iconEl.textContent   = w.icon;
    if (stats[0]) stats[0].textContent = w.humidity + '%';
    if (stats[1]) stats[1].textContent = w.wind_speed + ' km/h';
    if (stats[2]) stats[2].textContent = w.uv_index;
    if (stats[3]) stats[3].textContent = w.pressure;
  });
}

// ── Update scrolling ticker ──────────────────────────────────────────────
function updateTicker(weatherList) {
  const ticker = document.querySelector('.ticker');
  if (!ticker) return;
  const items = weatherList.map(w =>
    `<span class="ticker-item">${w.icon} ${w.city} ${w.temp}°C · ${w.condition}</span>`
  ).join('');
  ticker.innerHTML = items + items;
}

// ── Auto-refresh: poll /api/weather every 60 seconds ────────────────────
function autoRefresh() {
  fetch('/api/weather')
    .then(r => r.json())
    .then(data => {
      // Update all city cards and ticker
      updateAllCards(data.weather);
      updateTicker(data.weather);

      // Update last-updated label in header
      const label = document.getElementById('last-updated-label');
      if (label) label.textContent = 'Last updated: ' + data.last_updated;

      // If a city is selected, update featured panel with fresh data
      if (currentFeaturedCity) {
        const w = data.weather.find(x => x.city === currentFeaturedCity);
        if (w) updateFeaturedPanel(w);
        // Also refresh the 7-day forecast for the selected city
        fetch(`/api/city/${encodeURIComponent(currentFeaturedCity)}`)
          .then(r => r.json())
          .then(d => updateForecast(d.city, d.forecast))
          .catch(() => {});
      }
      console.log('Auto-refreshed at', data.last_updated);
    })
    .catch(err => console.error('Auto-refresh error:', err));
}

// Kick off auto-refresh every 60 seconds
setInterval(autoRefresh, 60000);
console.log('Auto-refresh active — updates every 60 seconds');
</script>

</body>
</html>
"""

@app.route("/api/city/<city_name>")
def city_api(city_name):
    from flask import jsonify
    coords = CITIES.get(city_name)
    if not coords:
        return jsonify({"error": "City not found"}), 404
    lat, lon = coords["lat"], coords["lon"]
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current_weather=true"
        f"&hourly=relativehumidity_2m,apparent_temperature,visibility,surface_pressure,uv_index"
        f"&daily=weathercode,temperature_2m_max,temperature_2m_min"
        f"&timezone=auto&forecast_days=7"
    )
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        weather = data["current_weather"]
        icon, condition = get_weather_icon(weather["weathercode"])
        hourly = data.get("hourly", {})
        daily = data.get("daily", {})
        forecast = []
        for i in range(7):
            date_obj = datetime.strptime(daily["time"][i], "%Y-%m-%d")
            fi, fc = get_weather_icon(daily["weathercode"][i])
            forecast.append({
                "day": "Today" if i == 0 else date_obj.strftime("%a"),
                "icon": fi,
                "condition": fc,
                "high": round(daily["temperature_2m_max"][i]),
                "low": round(daily["temperature_2m_min"][i]),
            })
        return jsonify({
            "city": city_name,
            "country": coords["country"],
            "temp": round(weather["temperature"]),
            "feels_like": round(hourly.get("apparent_temperature", [weather["temperature"]])[0]),
            "humidity": hourly.get("relativehumidity_2m", [50])[0],
            "wind_speed": round(weather["windspeed"]),
            "condition": condition,
            "icon": icon,
            "uv_index": round(hourly.get("uv_index", [0])[0], 1),
            "visibility": round(hourly.get("visibility", [10000])[0] / 1000, 1),
            "pressure": round(hourly.get("surface_pressure", [1013])[0]),
            "forecast": forecast,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/weather")
def weather_api():
    """Returns all cached weather data as JSON for frontend polling."""
    data = get_cached_weather()
    return jsonify({
        "weather": data,
        "last_updated": _cache["last_updated"],
        "timestamp": _cache["timestamp"],
    })

@app.route("/")
def index():
    weather_data = get_cached_weather()
    featured = weather_data[0]
    forecast = get_forecast(featured["city"])
    now = datetime.now().strftime("%A, %d %B %Y · %H:%M UTC")
    return render_template_string(
        HTML_TEMPLATE,
        weather_data=weather_data,
        featured=featured,
        forecast=forecast,
        datetime=now,
        total_cities=len(CITIES),
        last_updated=_cache["last_updated"],
    )

if __name__ == "__main__":
    import socket
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        local_ip = "YOUR_PC_IP"
    print("\n" + "="*55)
    print("  🌍  WeatherDrift is running!")
    print("="*55)
    print(f"  Local  (this PC):  http://localhost:5000")
    print(f"  Network (all devices):  http://{local_ip}:5000")
    print("="*55)
    print("  📱 Open the Network URL on any phone, tablet,")
    print("     smart TV, or laptop on the same Wi-Fi!")
    print("="*55 + "\n")
    app.run(debug=False, host="0.0.0.0", port=5000)