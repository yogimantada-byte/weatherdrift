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
    """Fetch weather for one city from Open-Meteo with retry."""
    lat, lon = coords["lat"], coords["lon"]
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current_weather=true"
        f"&hourly=relativehumidity_2m,apparent_temperature,visibility,surface_pressure,uv_index"
        f"&timezone=auto&forecast_days=1"
    )
    for attempt in range(3):  # retry up to 3 times
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
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
        except Exception as e:
            print(f"[{city}] Attempt {attempt+1} failed: {e}")
            time.sleep(1)
    # All retries failed — return fallback
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
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🌤️</text></svg>">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🌤️</text></svg>">
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@300;400;500;600&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
  :root {
    --ink: #0a0a0f;
    --paper: #f2ede6;
    --accent: #e8441a;
    --muted: #8a8070;
    --card-bg: #ffffff;
    --border: #d4cec5;
    --toolbar-bg: #1a1a22;
  }

  body.dark-mode {
    --ink: #f2ede6;
    --paper: #0f0f14;
    --muted: #8a8a9a;
    --card-bg: #1a1a22;
    --border: #2a2a35;
    --toolbar-bg: #0a0a0f;
  }
  body.dark-mode header { background: #07070a; }
  body.dark-mode .featured-card { background: #1a1a22; }
  body.dark-mode footer { background: #07070a; }

  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    font-family: 'DM Sans', sans-serif;
    background: var(--paper);
    color: var(--ink);
    min-height: 100vh;
    overflow-x: hidden;
    transition: background 0.3s, color 0.3s;
  }

  /* ── TOOLBAR ── */
  .toolbar {
    background: var(--toolbar-bg);
    padding: 10px 40px;
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
    border-bottom: 1px solid rgba(255,255,255,0.06);
  }

  /* Search */
  .search-wrap {
    position: relative;
    flex: 1;
    min-width: 200px;
    max-width: 360px;
  }
  .search-wrap input {
    width: 100%;
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 6px;
    padding: 8px 14px 8px 36px;
    color: #f2ede6;
    font-family: 'Space Mono', monospace;
    font-size: 0.72rem;
    letter-spacing: 1px;
    outline: none;
    transition: border 0.2s;
  }
  .search-wrap input::placeholder { color: #666; }
  .search-wrap input:focus { border-color: var(--accent); }
  .search-wrap .search-icon {
    position: absolute;
    left: 10px; top: 50%;
    transform: translateY(-50%);
    font-size: 0.9rem; pointer-events: none;
  }
  #search-results {
    position: absolute;
    top: calc(100% + 4px); left: 0; right: 0;
    background: #1a1a22;
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 6px;
    z-index: 200;
    max-height: 260px;
    overflow-y: auto;
    display: none;
  }
  .search-result-item {
    padding: 10px 14px;
    font-family: 'Space Mono', monospace;
    font-size: 0.7rem;
    color: #ccc;
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid rgba(255,255,255,0.05);
  }
  .search-result-item:hover { background: rgba(232,68,26,0.15); color: white; }
  .search-result-flag { font-size: 1rem; }

  /* Toggle buttons */
  .toolbar-btn {
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 6px;
    padding: 7px 14px;
    color: #ccc;
    font-family: 'Space Mono', monospace;
    font-size: 0.68rem;
    letter-spacing: 1px;
    cursor: pointer;
    transition: all 0.2s;
    white-space: nowrap;
  }
  .toolbar-btn:hover, .toolbar-btn.active { background: var(--accent); color: white; border-color: var(--accent); }

  /* Country clocks */
  .clocks-bar {
    background: #111118;
    padding: 8px 40px;
    display: flex;
    gap: 30px;
    overflow-x: auto;
    border-bottom: 1px solid rgba(255,255,255,0.04);
  }
  .clocks-bar::-webkit-scrollbar { height: 3px; }
  .clocks-bar::-webkit-scrollbar-thumb { background: var(--accent); }
  .clock-item {
    display: flex;
    align-items: center;
    gap: 10px;
    white-space: nowrap;
  }
  .clock-flag { font-size: 1.2rem; }
  .clock-info { display: flex; flex-direction: column; }
  .clock-country {
    font-family: 'Space Mono', monospace;
    font-size: 0.55rem;
    color: #666;
    letter-spacing: 2px;
    text-transform: uppercase;
  }
  .clock-time {
    font-family: 'Space Mono', monospace;
    font-size: 0.85rem;
    color: #f2ede6;
    font-weight: 700;
    letter-spacing: 1px;
  }
  .clock-date {
    font-family: 'Space Mono', monospace;
    font-size: 0.55rem;
    color: var(--accent);
    letter-spacing: 1px;
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
    font-size: 0.75rem;
    letter-spacing: 3px;
    text-transform: uppercase;
    color: #222;
    font-weight: 700;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 12px;
  }
  body.dark-mode .section-label { color: #ddd; }

  .section-label .flag-emoji {
    font-family: "Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji", sans-serif;
    font-size: 1.2rem;
    font-style: normal;
    letter-spacing: 0;
    text-transform: none;
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
    color: #f2ede6;
  }

  .featured-country {
    font-family: 'Space Mono', monospace;
    font-size: 0.75rem;
    letter-spacing: 3px;
    color: #aaaaaa;
    text-transform: uppercase;
    margin-bottom: 24px;
  }

  .featured-condition {
    font-size: 1.1rem;
    font-weight: 300;
    color: #dddddd;
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

  /* Emoji font fix — forces colour emoji on ALL devices */
  .featured-icon,
  .city-icon,
  .forecast-icon,
  .ticker-item {
    font-family: "Segoe UI Emoji","Apple Color Emoji","Noto Color Emoji","Twemoji Mozilla",sans-serif;
  }

  .featured-icon { font-size: 3rem; margin-bottom: 16px; }

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
    background: #ffffff;
    padding: 28px;
    cursor: pointer;
    transition: transform 0.2s ease, background 0.2s ease;
    animation: fadeUp 0.5s ease both;
    position: relative;
    overflow: hidden;
  }
  body.dark-mode .city-card { background: #1e1e2a; }

  .city-card.selected {
    background: var(--accent) !important;
    transform: scale(1.02);
    z-index: 10;
  }
  .city-card.selected .city-name      { color: #ffffff !important; }
  .city-card.selected .city-country   { color: rgba(255,255,255,0.9) !important; }
  .city-card.selected .city-condition { color: rgba(255,255,255,0.9) !important; }
  .city-card.selected .city-temp      { color: #ffffff !important; }
  .city-card.selected .card-stat-label { color: rgba(255,255,255,0.75) !important; }
  .city-card.selected .card-stat-value { color: #ffffff !important; }
  .city-card.selected .card-stats     { border-color: rgba(255,255,255,0.25) !important; }

  .city-card:hover { background: #111118; transform: scale(1.02); z-index: 10; }
  .city-card:hover .city-name         { color: #ffffff !important; }
  .city-card:hover .city-country      { color: #cccccc !important; }
  .city-card:hover .city-condition    { color: #cccccc !important; }
  .city-card:hover .card-stat-label   { color: #999999 !important; }
  .city-card:hover .card-stat-value   { color: #ffffff !important; }
  .city-card:hover .card-stats        { border-color: rgba(255,255,255,0.12) !important; }

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
    color: #0a0a0f;
    transition: color 0.2s;
  }
  body.dark-mode .city-name { color: #f0ede8; }

  .city-country {
    font-family: 'Space Mono', monospace;
    font-size: 0.62rem;
    letter-spacing: 1.5px;
    color: #333333;
    text-transform: uppercase;
    margin-top: 3px;
    transition: color 0.2s;
    font-weight: 700;
  }
  body.dark-mode .city-country { color: #b8b8cc; }

  .city-icon {
    font-size: 2.2rem;
    font-family: "Segoe UI Emoji","Apple Color Emoji","Noto Color Emoji",sans-serif;
  }

  .city-temp {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 3.5rem;
    color: var(--accent);
    line-height: 1;
    margin-bottom: 6px;
  }

  .city-condition {
    font-size: 0.85rem;
    color: #444444;
    font-weight: 500;
    margin-bottom: 20px;
    transition: color 0.2s;
  }
  body.dark-mode .city-condition { color: #a8a8bc; }

  .card-stats {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    padding-top: 16px;
    border-top: 1px solid #dddddd;
  }
  body.dark-mode .card-stats { border-color: #2e2e3e; }

  .card-stat-label {
    font-family: 'Space Mono', monospace;
    font-size: 0.55rem;
    letter-spacing: 1.5px;
    color: #666666;
    text-transform: uppercase;
    transition: color 0.2s;
    font-weight: 600;
  }
  body.dark-mode .card-stat-label { color: #8888a0; }

  .card-stat-value {
    font-size: 0.9rem;
    font-weight: 600;
    color: #111111;
  }
  body.dark-mode .card-stat-value { color: #e0ddd8; }

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

  /* Share & Download buttons */
  .action-bar {
    display: flex;
    gap: 10px;
    margin-top: 20px;
    flex-wrap: wrap;
  }
  .action-btn {
    display: inline-flex;
    align-items: center;
    gap: 7px;
    padding: 9px 18px;
    border-radius: 6px;
    font-family: 'Space Mono', monospace;
    font-size: 0.68rem;
    letter-spacing: 1px;
    cursor: pointer;
    border: none;
    transition: all 0.2s;
    text-decoration: none;
  }
  .btn-whatsapp { background: #25D366; color: white; }
  .btn-whatsapp:hover { background: #1da851; }
  .btn-twitter  { background: #1DA1F2; color: white; }
  .btn-twitter:hover  { background: #0d8bd9; }
  .btn-download { background: var(--accent); color: white; }
  .btn-download:hover { background: #c93a15; }

  @media (max-width: 768px) {
    main { padding: 20px; }
    .featured-card { grid-template-columns: 1fr; padding: 30px; }
    .featured-temp { font-size: 6rem; text-align: left; }
    .featured-city { font-size: 3rem; }
    .forecast-strip { grid-template-columns: repeat(4, 1fr); }
    header { padding: 0 20px; }
    .tagline { display: none; }
    .toolbar { padding: 10px 16px; }
    .clocks-bar { padding: 8px 16px; }
  }
</style>
</head>
<body>

<div id="page-loader" style="
  position:fixed; inset:0; background:#0a0a0f;
  display:flex; flex-direction:column;
  align-items:center; justify-content:center;
  z-index:9999; transition: opacity 0.5s ease;">
  <div style="font-family:'Bebas Neue',sans-serif; font-size:3rem; color:#f2ede6; letter-spacing:4px;">
    Weather<span style="color:#e8441a">Drift</span>
  </div>
  <div style="font-family:monospace; font-size:0.8rem; color:#8a8070; margin-top:16px; letter-spacing:2px;">
    FETCHING LIVE WEATHER DATA...
  </div>
  <div style="margin-top:24px; width:200px; height:3px; background:#1a1a1f; border-radius:2px; overflow:hidden;">
    <div style="height:100%; background:#e8441a; border-radius:2px; animation:load-bar 2s ease-in-out infinite;"></div>
  </div>
  <style>
    @keyframes load-bar {
      0% { width:0%; margin-left:0; }
      50% { width:60%; margin-left:20%; }
      100% { width:0%; margin-left:100%; }
    }
  </style>
</div>

<script>
  // Hide loader once page is fully ready
  window.addEventListener('load', () => {
    setTimeout(() => {
      const loader = document.getElementById('page-loader');
      if (loader) { loader.style.opacity = '0'; setTimeout(() => loader.remove(), 500); }
    }, 800);
  });
</script>

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

<!-- TOOLBAR: Search + Toggles -->
<div class="toolbar">
  <div class="search-wrap">
    <span class="search-icon">🔍</span>
    <input type="text" id="city-search" placeholder="Search any city..." autocomplete="off" oninput="handleSearch(this.value)">
    <div id="search-results"></div>
  </div>
  <button class="toolbar-btn" id="unit-btn" onclick="toggleUnit()">°C / °F</button>
  <button class="toolbar-btn" id="dark-btn" onclick="toggleDark()">🌙 Dark Mode</button>
</div>

<!-- COUNTRY CLOCKS -->
<div class="clocks-bar">
  <div class="clock-item">
    <span class="clock-flag">🇮🇳</span>
    <div class="clock-info">
      <span class="clock-country">India (IST)</span>
      <span class="clock-time" id="clock-IN">--:--:--</span>
      <span class="clock-date" id="date-IN">---</span>
    </div>
  </div>
  <div class="clock-item">
    <span class="clock-flag">🇯🇵</span>
    <div class="clock-info">
      <span class="clock-country">Japan (JST)</span>
      <span class="clock-time" id="clock-JP">--:--:--</span>
      <span class="clock-date" id="date-JP">---</span>
    </div>
  </div>
  <div class="clock-item">
    <span class="clock-flag">🇷🇺</span>
    <div class="clock-info">
      <span class="clock-country">Russia (MSK)</span>
      <span class="clock-time" id="clock-RU">--:--:--</span>
      <span class="clock-date" id="date-RU">---</span>
    </div>
  </div>
  <div class="clock-item">
    <span class="clock-flag">🇿🇦</span>
    <div class="clock-info">
      <span class="clock-country">S.Africa (SAST)</span>
      <span class="clock-time" id="clock-ZA">--:--:--</span>
      <span class="clock-date" id="date-ZA">---</span>
    </div>
  </div>
  <div class="clock-item">
    <span class="clock-flag">🌐</span>
    <div class="clock-info">
      <span class="clock-country">UTC</span>
      <span class="clock-time" id="clock-UTC">--:--:--</span>
      <span class="clock-date" id="date-UTC">---</span>
    </div>
  </div>
</div>
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
        <div class="featured-country" id="feat-country">{% set cn = {"IN":"🇮🇳 India","JP":"🇯🇵 Japan","RU":"🇷🇺 Russia","ZA":"🇿🇦 South Africa"} %}{{ cn.get(featured.country, featured.country) }} · Updated just now</div>
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
        <div class="featured-unit" id="feat-unit">Celsius</div>
        <div class="action-bar">
          <button class="action-btn btn-whatsapp" onclick="shareWhatsApp()">💬 WhatsApp</button>
          <button class="action-btn btn-twitter"  onclick="shareTwitter()">🐦 Share</button>
          <button class="action-btn btn-download" onclick="downloadCard()">⬇️ Download</button>
        </div>
      </div>
    </div>
  </section>

  <!-- CITY CARDS -->
  <section>
    {% set countries = {"IN": ["🇮🇳", "India"], "JP": ["🇯🇵", "Japan"], "RU": ["🇷🇺", "Russia"], "ZA": ["🇿🇦", "South Africa"]} %}
    {% for code, info in countries.items() %}
    <div class="section-label" style="margin-top: 40px;"><span class="flag-emoji">{{ info[0] }}</span> {{ info[1] }}</div>
    <div class="city-grid" style="margin-bottom: 2px;">
      {% for w in weather_data if w.country == code %}
      <div class="city-card" onclick="selectCity('{{ w.city }}')" data-city="{{ w.city }}">
        <div class="city-header">
          <div>
            <div class="city-name">{{ w.city }}</div>
            <div class="city-country">{{ info[1] }}</div>
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
// ── State ────────────────────────────────────────────────────────────────
let currentFeaturedCity = null;
let isCelsius = true;
let rawTemp = {};   // stores original °C values keyed by element id
let allCities = [];  // populated from weather data for search

// ── Safe value helper ────────────────────────────────────────────────────
function safe(val, suffix = '') {
  return (val !== undefined && val !== null) ? val + suffix : '—';
}

// ── Temperature conversion ───────────────────────────────────────────────
function toF(c) { return Math.round(c * 9/5 + 32); }
function displayTemp(c) {
  if (c === '—' || c === null || c === undefined) return '—';
  return isCelsius ? c + '°' : toF(Number(c)) + '°';
}
function unitLabel() { return isCelsius ? 'Celsius' : 'Fahrenheit'; }

function toggleUnit() {
  isCelsius = !isCelsius;
  document.getElementById('unit-btn').textContent = isCelsius ? '°C / °F' : '°F / °C';
  document.getElementById('feat-unit').textContent = unitLabel();

  // Update featured temp
  const rawC = rawTemp['feat-temp'];
  if (rawC !== undefined) document.getElementById('feat-temp').textContent = displayTemp(rawC);

  // Update all city cards
  document.querySelectorAll('.city-card').forEach(card => {
    const rawC = parseFloat(card.dataset.tempC);
    const tempEl = card.querySelector('.city-temp');
    if (!isNaN(rawC) && tempEl) tempEl.textContent = displayTemp(rawC);
  });

  // Update ticker
  if (allCities.length) updateTicker(allCities);
}

// ── Dark mode ────────────────────────────────────────────────────────────
function toggleDark() {
  document.body.classList.toggle('dark-mode');
  const btn = document.getElementById('dark-btn');
  btn.textContent = document.body.classList.contains('dark-mode') ? '☀️ Light Mode' : '🌙 Dark Mode';
  btn.classList.toggle('active', document.body.classList.contains('dark-mode'));
  localStorage.setItem('darkMode', document.body.classList.contains('dark-mode'));
}
if (localStorage.getItem('darkMode') === 'true') {
  document.body.classList.add('dark-mode');
  document.getElementById('dark-btn').textContent = '☀️ Light Mode';
}

// ── Country clocks ───────────────────────────────────────────────────────
const TIMEZONES = {
  IN:  'Asia/Kolkata',
  JP:  'Asia/Tokyo',
  RU:  'Europe/Moscow',
  ZA:  'Africa/Johannesburg',
  UTC: 'UTC',
};
function updateClocks() {
  const now = new Date();
  for (const [code, tz] of Object.entries(TIMEZONES)) {
    const timeStr = now.toLocaleTimeString('en-GB', { timeZone: tz, hour12: false });
    const dateStr = now.toLocaleDateString('en-GB', { timeZone: tz, weekday: 'short', day: '2-digit', month: 'short' });
    const timeEl = document.getElementById('clock-' + code);
    const dateEl = document.getElementById('date-' + code);
    if (timeEl) timeEl.textContent = timeStr;
    if (dateEl) dateEl.textContent = dateStr;
  }
}
updateClocks();
setInterval(updateClocks, 1000);

// ── Search ───────────────────────────────────────────────────────────────
function handleSearch(query) {
  const box = document.getElementById('search-results');
  if (!query.trim()) { box.style.display = 'none'; return; }
  const q = query.toLowerCase();
  const matches = allCities.filter(c => c.city.toLowerCase().includes(q)).slice(0, 8);
  if (!matches.length) { box.style.display = 'none'; return; }
  const flags = { IN:'🇮🇳', JP:'🇯🇵', RU:'🇷🇺', ZA:'🇿🇦' };
  box.innerHTML = matches.map(c => `
    <div class="search-result-item" onclick="selectCity('${c.city}'); document.getElementById('city-search').value=''; document.getElementById('search-results').style.display='none';">
      <span>${c.city}</span>
      <span class="search-result-flag">${flags[c.country] || ''} ${c.temp !== undefined ? displayTemp(c.temp) : ''}</span>
    </div>
  `).join('');
  box.style.display = 'block';
}
document.addEventListener('click', e => {
  if (!e.target.closest('.search-wrap')) document.getElementById('search-results').style.display = 'none';
});

// ── Update featured panel ────────────────────────────────────────────────
const COUNTRY_NAMES = { IN:'🇮🇳 India', JP:'🇯🇵 Japan', RU:'🇷🇺 Russia', ZA:'🇿🇦 South Africa' };

function updateFeaturedPanel(d) {
  if (!d || d.error) return;
  rawTemp['feat-temp'] = d.temp;
  const countryLabel = COUNTRY_NAMES[d.country] || d.country || '—';
  document.getElementById('feat-icon').textContent       = safe(d.icon);
  document.getElementById('feat-city').textContent       = safe(d.city);
  document.getElementById('feat-country').textContent    = countryLabel + ' · Updated just now';
  document.getElementById('feat-condition').textContent  = safe(d.condition) + ' — Feels like ' + (isCelsius ? safe(d.feels_like,'°C') : toF(d.feels_like)+'°F');
  document.getElementById('feat-temp').textContent       = displayTemp(d.temp);
  document.getElementById('feat-unit').textContent       = unitLabel();
  document.getElementById('feat-humidity').textContent   = safe(d.humidity, '%');
  document.getElementById('feat-wind').textContent       = safe(d.wind_speed, ' km/h');
  document.getElementById('feat-uv').textContent         = safe(d.uv_index);
  document.getElementById('feat-pressure').textContent   = safe(d.pressure, ' hPa');
  document.getElementById('feat-visibility').textContent = safe(d.visibility, ' km');
}

// ── Update 7-day forecast ────────────────────────────────────────────────
function updateForecast(cityName, forecastData) {
  document.getElementById('forecast-label').textContent = '7-Day Outlook · ' + cityName;
  const strip = document.getElementById('forecast-strip');
  strip.innerHTML = (forecastData || []).map(day => `
    <div class="forecast-day">
      <div class="forecast-label">${day.day}</div>
      <div class="forecast-icon">${day.icon}</div>
      <div class="forecast-hi">${displayTemp(day.high)}</div>
      <div class="forecast-lo">${displayTemp(day.low)} lo</div>
    </div>
  `).join('');
}

// ── Select a city card ───────────────────────────────────────────────────
function selectCity(cityName) {
  if (!cityName) return;
  currentFeaturedCity = cityName;
  document.querySelectorAll('.city-card').forEach(c => c.classList.remove('selected'));
  const selected = document.querySelector(`.city-card[data-city="${cityName}"]`);
  if (selected) selected.classList.add('selected');
  document.getElementById('featured-loading').style.display = 'inline';
  document.querySelector('.featured-section').scrollIntoView({ behavior: 'smooth', block: 'start' });

  fetch(`/api/city/${encodeURIComponent(cityName)}`)
    .then(r => r.json())
    .then(d => {
      // Even if there's a soft error field, use cached card data as fallback
      if (d.error && !d.temp) throw new Error(d.error);
      updateFeaturedPanel(d);
      updateForecast(d.city || cityName, d.forecast || []);
      document.getElementById('featured-loading').style.display = 'none';
    })
    .catch(() => {
      // Silent fallback — read data directly from the card already on the page
      document.getElementById('featured-loading').style.display = 'none';
      const card = document.querySelector(`.city-card[data-city="${cityName}"]`);
      if (card) {
        updateFeaturedPanel({
          city: cityName,
          country: card.querySelector('.city-country')?.textContent || '',
          icon: card.querySelector('.city-icon')?.textContent || '🌡️',
          temp: parseFloat(card.dataset.tempC) || 25,
          condition: card.querySelector('.city-condition')?.textContent || '—',
          feels_like: '—', humidity: '—', wind_speed: '—',
          uv_index: '—', pressure: '—', visibility: '—',
        });
      }
    });
}

// ── Update all city cards ────────────────────────────────────────────────
function updateAllCards(weatherList) {
  allCities = weatherList;
  weatherList.forEach(w => {
    const card = document.querySelector(`.city-card[data-city="${w.city}"]`);
    if (!card) return;
    card.dataset.tempC = w.temp;
    const stats = card.querySelectorAll('.card-stat-value');
    const tempEl = card.querySelector('.city-temp');
    const condEl = card.querySelector('.city-condition');
    const iconEl = card.querySelector('.city-icon');
    if (tempEl)   tempEl.textContent   = displayTemp(w.temp);
    if (condEl)   condEl.textContent   = w.condition;
    if (iconEl)   iconEl.textContent   = w.icon;
    if (stats[0]) stats[0].textContent = w.humidity + '%';
    if (stats[1]) stats[1].textContent = w.wind_speed + ' km/h';
    if (stats[2]) stats[2].textContent = w.uv_index;
    if (stats[3]) stats[3].textContent = w.pressure;
  });
}

// ── Update ticker ────────────────────────────────────────────────────────
function updateTicker(weatherList) {
  const ticker = document.querySelector('.ticker');
  if (!ticker) return;
  const items = weatherList.map(w =>
    `<span class="ticker-item">${w.icon} ${w.city} ${displayTemp(w.temp)}·${w.condition}</span>`
  ).join('');
  ticker.innerHTML = items + items;
}

// ── Share on WhatsApp ────────────────────────────────────────────────────
function shareWhatsApp() {
  const city    = document.getElementById('feat-city').textContent;
  const temp    = document.getElementById('feat-temp').textContent;
  const cond    = document.getElementById('feat-condition').textContent;
  const url     = window.location.href;
  const text    = `🌤️ Weather in ${city}: ${temp} — ${cond}\nCheck live weather: ${url}`;
  window.open('https://wa.me/?text=' + encodeURIComponent(text), '_blank');
}

// ── Share on Twitter/X ───────────────────────────────────────────────────
function shareTwitter() {
  const city = document.getElementById('feat-city').textContent;
  const temp = document.getElementById('feat-temp').textContent;
  const cond = document.getElementById('feat-condition').textContent;
  const text = `🌤️ Weather in ${city}: ${temp} — ${cond} | WeatherDrift`;
  window.open('https://twitter.com/intent/tweet?text=' + encodeURIComponent(text) + '&url=' + encodeURIComponent(window.location.href), '_blank');
}

// ── Download weather card as image ───────────────────────────────────────
function downloadCard() {
  const city    = document.getElementById('feat-city').textContent;
  const temp    = document.getElementById('feat-temp').textContent;
  const cond    = document.getElementById('feat-condition').textContent;
  const humidity= document.getElementById('feat-humidity').textContent;
  const wind    = document.getElementById('feat-wind').textContent;
  const icon    = document.getElementById('feat-icon').textContent;
  const date    = new Date().toLocaleDateString('en-GB', {weekday:'long', day:'numeric', month:'long', year:'numeric'});

  const canvas  = document.createElement('canvas');
  canvas.width  = 800; canvas.height = 420;
  const ctx     = canvas.getContext('2d');

  // Background
  const grad = ctx.createLinearGradient(0, 0, 800, 420);
  grad.addColorStop(0, '#0a0a0f');
  grad.addColorStop(1, '#1a1a2e');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, 800, 420);

  // Accent bar
  ctx.fillStyle = '#e8441a';
  ctx.fillRect(0, 0, 6, 420);

  // Icon
  ctx.font = '80px serif';
  ctx.fillText(icon, 60, 120);

  // City name
  ctx.fillStyle = '#f2ede6';
  ctx.font = 'bold 56px sans-serif';
  ctx.fillText(city, 60, 200);

  // Temp
  ctx.fillStyle = '#e8441a';
  ctx.font = 'bold 100px sans-serif';
  ctx.textAlign = 'right';
  ctx.fillText(temp, 760, 200);

  // Condition
  ctx.fillStyle = '#aaa';
  ctx.font = '22px sans-serif';
  ctx.textAlign = 'left';
  ctx.fillText(cond, 60, 250);

  // Stats
  ctx.fillStyle = '#888';
  ctx.font = '18px monospace';
  ctx.fillText('💧 ' + humidity + '   💨 ' + wind, 60, 300);

  // Date
  ctx.fillStyle = '#555';
  ctx.font = '15px monospace';
  ctx.fillText(date, 60, 360);

  // Branding
  ctx.fillStyle = '#e8441a';
  ctx.font = 'bold 18px monospace';
  ctx.textAlign = 'right';
  ctx.fillText('WeatherDrift', 760, 390);

  // Download
  const a = document.createElement('a');
  a.download = `weather-${city.toLowerCase().replace(/ /g,'-')}.png`;
  a.href = canvas.toDataURL('image/png');
  a.click();
}

// ── Auto-refresh every 60 seconds ────────────────────────────────────────
function autoRefresh() {
  fetch('/api/weather')
    .then(r => r.json())
    .then(data => {
      updateAllCards(data.weather);
      updateTicker(data.weather);
      const label = document.getElementById('last-updated-label');
      if (label) label.textContent = 'Last updated: ' + data.last_updated;
      if (currentFeaturedCity) {
        const w = data.weather.find(x => x.city === currentFeaturedCity);
        if (w) updateFeaturedPanel(w);
        fetch(`/api/city/${encodeURIComponent(currentFeaturedCity)}`)
          .then(r => r.json())
          .then(d => updateForecast(d.city, d.forecast))
          .catch(() => {});
      }
    })
    .catch(err => console.error('Auto-refresh error:', err));
}

// ── Init: populate allCities from existing cards ─────────────────────────
document.querySelectorAll('.city-card').forEach(card => {
  const city    = card.dataset.city;
  const tempEl  = card.querySelector('.city-temp');
  const rawC    = tempEl ? parseFloat(tempEl.textContent) : null;
  card.dataset.tempC = rawC;
  if (city && rawC !== null) {
    allCities.push({
      city,
      country: card.querySelector('.city-country')?.textContent || '',
      temp: rawC,
    });
  }
});

setInterval(autoRefresh, 60000);
console.log('WeatherDrift ready ✅');
</script>

</body>
</html>
"""

@app.route("/api/city/<path:city_name>")
def city_api(city_name):
    # Try cache first — avoids redundant API calls and fixes "API error" on click
    cached = get_cached_weather()
    cached_city = next((w for w in cached if w["city"].lower() == city_name.lower()), None)

    coords = CITIES.get(city_name)
    # Also try case-insensitive match in CITIES
    if not coords:
        for k, v in CITIES.items():
            if k.lower() == city_name.lower():
                city_name = k
                coords = v
                break
    if not coords:
        return jsonify({"error": "City not found", "city": city_name}), 404

    # Build forecast — try live API, fall back to random if unavailable
    forecast = get_forecast(city_name)

    # If we have cached data, return it with forecast (no extra API call needed)
    if cached_city:
        return jsonify({**cached_city, "forecast": forecast})

    # No cache — try live fetch
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
        response = requests.get(url, timeout=15)
        data = response.json()
        weather = data["current_weather"]
        icon, condition = get_weather_icon(weather["weathercode"])
        hourly = data.get("hourly", {})
        daily  = data.get("daily", {})
        fc_list = []
        for i in range(7):
            date_obj = datetime.strptime(daily["time"][i], "%Y-%m-%d")
            fi, fc = get_weather_icon(daily["weathercode"][i])
            fc_list.append({
                "day": "Today" if i == 0 else date_obj.strftime("%a"),
                "icon": fi, "condition": fc,
                "high": round(daily["temperature_2m_max"][i]),
                "low":  round(daily["temperature_2m_min"][i]),
            })
        return jsonify({
            "city": city_name,
            "country": coords["country"],
            "temp": round(weather["temperature"]),
            "feels_like": round(hourly.get("apparent_temperature", [weather["temperature"]])[0]),
            "humidity": hourly.get("relativehumidity_2m", [50])[0],
            "wind_speed": round(weather["windspeed"]),
            "condition": condition, "icon": icon,
            "uv_index": round(hourly.get("uv_index", [0])[0], 1),
            "visibility": round(hourly.get("visibility", [10000])[0] / 1000, 1),
            "pressure": round(hourly.get("surface_pressure", [1013])[0]),
            "forecast": fc_list,
        })
    except Exception as e:
        # Return a safe fallback instead of an error — app keeps working
        cond = random.choice(WEATHER_CONDITIONS)
        temp = random.randint(15, 35)
        return jsonify({
            "city": city_name,
            "country": coords["country"],
            "temp": temp, "feels_like": temp - 2,
            "humidity": 65, "wind_speed": 12,
            "condition": cond["condition"], "icon": cond["icon"],
            "uv_index": 4, "visibility": 10.0, "pressure": 1013,
            "forecast": forecast,
        })

@app.route("/api/test")
def api_test():
    """Test if Open-Meteo API is reachable."""
    try:
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast?latitude=28.61&longitude=77.21&current_weather=true",
            timeout=10
        )
        data = r.json()
        return jsonify({
            "status": "✅ API working",
            "test_city": "Delhi",
            "temp": data["current_weather"]["temperature"],
            "windspeed": data["current_weather"]["windspeed"],
        })
    except Exception as e:
        return jsonify({"status": "❌ API failed", "error": str(e)}), 500

@app.route("/health")
def health():
    """Railway health check endpoint."""
    return jsonify({"status": "ok", "cities": len(CITIES)}), 200

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
    import os
    import socket
    port = int(os.environ.get("PORT", 5000))
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        local_ip = "YOUR_PC_IP"
    print("\n" + "="*55)
    print("  🌍  WeatherDrift is running!")
    print("="*55)
    print(f"  Local  (this PC):      http://localhost:{port}")
    print(f"  Network (all devices): http://{local_ip}:{port}")
    print("="*55)
    print("  📱 Share the Network URL on same Wi-Fi")
    print("  🌐 Or deploy to Railway for global access!")
    print("="*55 + "\n")
    app.run(debug=False, host="0.0.0.0", port=port)