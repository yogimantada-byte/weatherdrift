from flask import Flask, render_template_string, jsonify, request
import requests, json, random, time, threading, math, os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

app = Flask(__name__)

# ── Persistence file (survives restarts) ────────────────────────────────────
DATA_FILE = os.path.join(os.path.dirname(__file__), "city_data.json")

def _load_data():
    """Load custom cities and deleted city names from disk."""
    global _custom_cities, _deleted_cities
    if os.path.exists(DATA_FILE):
        try:
            d = json.load(open(DATA_FILE))
            _custom_cities  = d.get("custom_cities",  {})
            _deleted_cities = set(d.get("deleted_cities", []))
        except Exception:
            pass

def _save_data():
    """Persist custom cities and deleted city names to disk."""
    try:
        json.dump(
            {"custom_cities": _custom_cities,
             "deleted_cities": list(_deleted_cities)},
            open(DATA_FILE, "w"), indent=2
        )
    except Exception:
        pass

# ── Cache ───────────────────────────────────────────────────────────────────
_cache = {"weather": None, "timestamp": 0, "last_updated": "Never"}
_custom_cities  = {}   # user-added cities (persisted to disk)
_deleted_cities = set()  # built-in cities hidden by user (persisted to disk)
REFRESH_INTERVAL = 60

# Load persisted data on startup
_load_data()

CITIES = {
    "Mumbai":          {"lat": 19.08,  "lon": 72.88,  "country": "IN"},
    "Delhi":           {"lat": 28.61,  "lon": 77.21,  "country": "IN"},
    "Bangalore":       {"lat": 12.97,  "lon": 77.59,  "country": "IN"},
    "Chennai":         {"lat": 13.08,  "lon": 80.27,  "country": "IN"},
    "Kolkata":         {"lat": 22.57,  "lon": 88.36,  "country": "IN"},
    "Hyderabad":       {"lat": 17.38,  "lon": 78.49,  "country": "IN"},
    "Pune":            {"lat": 18.52,  "lon": 73.86,  "country": "IN"},
    "Ahmedabad":       {"lat": 23.03,  "lon": 72.58,  "country": "IN"},
    "Jaipur":          {"lat": 26.91,  "lon": 75.79,  "country": "IN"},
    "Visakhapatnam":   {"lat": 17.69,  "lon": 83.22,  "country": "IN"},
    "Vijayawada":      {"lat": 16.51,  "lon": 80.62,  "country": "IN"},
    "R Bhimavaram":    {"lat": 17.69,  "lon": 82.89,  "country": "IN"},
    "Surat":           {"lat": 21.17,  "lon": 72.83,  "country": "IN"},
    "Vadodara":        {"lat": 22.31,  "lon": 73.18,  "country": "IN"},
    "Rajkot":          {"lat": 22.30,  "lon": 70.80,  "country": "IN"},
    "Itanagar":        {"lat": 27.08,  "lon": 93.60,  "country": "IN"},
    "Naharlagun":      {"lat": 27.10,  "lon": 93.69,  "country": "IN"},
    "Lucknow":         {"lat": 26.85,  "lon": 80.95,  "country": "IN"},
    "Kanpur":          {"lat": 26.46,  "lon": 80.33,  "country": "IN"},
    "Agra":            {"lat": 27.18,  "lon": 78.01,  "country": "IN"},
    "Varanasi":        {"lat": 25.32,  "lon": 83.01,  "country": "IN"},
    "Bhopal":          {"lat": 23.25,  "lon": 77.40,  "country": "IN"},
    "Indore":          {"lat": 22.72,  "lon": 75.86,  "country": "IN"},
    "Gwalior":         {"lat": 26.22,  "lon": 78.18,  "country": "IN"},
    "Guwahati":        {"lat": 26.19,  "lon": 91.74,  "country": "IN"},
    "Dibrugarh":       {"lat": 27.48,  "lon": 94.91,  "country": "IN"},
    "Silchar":         {"lat": 24.83,  "lon": 92.80,  "country": "IN"},
    "Thiruvananthapuram": {"lat": 8.52, "lon": 76.94, "country": "IN"},
    "Kochi":           {"lat": 9.93,   "lon": 76.26,  "country": "IN"},
    "Kozhikode":       {"lat": 11.25,  "lon": 75.78,  "country": "IN"},
    "Tokyo":           {"lat": 35.68,  "lon": 139.69, "country": "JP"},
    "Osaka":           {"lat": 34.69,  "lon": 135.50, "country": "JP"},
    "Kyoto":           {"lat": 35.01,  "lon": 135.77, "country": "JP"},
    "Sapporo":         {"lat": 43.06,  "lon": 141.35, "country": "JP"},
    "Nagoya":          {"lat": 35.18,  "lon": 136.91, "country": "JP"},
    "Fukuoka":         {"lat": 33.59,  "lon": 130.40, "country": "JP"},
    "Hiroshima":       {"lat": 34.39,  "lon": 132.45, "country": "JP"},
    "Sendai":          {"lat": 38.27,  "lon": 140.87, "country": "JP"},
    "Yokohama":        {"lat": 35.44,  "lon": 139.64, "country": "JP"},
    "Naha":            {"lat": 26.21,  "lon": 127.68, "country": "JP"},
    "Moscow":          {"lat": 55.75,  "lon": 37.62,  "country": "RU"},
    "Saint Petersburg": {"lat": 59.93, "lon": 30.32,  "country": "RU"},
    "Novosibirsk":     {"lat": 55.01,  "lon": 82.92,  "country": "RU"},
    "Yekaterinburg":   {"lat": 56.84,  "lon": 60.60,  "country": "RU"},
    "Kazan":           {"lat": 55.79,  "lon": 49.12,  "country": "RU"},
    "Vladivostok":     {"lat": 43.12,  "lon": 131.89, "country": "RU"},
    "Sochi":           {"lat": 43.60,  "lon": 39.73,  "country": "RU"},
    "Omsk":            {"lat": 54.99,  "lon": 73.37,  "country": "RU"},
    "Irkutsk":         {"lat": 52.29,  "lon": 104.29, "country": "RU"},
    "Murmansk":        {"lat": 68.97,  "lon": 33.07,  "country": "RU"},
    "Johannesburg":    {"lat": -26.20, "lon": 28.04,  "country": "ZA"},
    "Cape Town":       {"lat": -33.93, "lon": 18.42,  "country": "ZA"},
    "Durban":          {"lat": -29.86, "lon": 31.02,  "country": "ZA"},
    "Pretoria":        {"lat": -25.75, "lon": 28.19,  "country": "ZA"},
    "Port Elizabeth":  {"lat": -33.96, "lon": 25.60,  "country": "ZA"},
    "Bloemfontein":    {"lat": -29.12, "lon": 26.21,  "country": "ZA"},
    "East London":     {"lat": -33.02, "lon": 27.91,  "country": "ZA"},
    "Nelspruit":       {"lat": -25.47, "lon": 30.97,  "country": "ZA"},
    "Kimberley":       {"lat": -28.74, "lon": 24.76,  "country": "ZA"},
    "Polokwane":       {"lat": -23.90, "lon": 29.45,  "country": "ZA"},
}

COUNTRY_NAMES = {"IN": "🇮🇳 India", "JP": "🇯🇵 Japan", "RU": "🇷🇺 Russia", "ZA": "🇿🇦 South Africa", "CUSTOM": "🌍 Custom"}

def get_weather_icon(weathercode):
    if weathercode == 0:             return "☀️",  "Clear Sky"
    elif weathercode in [1, 2]:      return "⛅",  "Partly Cloudy"
    elif weathercode == 3:           return "☁️",  "Overcast"
    elif weathercode in [45, 48]:    return "🌫️", "Foggy"
    elif weathercode in [51, 53, 55]:return "🌦️", "Drizzle"
    elif weathercode in [61, 63, 65]:return "🌧️", "Rainy"
    elif weathercode in [71,73,75,77]:return "❄️", "Snowy"
    elif weathercode in [80, 81, 82]:return "🌧️", "Rain Showers"
    elif weathercode in [85, 86]:    return "🌨️", "Snow Showers"
    elif weathercode in [95,96,99]:  return "⛈️",  "Stormy"
    else:                            return "🌡️", "Unknown"

def get_aqi_label(aqi):
    if aqi <= 50:   return "Good",        "#00c853"
    if aqi <= 100:  return "Moderate",    "#ffd600"
    if aqi <= 150:  return "Unhealthy*",  "#ff6d00"
    if aqi <= 200:  return "Unhealthy",   "#d50000"
    if aqi <= 300:  return "Very Unhealthy","#6a1b9a"
    return "Hazardous", "#4e342e"

def fetch_single_city(city, coords):
    lat, lon = coords["lat"], coords["lon"]
    url = (f"https://api.open-meteo.com/v1/forecast"
           f"?latitude={lat}&longitude={lon}&current_weather=true"
           f"&hourly=relativehumidity_2m,apparent_temperature,visibility,"
           f"surface_pressure,uv_index,precipitation_probability,windspeed_10m"
           f"&daily=weathercode,temperature_2m_max,temperature_2m_min,"
           f"sunrise,sunset,precipitation_probability_max"
           f"&timezone=auto&forecast_days=1")
    # AQI from Open-Meteo air quality API
    aqi_url = (f"https://air-quality-api.open-meteo.com/v1/air-quality"
               f"?latitude={lat}&longitude={lon}&hourly=us_aqi&timezone=auto&forecast_days=1")
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            data = r.json()
            weather = data["current_weather"]
            temp = round(weather["temperature"])
            wind = round(weather["windspeed"])
            icon, condition = get_weather_icon(weather["weathercode"])
            hourly = data.get("hourly", {})
            daily  = data.get("daily", {})
            # Current hour index
            now_h  = datetime.now().hour
            # Sunrise/Sunset
            sunrise = daily.get("sunrise", [""])[0]
            sunset  = daily.get("sunset", [""])[0]
            sunrise_t = sunrise.split("T")[-1][:5] if sunrise else "06:00"
            sunset_t  = sunset.split("T")[-1][:5]  if sunset  else "18:00"
            # Rain probability
            rain_prob = hourly.get("precipitation_probability", [0] * 24)
            rain_now  = rain_prob[min(now_h, len(rain_prob)-1)] if rain_prob else 0
            # AQI
            aqi_val = 50
            try:
                aq = requests.get(aqi_url, timeout=8).json()
                aqi_list = aq.get("hourly", {}).get("us_aqi", [])
                aqi_val = int(aqi_list[min(now_h, len(aqi_list)-1)]) if aqi_list else 50
            except: pass
            aqi_label, aqi_color = get_aqi_label(aqi_val)
            # Hourly forecast (next 24h)
            hourly_fc = []
            for i in range(0, 24, 3):
                if i < len(hourly.get("windspeed_10m", [])):
                    h_icon, h_cond = get_weather_icon(weather["weathercode"])
                    hourly_fc.append({
                        "hour": f"{(now_h + i) % 24:02d}:00",
                        "temp": round(hourly.get("apparent_temperature", [temp]*24)[min(i, 23)]),
                        "icon": h_icon,
                        "rain": hourly.get("precipitation_probability", [0]*24)[min(i,23)],
                    })
            return {
                "city": city, "country": coords["country"],
                "temp": temp, "feels_like": round(hourly.get("apparent_temperature",[temp])[0]),
                "humidity": hourly.get("relativehumidity_2m",[50])[0],
                "wind_speed": wind, "condition": condition, "icon": icon,
                "uv_index": round(hourly.get("uv_index",[0])[0], 1),
                "visibility": round(hourly.get("visibility",[10000])[0]/1000, 1),
                "pressure": round(hourly.get("surface_pressure",[1013])[0]),
                "sunrise": sunrise_t, "sunset": sunset_t,
                "rain_prob": rain_now,
                "aqi": aqi_val, "aqi_label": aqi_label, "aqi_color": aqi_color,
                "hourly": hourly_fc,
                "lat": lat, "lon": lon,
            }
        except Exception as e:
            print(f"[{city}] Attempt {attempt+1} failed: {e}")
            time.sleep(1)
    # Fallback
    return {
        "city": city, "country": coords["country"],
        "temp": 25, "feels_like": 23, "humidity": 65, "wind_speed": 12,
        "condition": "Partly Cloudy", "icon": "⛅",
        "uv_index": 4, "visibility": 10.0, "pressure": 1013,
        "sunrise": "06:15", "sunset": "18:30", "rain_prob": 10,
        "aqi": 50, "aqi_label": "Good", "aqi_color": "#00c853",
        "hourly": [], "lat": coords["lat"], "lon": coords["lon"],
    }

def get_all_cities():
    """Return all active cities — built-ins minus deleted ones, plus custom additions."""
    active = {k: v for k, v in CITIES.items() if k not in _deleted_cities}
    return {**active, **_custom_cities}

def get_weather_data():
    all_c = get_all_cities()
    results = {}
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(fetch_single_city, city, coords): city
                   for city, coords in all_c.items()}
        for future in as_completed(futures):
            city = futures[future]
            result = future.result()
            if result: results[city] = result
    return [results[c] for c in all_c if c in results]

def refresh_cache():
    global _cache
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Refreshing cache...")
    data = get_weather_data()
    _cache["weather"] = data
    _cache["timestamp"] = time.time()
    _cache["last_updated"] = datetime.now().strftime("%H:%M:%S")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Cache updated — {len(data)} cities")

def background_refresh():
    while True:
        try: refresh_cache()
        except Exception as e: print(f"BG error: {e}")
        time.sleep(REFRESH_INTERVAL)

def get_cached_weather():
    if _cache["weather"] is None: refresh_cache()
    return _cache["weather"]

_bg = threading.Thread(target=background_refresh, daemon=True)
_bg.start()

def get_forecast(city_name):
    all_c = get_all_cities()
    coords = all_c.get(city_name)
    if not coords: return []
    lat, lon = coords["lat"], coords["lon"]
    url = (f"https://api.open-meteo.com/v1/forecast"
           f"?latitude={lat}&longitude={lon}"
           f"&daily=weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max"
           f"&timezone=auto&forecast_days=7")
    try:
        data = requests.get(url, timeout=10).json()
        daily = data["daily"]
        fc = []
        for i in range(7):
            d = datetime.strptime(daily["time"][i], "%Y-%m-%d")
            icon, cond = get_weather_icon(daily["weathercode"][i])
            fc.append({
                "day": "Today" if i == 0 else d.strftime("%a"),
                "icon": icon, "condition": cond,
                "high": round(daily["temperature_2m_max"][i]),
                "low":  round(daily["temperature_2m_min"][i]),
                "rain": daily.get("precipitation_probability_max", [0]*7)[i],
            })
        return fc
    except:
        days = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
        today = datetime.now().weekday()
        return [{"day": "Today" if i==0 else days[(today+i)%7],
                 "icon":"⛅","condition":"Partly Cloudy",
                 "high":random.randint(20,35),"low":random.randint(10,19),"rain":20}
                for i in range(7)]

# ─────────────────────────────────────────────────────────────────────────────
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AHOY WeatherDrift — Global Weather Intelligence</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🌤️</text></svg>">
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@300;400;500;600&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/twemoji.min.js" crossorigin="anonymous" defer></script>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" defer></script>
<style>
:root {
  --ink:#0a0a0f; --paper:#f2ede6; --accent:#e8441a;
  --muted:#8a8070; --card-bg:#ffffff; --border:#d4cec5;
  --toolbar-bg:#1a1a22; --success:#00c853; --warn:#ffd600;
}
body.dark {
  --ink:#f2ede6; --paper:#0f0f14; --muted:#8a8a9a;
  --card-bg:#1e1e2a; --border:#2a2a35; --toolbar-bg:#0a0a0f;
}
*{margin:0;padding:0;box-sizing:border-box;}
body{font-family:'DM Sans',sans-serif;background:var(--paper);color:var(--ink);min-height:100vh;overflow-x:hidden;transition:background .3s,color .3s;}

/* ── HEADER ── */
header{background:#0a0a0f;color:#f2ede6;padding:0 40px;display:flex;align-items:center;justify-content:space-between;border-bottom:3px solid var(--accent);position:sticky;top:0;z-index:1000;}
.logo-block{display:flex;align-items:baseline;gap:12px;padding:18px 0;}
.logo{font-family:'Bebas Neue',sans-serif;font-size:2.6rem;letter-spacing:3px;color:#f2ede6;}
.logo span{color:var(--accent);}
.tagline{font-family:'Space Mono',monospace;font-size:.65rem;color:#8a8070;letter-spacing:2px;text-transform:uppercase;}
.header-meta{font-family:'Space Mono',monospace;font-size:.7rem;color:#8a8070;text-align:right;line-height:1.8;}
.live-badge{display:inline-flex;align-items:center;gap:6px;background:var(--accent);color:white;padding:3px 10px;font-size:.65rem;letter-spacing:2px;font-weight:700;margin-bottom:4px;}
.live-dot{width:6px;height:6px;background:white;border-radius:50%;animation:pulse 1.5s infinite;}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}

/* ── TOOLBAR ── */
.toolbar{background:var(--toolbar-bg);padding:10px 40px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;border-bottom:1px solid rgba(255,255,255,.06);}
.search-wrap{position:relative;flex:1;min-width:200px;max-width:360px;}
.search-wrap input{width:100%;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.12);border-radius:6px;padding:8px 14px 8px 36px;color:#f2ede6;font-family:'Space Mono',monospace;font-size:.72rem;letter-spacing:1px;outline:none;transition:border .2s;}
.search-wrap input::placeholder{color:#666;}
.search-wrap input:focus{border-color:var(--accent);}
.search-icon{position:absolute;left:10px;top:50%;transform:translateY(-50%);font-size:.9rem;pointer-events:none;}
#search-results{position:absolute;top:calc(100% + 4px);left:0;right:0;background:#1a1a22;border:1px solid rgba(255,255,255,.1);border-radius:6px;z-index:1100;max-height:260px;overflow-y:auto;display:none;}
.search-result-item{padding:10px 14px;font-family:'Space Mono',monospace;font-size:.7rem;color:#ccc;cursor:pointer;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid rgba(255,255,255,.05);}
.search-result-item:hover{background:rgba(232,68,26,.15);color:white;}
.toolbar-btn{background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.12);border-radius:6px;padding:7px 14px;color:#ccc;font-family:'Space Mono',monospace;font-size:.68rem;letter-spacing:1px;cursor:pointer;transition:all .2s;white-space:nowrap;}
.toolbar-btn:hover,.toolbar-btn.active{background:var(--accent);color:white;border-color:var(--accent);}

/* ── CLOCKS ── */
.clocks-bar{background:#111118;padding:8px 40px;display:flex;gap:30px;overflow-x:auto;border-bottom:1px solid rgba(255,255,255,.04);}
.clocks-bar::-webkit-scrollbar{height:3px;}
.clocks-bar::-webkit-scrollbar-thumb{background:var(--accent);}
.clock-item{display:flex;align-items:center;gap:10px;white-space:nowrap;}
.clock-flag{font-size:1.2rem;font-family:"Segoe UI Emoji","Apple Color Emoji","Noto Color Emoji",sans-serif;}
.clock-info{display:flex;flex-direction:column;}
.clock-country{font-family:'Space Mono',monospace;font-size:.55rem;color:#666;letter-spacing:2px;text-transform:uppercase;}
.clock-time{font-family:'Space Mono',monospace;font-size:.85rem;color:#f2ede6;font-weight:700;}
.clock-date{font-family:'Space Mono',monospace;font-size:.55rem;color:var(--accent);}

/* ── TICKER ── */
.ticker-wrap{background:var(--accent);overflow:hidden;padding:10px 0;}
.ticker{display:flex;animation:ticker-scroll 40s linear infinite;white-space:nowrap;}
.ticker-item{font-family:'Space Mono',monospace;font-size:.75rem;font-weight:700;color:white;padding:0 40px;letter-spacing:1px;}
@keyframes ticker-scroll{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}

/* ── MAIN ── */
main{max-width:1400px;margin:0 auto;padding:40px;}
.section-label{font-family:'Space Mono',monospace;font-size:.75rem;letter-spacing:3px;text-transform:uppercase;color:#222;font-weight:700;margin-bottom:20px;display:flex;align-items:center;gap:12px;}
body.dark .section-label{color:#ddd;}
.section-label .flag-emoji{font-family:"Segoe UI Emoji","Apple Color Emoji","Noto Color Emoji",sans-serif;font-size:1.2rem;letter-spacing:0;text-transform:none;}
.section-label::after{content:'';flex:1;height:1px;background:var(--border);}

/* ── FEATURED CARD ── */
.featured-section{margin-bottom:60px;}
.featured-card{background:#0a0a0f;color:#f2ede6;padding:50px 60px;display:grid;grid-template-columns:1fr auto;gap:40px;align-items:start;position:relative;overflow:hidden;animation:fadeUp .6s ease both;}
.featured-card::before{content:'';position:absolute;top:-80px;right:-80px;width:300px;height:300px;border-radius:50%;background:radial-gradient(circle,rgba(232,68,26,.2) 0%,transparent 70%);}
.featured-city{font-family:'Bebas Neue',sans-serif;font-size:5rem;letter-spacing:4px;line-height:1;margin-bottom:8px;color:#f2ede6;}
.featured-country{font-family:'Space Mono',monospace;font-size:.75rem;letter-spacing:3px;color:#aaa;text-transform:uppercase;margin-bottom:20px;}
.featured-condition{font-size:1.1rem;font-weight:300;color:#ddd;margin-bottom:20px;}
.featured-icon{font-size:3rem;margin-bottom:16px;font-family:"Segoe UI Emoji","Apple Color Emoji","Noto Color Emoji",sans-serif;}
.featured-temp{font-family:'Bebas Neue',sans-serif;font-size:9rem;line-height:1;color:var(--accent);text-align:right;}
.featured-unit{font-family:'Space Mono',monospace;font-size:1.2rem;color:#888;text-align:right;margin-bottom:16px;}

.stats-row{display:flex;gap:30px;margin-top:24px;padding-top:24px;border-top:1px solid rgba(255,255,255,.1);flex-wrap:wrap;}
.stat{display:flex;flex-direction:column;gap:4px;}
.stat-label{font-family:'Space Mono',monospace;font-size:.6rem;letter-spacing:2px;color:#888;text-transform:uppercase;}
.stat-value{font-size:1.1rem;font-weight:600;color:#f2ede6;}

/* AQI Bar */
.aqi-row{display:flex;align-items:center;gap:12px;margin-top:16px;}
.aqi-bar-wrap{flex:1;height:8px;background:rgba(255,255,255,.1);border-radius:4px;overflow:hidden;}
.aqi-bar-fill{height:100%;border-radius:4px;transition:width .5s;}
.aqi-label-text{font-family:'Space Mono',monospace;font-size:.65rem;font-weight:700;letter-spacing:1px;}

/* Sun row */
.sun-row{display:flex;gap:24px;margin-top:12px;}
.sun-item{font-family:'Space Mono',monospace;font-size:.7rem;color:#aaa;display:flex;align-items:center;gap:6px;}
.sun-item span{color:#f2ede6;font-weight:700;}

/* Rain gauge */
.rain-row{margin-top:12px;display:flex;align-items:center;gap:12px;}
.rain-gauge{position:relative;width:60px;height:60px;}
.rain-gauge svg{transform:rotate(-90deg);}
.rain-pct{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-family:'Space Mono',monospace;font-size:.65rem;font-weight:700;color:#4fc3f7;}

/* Hourly strip */
.hourly-strip{display:flex;gap:8px;overflow-x:auto;padding:16px 0;margin-top:20px;border-top:1px solid rgba(255,255,255,.1);}
.hourly-strip::-webkit-scrollbar{height:3px;}
.hourly-strip::-webkit-scrollbar-thumb{background:var(--accent);}
.hour-block{min-width:64px;background:rgba(255,255,255,.05);border-radius:8px;padding:10px 8px;text-align:center;flex-shrink:0;}
.hour-time{font-family:'Space Mono',monospace;font-size:.58rem;color:#888;margin-bottom:6px;}
.hour-icon{font-size:1.3rem;margin-bottom:4px;font-family:"Segoe UI Emoji","Apple Color Emoji","Noto Color Emoji",sans-serif;}
.hour-temp{font-family:'Space Mono',monospace;font-size:.72rem;font-weight:700;color:#f2ede6;}
.hour-rain{font-size:.58rem;color:#4fc3f7;margin-top:2px;}

/* Action bar */
.action-bar{display:flex;gap:10px;margin-top:20px;flex-wrap:wrap;}
.action-btn{display:inline-flex;align-items:center;gap:7px;padding:9px 18px;border-radius:6px;font-family:'Space Mono',monospace;font-size:.68rem;letter-spacing:1px;cursor:pointer;border:none;transition:all .2s;text-decoration:none;}
.btn-whatsapp{background:#25D366;color:white;}
.btn-whatsapp:hover{background:#1da851;}
.btn-twitter{background:#1DA1F2;color:white;}
.btn-twitter:hover{background:#0d8bd9;}
.btn-download{background:var(--accent);color:white;}
.btn-download:hover{background:#c93a15;}

/* ── COMPARE PANEL ── */
.compare-panel{background:#0a0a0f;border:2px solid var(--accent);padding:30px 40px;margin-bottom:40px;display:none;}
body.dark .compare-panel{background:#1a1a22;}
.compare-grid{display:grid;grid-template-columns:1fr 1fr;gap:30px;margin-top:20px;}
.compare-city{padding:20px;border:1px solid rgba(255,255,255,.1);border-radius:4px;}
.compare-city-name{font-family:'Bebas Neue',sans-serif;font-size:2rem;color:#f2ede6;letter-spacing:2px;}
.compare-temp{font-family:'Bebas Neue',sans-serif;font-size:4rem;color:var(--accent);line-height:1;}
.compare-row{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.06);font-family:'Space Mono',monospace;font-size:.68rem;color:#aaa;}
.compare-row span:last-child{color:#f2ede6;font-weight:700;}
.compare-select{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.15);color:#f2ede6;padding:8px 12px;font-family:'Space Mono',monospace;font-size:.7rem;border-radius:4px;outline:none;width:100%;margin-bottom:12px;}

/* ── ALERTS ── */
.alert-bar{background:#d50000;color:white;padding:10px 40px;font-family:'Space Mono',monospace;font-size:.72rem;letter-spacing:1px;display:none;align-items:center;gap:12px;}
.alert-bar.show{display:flex;}

/* ── CITY GRID ── */
.city-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:2px;margin-bottom:60px;background:var(--border);border:2px solid var(--border);}
.city-card{background:#ffffff;padding:28px;cursor:pointer;transition:transform .2s,background .2s;animation:fadeUp .5s ease both;position:relative;overflow:hidden;}
body.dark .city-card{background:#1e1e2a;}
.city-card.selected{background:var(--accent)!important;transform:scale(1.02);z-index:10;}
.city-card.selected .city-name{color:#fff!important;}
.city-card.selected .city-country,.city-card.selected .city-condition,.city-card.selected .card-stat-label{color:rgba(255,255,255,.85)!important;}
.city-card.selected .card-stat-value,.city-card.selected .city-temp{color:#fff!important;}
.city-card.selected .card-stats{border-color:rgba(255,255,255,.25)!important;}
.city-card:hover{background:#111118;transform:scale(1.02);z-index:10;}
.city-card:hover .city-name{color:#fff!important;}
.city-card:hover .city-country,.city-card:hover .city-condition,.city-card:hover .card-stat-label{color:#ccc!important;}
.city-card:hover .card-stat-value{color:#fff!important;}
.city-card:hover .card-stats{border-color:rgba(255,255,255,.12)!important;}
.city-delete-btn{position:absolute;top:8px;right:8px;background:rgba(244,67,54,.15);border:1px solid rgba(244,67,54,.4);color:#f44336;width:24px;height:24px;border-radius:50%;font-size:.7rem;cursor:pointer;display:none;align-items:center;justify-content:center;z-index:20;transition:all .2s;line-height:1;}
.city-card:hover .city-delete-btn{display:flex;}
.city-delete-btn:hover{background:rgba(244,67,54,.85);color:#fff;border-color:#f44336;transform:scale(1.15);}
.city-header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:20px;}
.city-name{font-family:'Bebas Neue',sans-serif;font-size:1.8rem;letter-spacing:2px;color:#0a0a0f;transition:color .2s;}
body.dark .city-name{color:#f0ede8;}
.city-country{font-family:'Space Mono',monospace;font-size:.62rem;letter-spacing:1.5px;color:#333;text-transform:uppercase;margin-top:3px;font-weight:700;}
body.dark .city-country{color:#b8b8cc;}
.city-icon{font-size:2.2rem;font-family:"Segoe UI Emoji","Apple Color Emoji","Noto Color Emoji",sans-serif;}
.city-temp{font-family:'Bebas Neue',sans-serif;font-size:3.5rem;color:var(--accent);line-height:1;margin-bottom:6px;}
.city-condition{font-size:.85rem;color:#444;font-weight:500;margin-bottom:12px;}
body.dark .city-condition{color:#a8a8bc;}
/* Mini badges */
.city-badges{display:flex;gap:6px;margin-bottom:12px;flex-wrap:wrap;}
.badge{font-family:'Space Mono',monospace;font-size:.55rem;padding:2px 7px;border-radius:20px;font-weight:700;letter-spacing:.5px;}
.badge-aqi{background:rgba(0,200,83,.15);color:#00c853;}
.badge-rain{background:rgba(79,195,247,.15);color:#4fc3f7;}
.card-stats{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding-top:16px;border-top:1px solid #ddd;}
body.dark .card-stats{border-color:#2e2e3e;}
.card-stat-label{font-family:'Space Mono',monospace;font-size:.55rem;letter-spacing:1.5px;color:#666;text-transform:uppercase;font-weight:600;}
body.dark .card-stat-label{color:#8888a0;}
.card-stat-value{font-size:.9rem;font-weight:600;color:#111;}
body.dark .card-stat-value{color:#e0ddd8;}

/* ── FORECAST ── */
.forecast-section{margin-bottom:60px;}
.forecast-strip{display:grid;grid-template-columns:repeat(7,1fr);gap:2px;background:var(--border);border:2px solid var(--border);}
.forecast-day{background:var(--card-bg);padding:20px 16px;text-align:center;animation:fadeUp .5s ease both;}
.forecast-label{font-family:'Space Mono',monospace;font-size:.65rem;letter-spacing:2px;color:var(--muted);text-transform:uppercase;margin-bottom:12px;}
.forecast-icon{font-size:1.8rem;margin-bottom:8px;font-family:"Segoe UI Emoji","Apple Color Emoji","Noto Color Emoji",sans-serif;}
.forecast-hi{font-family:'Bebas Neue',sans-serif;font-size:1.8rem;color:var(--accent);}
.forecast-lo{font-family:'Space Mono',monospace;font-size:.65rem;color:var(--muted);margin-top:2px;}
.forecast-rain-bar{height:3px;background:rgba(79,195,247,.3);border-radius:2px;margin-top:6px;overflow:hidden;}
.forecast-rain-fill{height:100%;background:#4fc3f7;border-radius:2px;}

/* ── HISTORY CHART ── */
.history-section{margin-bottom:60px;}
.chart-outer{background:var(--card-bg);border:2px solid var(--border);padding:0;position:relative;}
body.dark .chart-outer{background:#1a1a24;}
.chart-toolbar{display:flex;align-items:center;justify-content:space-between;padding:16px 24px 0;flex-wrap:wrap;gap:8px;}
.chart-title{font-family:'Space Mono',monospace;font-size:.7rem;letter-spacing:2px;color:var(--muted);text-transform:uppercase;}
.chart-tabs{display:flex;gap:4px;}
.chart-tab{font-family:'Space Mono',monospace;font-size:.6rem;padding:4px 12px;border:1px solid var(--border);background:transparent;color:var(--muted);cursor:pointer;border-radius:3px;transition:all .2s;letter-spacing:1px;}
.chart-tab.active,.chart-tab:hover{background:var(--accent);color:white;border-color:var(--accent);}
.chart-stats-row{display:flex;gap:30px;padding:12px 24px;border-bottom:1px solid var(--border);}
.chart-stat{display:flex;flex-direction:column;gap:2px;}
.chart-stat-label{font-family:'Space Mono',monospace;font-size:.55rem;color:var(--muted);letter-spacing:1px;text-transform:uppercase;}
.chart-stat-value{font-family:'Bebas Neue',sans-serif;font-size:1.6rem;color:var(--accent);letter-spacing:1px;}
.chart-canvas-wrap{padding:20px 24px 24px;height:260px;position:relative;}
#history-chart{width:100%;height:100%;display:block;}
.chart-legend{display:flex;gap:16px;padding:0 24px 16px;flex-wrap:wrap;}
.legend-item{display:flex;align-items:center;gap:6px;font-family:'Space Mono',monospace;font-size:.6rem;color:var(--muted);}
.legend-dot{width:8px;height:8px;border-radius:50%;}

/* ── WORLD MAP ── */
.map-section{margin-bottom:60px;}
/* Leaflet customisation */
.leaflet-weather-tooltip{background:#0d1a2a!important;border:1px solid #e8441a!important;color:#f2ede6!important;border-radius:4px!important;font-family:monospace!important;padding:8px 12px!important;box-shadow:0 4px 20px rgba(0,0,0,.6)!important;}
.leaflet-weather-tooltip::before{border-top-color:#e8441a!important;}
.leaflet-tooltip-top::before{border-top-color:#e8441a!important;}
.leaflet-container{font-family:monospace!important;background:#050d1a!important;}
.leaflet-pane,.leaflet-tile,.leaflet-marker-icon,.leaflet-marker-shadow,.leaflet-tile-container,.leaflet-pane > svg,.leaflet-pane > canvas,.leaflet-zoom-box,.leaflet-image-layer,.leaflet-layer{position:absolute!important;}
.leaflet-map-pane{z-index:auto!important;}
.leaflet-tile-pane{z-index:200!important;}
.leaflet-overlay-pane{z-index:400!important;}
.leaflet-shadow-pane{z-index:500!important;}
.leaflet-marker-pane{z-index:600!important;}
.leaflet-tooltip-pane{z-index:650!important;}
.leaflet-popup-pane{z-index:700!important;}
.leaflet-control-attribution{display:none!important;}
@keyframes mapPulse{0%,100%{box-shadow:0 0 0 0 rgba(232,68,26,.6);}70%{box-shadow:0 0 0 8px rgba(232,68,26,0);}}
@keyframes mapRing{0%{transform:translate(-50%,-50%) scale(1);opacity:.4;}100%{transform:translate(-50%,-50%) scale(2);opacity:0;}}
.map-outer{background:#050d1a;border:2px solid var(--border);overflow:hidden;position:relative;}
.map-toolbar{display:flex;align-items:center;justify-content:space-between;padding:14px 24px;background:rgba(0,0,0,.4);border-bottom:1px solid rgba(255,255,255,.06);flex-wrap:wrap;gap:8px;}
.map-view-btns{display:flex;gap:4px;flex-wrap:wrap;}
.map-view-btn{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);color:#aaa;padding:5px 11px;font-family:monospace;font-size:.63rem;letter-spacing:.4px;border-radius:4px;cursor:pointer;transition:all .18s;white-space:nowrap;}
.map-view-btn:hover{background:rgba(232,68,26,.15);border-color:rgba(232,68,26,.4);color:#e8441a;}
.map-view-btn.active{background:rgba(232,68,26,.22);border-color:#e8441a;color:#f2ede6;font-weight:600;}
.map-legend{display:flex;gap:14px;align-items:center;}
.map-legend-item{display:flex;align-items:center;gap:6px;font-family:'Space Mono',monospace;font-size:.58rem;color:#aaa;letter-spacing:.5px;}
.map-legend-dot{width:10px;height:10px;border-radius:50%;}
.map-wrap{position:relative;height:480px;overflow:hidden;}
#world-svg{width:100%;height:100%;}
.map-city-dot{cursor:pointer;transition:r .2s,opacity .2s;}
.map-city-dot:hover{opacity:.8;}
.map-city-label{font-family:'Space Mono',monospace;font-size:9px;fill:#f2ede6;pointer-events:none;opacity:0;transition:opacity .2s;}
.map-city-group:hover .map-city-label{opacity:1;}
.map-tooltip{position:absolute;background:rgba(5,13,26,.95);border:1px solid var(--accent);color:#f2ede6;padding:10px 14px;font-family:'Space Mono',monospace;font-size:.65rem;border-radius:4px;pointer-events:none;display:none;z-index:50;white-space:nowrap;line-height:1.8;min-width:160px;}
.map-tooltip-city{font-size:.8rem;font-weight:700;color:var(--accent);margin-bottom:4px;}
.map-zoom-btns{display:flex;gap:6px;}
.map-zoom-btn{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.15);color:#f2ede6;width:30px;height:30px;cursor:pointer;font-size:1rem;border-radius:4px;display:flex;align-items:center;justify-content:center;transition:background .2s;}
.map-zoom-btn:hover{background:var(--accent);}

/* ── ADD CITY ── */
.add-city-section{margin-bottom:60px;}
.add-city-form{display:flex;gap:12px;flex-wrap:wrap;align-items:flex-end;}
.form-group{display:flex;flex-direction:column;gap:6px;}
.form-label{font-family:'Space Mono',monospace;font-size:.6rem;letter-spacing:2px;color:var(--muted);text-transform:uppercase;}
.form-input{background:var(--card-bg);border:2px solid var(--border);padding:10px 14px;font-family:'Space Mono',monospace;font-size:.75rem;color:var(--ink);outline:none;transition:border .2s;border-radius:4px;}
.form-input:focus{border-color:var(--accent);}
.btn-add{background:var(--accent);color:white;border:none;padding:10px 20px;font-family:'Space Mono',monospace;font-size:.72rem;letter-spacing:1px;cursor:pointer;border-radius:4px;transition:background .2s;}
.btn-add:hover{background:#c93a15;}
.add-msg{font-family:'Space Mono',monospace;font-size:.7rem;color:var(--accent);margin-top:8px;}

/* ── FOOTER ── */
footer{background:#0a0a0f;color:#f2ede6;padding:40px;display:flex;justify-content:space-between;align-items:center;border-top:3px solid var(--accent);}
.footer-logo{font-family:'Bebas Neue',sans-serif;font-size:2rem;letter-spacing:3px;}
.footer-logo span{color:var(--accent);}
.footer-info{font-family:'Space Mono',monospace;font-size:.65rem;color:#666;text-align:right;line-height:2;}

/* ── ANIMATIONS ── */
@keyframes fadeUp{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}

/* ── ANIMATED BG ── */
.weather-bg{position:absolute;inset:0;overflow:hidden;pointer-events:none;z-index:0;}
.featured-card > *{position:relative;z-index:1;}
.rain-drop{position:absolute;width:2px;background:linear-gradient(transparent,rgba(79,195,247,.6));animation:rain-fall linear infinite;border-radius:2px;}
@keyframes rain-fall{0%{transform:translateY(-20px);opacity:0}10%{opacity:1}90%{opacity:.7}100%{transform:translateY(500px);opacity:0}}
.snow-flake{position:absolute;color:white;animation:snow-fall linear infinite;font-size:12px;}
@keyframes snow-fall{0%{transform:translateY(-20px) rotate(0deg);opacity:0}10%{opacity:1}100%{transform:translateY(500px) rotate(360deg);opacity:0}}
.sun-ray{position:absolute;top:30px;right:60px;width:80px;height:80px;background:radial-gradient(circle,rgba(255,200,0,.3) 0%,transparent 70%);border-radius:50%;animation:sun-pulse 3s ease-in-out infinite;}
@keyframes sun-pulse{0%,100%{transform:scale(1);opacity:.6}50%{transform:scale(1.4);opacity:1}}
.cloud-drift{position:absolute;font-size:3rem;animation:cloud-move linear infinite;opacity:.15;}
@keyframes cloud-move{0%{transform:translateX(-100px)}100%{transform:translateX(calc(100vw + 100px))}}

/* ── MOBILE ── */
@media(max-width:768px){
  main{padding:20px;}
  .featured-card{grid-template-columns:1fr;padding:30px;}
  .featured-temp{font-size:6rem;text-align:left;}
  .featured-city{font-size:3rem;}
  .forecast-strip{grid-template-columns:repeat(4,1fr);}
  header{padding:0 20px;}
  .tagline{display:none;}
  .toolbar{padding:10px 16px;}
  .clocks-bar{padding:8px 16px;}
  .compare-grid{grid-template-columns:1fr;}
  footer{flex-direction:column;gap:20px;text-align:center;}
  footer .footer-info{text-align:center;}
  .stats-row{gap:16px;}
  .map-wrap{height:260px;}
}

/* Emoji font */
img.emoji{height:1.2em;width:1.2em;vertical-align:middle;display:inline-block;}
.flag-emoji img.emoji,.clock-flag img.emoji{height:1.4em;width:1.4em;}
</style>
</head>
<body>

<!-- LOADER -->
<div id="page-loader" style="position:fixed;inset:0;background:#0a0a0f;display:flex;flex-direction:column;align-items:center;justify-content:center;z-index:9999;transition:opacity .5s;">
  <div style="font-family:'Bebas Neue',sans-serif;font-size:3rem;color:#f2ede6;letter-spacing:4px;">AHOY Weather<span style="color:#e8441a">Drift</span></div>
  <div style="font-family:monospace;font-size:.8rem;color:#8a8070;margin-top:16px;letter-spacing:2px;">LOADING GLOBAL WEATHER...</div>
  <div style="margin-top:24px;width:200px;height:3px;background:#1a1a1f;border-radius:2px;overflow:hidden;">
    <div style="height:100%;background:#e8441a;border-radius:2px;animation:load-bar 2s ease-in-out infinite;"></div>
  </div>
  <style>@keyframes load-bar{0%{width:0%;margin-left:0}50%{width:60%;margin-left:20%}100%{width:0%;margin-left:100%}}</style>
</div>
<script>window.addEventListener('load',()=>{setTimeout(()=>{const l=document.getElementById('page-loader');if(l){l.style.opacity='0';setTimeout(()=>l.remove(),500);}},800);});</script>

<!-- ALERT BAR -->
<div class="alert-bar" id="alert-bar">
  <span>⚠️</span>
  <span id="alert-text">Weather alert active</span>
  <button onclick="document.getElementById('alert-bar').classList.remove('show')" style="margin-left:auto;background:none;border:none;color:white;cursor:pointer;font-size:1rem;">✕</button>
</div>

<header>
  <div class="logo-block">
    <div>
      <div class="logo">AHOY Weather<span>Drift</span></div>
      <div class="tagline">Global Atmospheric Intelligence</div>
    </div>
  </div>
  <div class="header-meta">
    <div class="live-badge"><span class="live-dot"></span> LIVE</div>
    <div>{{ datetime }}</div>
    <div>{{ total_cities }} cities monitored</div>
    <div id="last-updated-label" style="color:#e8441a;font-size:.6rem;">Last updated: {{ last_updated }}</div>
  </div>
</header>

<!-- TOOLBAR -->
<div class="toolbar">
  <div class="search-wrap">
    <span class="search-icon">🔍</span>
    <input type="text" id="city-search" placeholder="Search any city..." autocomplete="off" oninput="handleSearch(this.value)">
    <div id="search-results"></div>
  </div>
  <button class="toolbar-btn" id="unit-btn" onclick="toggleUnit()">°C / °F</button>
  <button class="toolbar-btn" id="dark-btn" onclick="toggleDark()">🌙 Dark</button>
  <button class="toolbar-btn" id="compare-btn" onclick="toggleCompare()">⚖️ Compare</button>
  <button class="toolbar-btn" onclick="toggleNotifications()">🔔 Alerts</button>
</div>

<!-- CLOCKS -->
<div class="clocks-bar">
  <div class="clock-item"><span class="clock-flag">🇮🇳</span><div class="clock-info"><span class="clock-country">India (IST)</span><span class="clock-time" id="clock-IN">--:--:--</span><span class="clock-date" id="date-IN">---</span></div></div>
  <div class="clock-item"><span class="clock-flag">🇯🇵</span><div class="clock-info"><span class="clock-country">Japan (JST)</span><span class="clock-time" id="clock-JP">--:--:--</span><span class="clock-date" id="date-JP">---</span></div></div>
  <div class="clock-item"><span class="clock-flag">🇷🇺</span><div class="clock-info"><span class="clock-country">Russia (MSK)</span><span class="clock-time" id="clock-RU">--:--:--</span><span class="clock-date" id="date-RU">---</span></div></div>
  <div class="clock-item"><span class="clock-flag">🇿🇦</span><div class="clock-info"><span class="clock-country">S.Africa (SAST)</span><span class="clock-time" id="clock-ZA">--:--:--</span><span class="clock-date" id="date-ZA">---</span></div></div>
  <div class="clock-item"><span class="clock-flag">🌐</span><div class="clock-info"><span class="clock-country">UTC</span><span class="clock-time" id="clock-UTC">--:--:--</span><span class="clock-date" id="date-UTC">---</span></div></div>
</div>

<!-- TICKER -->
<div class="ticker-wrap">
  <div class="ticker" id="ticker">
    {% for w in weather_data %}
    <span class="ticker-item">{{ w.icon }} {{ w.city }} {{ w.temp }}°C · {{ w.condition }}</span>
    {% endfor %}
    {% for w in weather_data %}
    <span class="ticker-item">{{ w.icon }} {{ w.city }} {{ w.temp }}°C · {{ w.condition }}</span>
    {% endfor %}
  </div>
</div>

<main>

<!-- COMPARE PANEL -->
<div class="compare-panel" id="compare-panel">
  <div class="section-label">⚖️ City Comparison</div>
  <div class="compare-grid">
    <div>
      <select class="compare-select" id="compare-a" onchange="loadCompare()">
        {% for w in weather_data %}<option value="{{ w.city }}">{{ w.city }}</option>{% endfor %}
      </select>
      <div id="compare-a-data"></div>
    </div>
    <div>
      <select class="compare-select" id="compare-b" onchange="loadCompare()">
        {% for w in weather_data %}<option value="{{ w.city }}" {% if loop.index == 2 %}selected{% endif %}>{{ w.city }}</option>{% endfor %}
      </select>
      <div id="compare-b-data"></div>
    </div>
  </div>
</div>

<!-- FEATURED -->
<section class="featured-section">
  <div class="section-label">Featured City <span id="featured-loading" style="display:none;color:var(--accent);font-size:.7rem;">· Loading...</span></div>
  <div class="featured-card" id="featured-card">
    <div class="weather-bg" id="weather-bg"></div>
    <div>
      <div class="featured-icon" id="feat-icon">{{ featured.icon }}</div>
      <div class="featured-city" id="feat-city">{{ featured.city }}</div>
      <div style="display:flex;align-items:center;gap:10px;">
        <div class="featured-country" id="feat-country">{% set cn = {"IN":"🇮🇳 India","JP":"🇯🇵 Japan","RU":"🇷🇺 Russia","ZA":"🇿🇦 South Africa"} %}{{ cn.get(featured.country, featured.country) }} · Updated just now</div>
        <span id="preview-badge" style="display:none;align-items:center;gap:5px;background:rgba(232,68,26,.2);border:1px solid var(--accent);color:var(--accent);font-family:'Space Mono',monospace;font-size:.55rem;padding:2px 8px;letter-spacing:1px;border-radius:2px;">👁 PREVIEW ONLY</span>
      </div>
      <div class="featured-condition" id="feat-condition">{{ featured.condition }} — Feels like {{ featured.feels_like }}°C</div>

      <!-- AQI -->
      <div class="aqi-row">
        <div class="aqi-bar-wrap"><div class="aqi-bar-fill" id="feat-aqi-bar" style="width:{{ [featured.aqi/300*100,100]|min }}%;background:{{ featured.aqi_color }};"></div></div>
        <span class="aqi-label-text" id="feat-aqi-label" style="color:{{ featured.aqi_color }};">AQI {{ featured.aqi }} · {{ featured.aqi_label }}</span>
      </div>

      <!-- Sun times -->
      <div class="sun-row">
        <div class="sun-item">🌅 Sunrise <span id="feat-sunrise">{{ featured.sunrise }}</span></div>
        <div class="sun-item">🌇 Sunset <span id="feat-sunset">{{ featured.sunset }}</span></div>
      </div>

      <!-- Rain gauge -->
      <div class="rain-row">
        <div class="rain-gauge">
          <svg width="60" height="60" viewBox="0 0 60 60">
            <circle cx="30" cy="30" r="24" fill="none" stroke="rgba(255,255,255,.1)" stroke-width="5"/>
            <circle cx="30" cy="30" r="24" fill="none" stroke="#4fc3f7" stroke-width="5"
              stroke-dasharray="{{ featured.rain_prob * 1.507 }} 150.7"
              stroke-linecap="round" id="feat-rain-circle"/>
          </svg>
          <div class="rain-pct" id="feat-rain-pct">{{ featured.rain_prob }}%</div>
        </div>
        <div style="font-family:'Space Mono',monospace;font-size:.65rem;color:#aaa;">Rain<br>Probability</div>
      </div>

      <div class="stats-row">
        <div class="stat"><span class="stat-label">Humidity</span><span class="stat-value" id="feat-humidity">{{ featured.humidity }}%</span></div>
        <div class="stat"><span class="stat-label">Wind</span><span class="stat-value" id="feat-wind">{{ featured.wind_speed }} km/h</span></div>
        <div class="stat"><span class="stat-label">UV Index</span><span class="stat-value" id="feat-uv">{{ featured.uv_index }}</span></div>
        <div class="stat"><span class="stat-label">Pressure</span><span class="stat-value" id="feat-pressure">{{ featured.pressure }} hPa</span></div>
        <div class="stat"><span class="stat-label">Visibility</span><span class="stat-value" id="feat-visibility">{{ featured.visibility }} km</span></div>
      </div>

      <!-- Hourly forecast -->
      <div class="hourly-strip" id="hourly-strip">
        {% for h in featured.hourly %}
        <div class="hour-block">
          <div class="hour-time">{{ h.hour }}</div>
          <div class="hour-icon">{{ h.icon }}</div>
          <div class="hour-temp">{{ h.temp }}°</div>
          <div class="hour-rain">💧{{ h.rain }}%</div>
        </div>
        {% endfor %}
      </div>

      <div class="action-bar">
        <button class="action-btn btn-whatsapp" onclick="shareWhatsApp()">💬 WhatsApp</button>
        <button class="action-btn btn-twitter"  onclick="shareTwitter()">🐦 Share</button>
        <button class="action-btn btn-download" onclick="downloadCard()">⬇️ Download</button>
      </div>
    </div>
    <div>
      <div class="featured-temp" id="feat-temp">{{ featured.temp }}°</div>
      <div class="featured-unit" id="feat-unit">Celsius</div>
    </div>
  </div>
</section>

<!-- HISTORY CHART -->
<section class="history-section">
  <div class="section-label">📈 Temperature History — <span id="history-city-label">{{ featured.city }}</span></div>
  <div class="chart-outer">
    <div class="chart-toolbar">
      <div class="chart-title">Live Temperature Trend</div>
      <div class="chart-tabs">
        <button class="chart-tab active" onclick="setChartMode('temp',this)">🌡 Temp</button>
        <button class="chart-tab" onclick="setChartMode('humidity',this)">💧 Humidity</button>
        <button class="chart-tab" onclick="setChartMode('wind',this)">💨 Wind</button>
      </div>
    </div>
    <div class="chart-stats-row">
      <div class="chart-stat"><div class="chart-stat-label">Current</div><div class="chart-stat-value" id="cs-current">--°</div></div>
      <div class="chart-stat"><div class="chart-stat-label">High</div><div class="chart-stat-value" id="cs-high" style="color:#f44336;">--°</div></div>
      <div class="chart-stat"><div class="chart-stat-label">Low</div><div class="chart-stat-value" id="cs-low" style="color:#2196f3;">--°</div></div>
      <div class="chart-stat"><div class="chart-stat-label">Average</div><div class="chart-stat-value" id="cs-avg" style="color:#aaa;">--°</div></div>
    </div>
    <div class="chart-canvas-wrap">
      <canvas id="history-chart"></canvas>
    </div>
    <div class="chart-legend">
      <div class="legend-item"><div class="legend-dot" style="background:#e8441a;"></div>Temperature</div>
      <div class="legend-item"><div class="legend-dot" style="background:#f44336;"></div>High</div>
      <div class="legend-item"><div class="legend-dot" style="background:#2196f3;"></div>Low</div>
    </div>
  </div>
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
      <div class="forecast-rain-bar"><div class="forecast-rain-fill" style="width:{{ day.rain }}%"></div></div>
    </div>
    {% endfor %}
  </div>
</section>

<!-- WORLD MAP -->
<section class="map-section">
  <div class="section-label">🗺️ World Weather Map</div>
  <div class="map-outer" style="isolation:isolate;">
    <div class="map-toolbar" style="flex-direction:column;align-items:stretch;gap:10px;">
      <!-- Row 1: view toggles + search + zoom -->
      <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;">
        <div class="map-view-btns">
          <button class="map-view-btn active" onclick="setMapView('dark')"      id="mv-dark">🌑 Dark</button>
          <button class="map-view-btn"        onclick="setMapView('satellite')" id="mv-satellite">🛰️ Satellite</button>
          <button class="map-view-btn"        onclick="setMapView('street')"    id="mv-street">🗺️ Street</button>
          <button class="map-view-btn"        onclick="setMapView('topo')"      id="mv-topo">⛰️ Terrain</button>
          <button class="map-view-btn"        onclick="setMapView('light')"     id="mv-light">☀️ Light</button>
          <button class="map-view-btn"        onclick="setMapView('watercolor')" id="mv-watercolor">🎨 Watercolor</button>
        </div>
        <div style="display:flex;gap:6px;align-items:center;">
          <div style="position:relative;">
            <input id="map-search-input" type="text" placeholder="Search location..."
              style="background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.15);
                     color:#f2ede6;padding:6px 32px 6px 12px;font-family:monospace;font-size:.68rem;
                     border-radius:4px;outline:none;width:200px;letter-spacing:.5px;"
              oninput="mapSearchDebounce(this.value)"
              onkeydown="if(event.key==='Enter') mapSearchGo()">
            <button onclick="mapSearchGo()" style="position:absolute;right:6px;top:50%;transform:translateY(-50%);
              background:none;border:none;color:#e8441a;cursor:pointer;font-size:.85rem;">🔍</button>
            <div id="map-search-results" style="display:none;position:absolute;top:100%;left:0;right:0;
              background:#1a1a22;border:1px solid rgba(255,255,255,.12);border-radius:4px;
              z-index:2000;max-height:200px;overflow-y:auto;margin-top:2px;"></div>
          </div>
          <div class="map-zoom-btns">
            <button class="map-zoom-btn" onclick="_leafletMap && _leafletMap.zoomIn()" title="Zoom in">+</button>
            <button class="map-zoom-btn" onclick="_leafletMap && _leafletMap.zoomOut()" title="Zoom out">−</button>
            <button class="map-zoom-btn" onclick="mapReset()" title="Reset view">⌂</button>
          </div>
        </div>
      </div>
      <!-- Row 2: temperature legend -->
      <div class="map-legend">
        <div class="map-legend-item"><div class="map-legend-dot" style="background:#f44336;"></div>&gt;35°C</div>
        <div class="map-legend-item"><div class="map-legend-dot" style="background:#ff9800;"></div>26–35°C</div>
        <div class="map-legend-item"><div class="map-legend-dot" style="background:#4caf50;"></div>16–25°C</div>
        <div class="map-legend-item"><div class="map-legend-dot" style="background:#2196f3;"></div>6–15°C</div>
        <div class="map-legend-item"><div class="map-legend-dot" style="background:#9c27b0;"></div>&lt;6°C</div>
      </div>
    </div>
    <!-- Leaflet map container -->
    <div id="map-wrap" style="height:480px;width:100%;background:#050d1a;"></div>
    <div style="font-family:monospace;font-size:.58rem;color:#444;padding:4px 8px;text-align:right;">
      Click anywhere on the map to get live weather · © OpenStreetMap contributors
    </div>
  </div>
</section>

<!-- CITY CARDS -->
<section>
  {% for group in country_groups %}
  <section data-country-name="{{ group.name }}">
  <div class="section-label" style="margin-top:40px;">
    <span class="flag-emoji">{{ group.flag }}</span> {{ group.name }}
  </div>
  <div class="city-grid" id="grid-{{ group.code }}">
    {% for w in group.cities %}
    <div class="city-card" onclick="selectCity(this.dataset.city)" data-city="{{ w.city }}" data-temp-c="{{ w.temp }}" data-country="{{ w.country }}">
      <button class="city-delete-btn" onclick="event.stopPropagation();deleteCity(this.closest('.city-card').dataset.city)" title="Remove city">✕</button>
      <div class="city-header">
        <div>
          <div class="city-name">{{ w.city }}</div>
          <div class="city-country">{{ group.name }}</div>
        </div>
        <div class="city-icon">{{ w.icon }}</div>
      </div>
      <div class="city-temp">{{ w.temp }}°</div>
      <div class="city-condition">{{ w.condition }}</div>
      <div class="city-badges">
        <span class="badge badge-aqi">AQI {{ w.aqi }}</span>
        <span class="badge badge-rain">💧{{ w.rain_prob }}%</span>
      </div>
      <div class="card-stats">
        <div><div class="card-stat-label">Humidity</div><div class="card-stat-value">{{ w.humidity }}%</div></div>
        <div><div class="card-stat-label">Wind</div><div class="card-stat-value">{{ w.wind_speed }} km/h</div></div>
        <div><div class="card-stat-label">UV</div><div class="card-stat-value">{{ w.uv_index }}</div></div>
        <div><div class="card-stat-label">Pressure</div><div class="card-stat-value">{{ w.pressure }}</div></div>
      </div>
    </div>
    {% endfor %}
  </div>
  </section>
  {% endfor %}
</section>

<!-- ADD CUSTOM CITY -->
<!-- RESTORE CITIES -->
<section class="add-city-section" id="restore-section" style="margin-top:60px;display:none;">
  <div class="section-label">♻️ Restore Removed Cities</div>
  <div style="background:var(--card-bg);border:2px solid var(--border);padding:24px;">
    <div id="restore-list" style="display:flex;flex-wrap:wrap;gap:10px;"></div>
    <div id="restore-empty" style="font-family:monospace;font-size:.7rem;color:#666;">No cities have been removed.</div>
  </div>
</section>

<section class="add-city-section" style="margin-top:60px;">
  <div class="section-label">➕ Add Location</div>
  <div style="background:var(--card-bg);border:2px solid var(--border);padding:30px;">

    <!-- Mode toggle -->
    <div style="display:flex;gap:8px;margin-bottom:20px;flex-wrap:wrap;">
      <button class="chart-tab active" id="mode-search" onclick="setAddMode('search')">🔍 Quick Search</button>
      <button class="chart-tab" id="mode-browse" onclick="setAddMode('browse')">🗂 Browse by Region</button>
    </div>

    <!-- QUICK SEARCH MODE -->
    <div id="add-mode-search">
      <div style="font-family:'Space Mono',monospace;font-size:.68rem;color:var(--muted);margin-bottom:16px;letter-spacing:1px;">
        Search any city, town, village, hamlet or rural area worldwide.
      </div>
      <div class="add-city-form">
        <div class="form-group" style="flex:1;min-width:220px;position:relative;">
          <label class="form-label">Place Name</label>
          <input class="form-input" id="add-city-name" placeholder="e.g. Korlakota, Naupada, Etcherla..."
            type="text" autocomplete="off" oninput="geocodeSearch(this.value)" style="width:100%;">
          <div id="geocode-results" style="
            display:none;position:absolute;top:100%;left:0;right:0;
            background:#1a1a22;border:1px solid rgba(255,255,255,.12);
            border-radius:4px;z-index:300;max-height:260px;overflow-y:auto;margin-top:2px;">
          </div>
        </div>
        <div class="form-group" style="min-width:110px;">
          <label class="form-label">Lat (auto)</label>
          <input class="form-input" id="add-city-lat" placeholder="Auto" type="text" readonly
            style="width:110px;background:rgba(0,0,0,.1);color:var(--muted);cursor:not-allowed;">
        </div>
        <div class="form-group" style="min-width:110px;">
          <label class="form-label">Lon (auto)</label>
          <input class="form-input" id="add-city-lon" placeholder="Auto" type="text" readonly
            style="width:110px;background:rgba(0,0,0,.1);color:var(--muted);cursor:not-allowed;">
        </div>
        <button class="btn-add" id="add-city-btn" onclick="addCustomCity()" disabled
          style="opacity:.5;cursor:not-allowed;">+ Add</button>
      </div>
    </div>

    <!-- BROWSE MODE -->
    <div id="add-mode-browse" style="display:none;">
      <div style="font-family:'Space Mono',monospace;font-size:.68rem;color:var(--muted);margin-bottom:16px;letter-spacing:1px;">
        Drill down: Country → State → District → Sub-District → Mandal → Village
      </div>

      <!-- Breadcrumb trail -->
      <div id="hier-breadcrumb" style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:16px;min-height:28px;align-items:center;">
        <span style="font-family:'Space Mono',monospace;font-size:.62rem;color:#666;">Start typing to explore...</span>
      </div>

      <!-- Search within level -->
      <div style="position:relative;margin-bottom:12px;">
        <input class="form-input" id="hier-search" placeholder="Search within current level..." type="text"
          oninput="hierSearch(this.value)" style="width:100%;max-width:400px;">
      </div>

      <!-- Results list -->
      <div id="hier-results" style="
        background:var(--paper);border:1px solid var(--border);border-radius:4px;
        max-height:320px;overflow-y:auto;">
        <div id="hier-results-inner" style="padding:8px 0;">
          <div style="padding:12px 16px;font-family:monospace;font-size:.68rem;color:#666;">
            Type a country, state or district name to begin browsing.
          </div>
        </div>
      </div>

      <!-- Selected location display -->
      <div id="hier-selected" style="display:none;margin-top:16px;padding:16px;background:rgba(232,68,26,.08);border:1px solid rgba(232,68,26,.3);border-radius:4px;">
        <div style="font-family:'Space Mono',monospace;font-size:.62rem;color:#e8441a;letter-spacing:1px;margin-bottom:6px;">SELECTED LOCATION</div>
        <div id="hier-selected-name" style="font-family:'Bebas Neue',sans-serif;font-size:1.8rem;color:var(--ink);letter-spacing:2px;"></div>
        <div id="hier-selected-path" style="font-family:'Space Mono',monospace;font-size:.6rem;color:var(--muted);margin-top:4px;"></div>
        <div style="display:flex;gap:10px;margin-top:12px;flex-wrap:wrap;">
          <button class="btn-add" id="hier-add-btn" onclick="addHierCity()">+ Add to Weather List</button>
          <button class="action-btn btn-twitter" onclick="previewHierCity()" style="font-size:.68rem;">👁 Preview Weather</button>
        </div>
      </div>
    </div>

    <div id="add-msg" class="add-msg" style="display:none;margin-top:12px;"></div>
  </div>
</section>

</main>

<footer>
  <div class="footer-logo">AHOY Weather<span>Drift</span></div>
  <div class="footer-info">
    <div>Powered by Open-Meteo · Flask · Python</div>
    <div>Data: ECMWF · NOAA GFS · DWD ICON</div>
    <div>Refreshes every 60 seconds</div>
  </div>
</footer>

<script>
// ── State ──────────────────────────────────────────────────────────────────
let currentCity = null;
let isCelsius = true;
let allCities = [];
let historyData = {};   // UNUSED — kept for compat
const histData = {};   // city -> [{t, temp, humidity, wind}]  ← single source of truth
const COUNTRY_NAMES = {IN:'🇮🇳 India',JP:'🇯🇵 Japan',RU:'🇷🇺 Russia',ZA:'🇿🇦 South Africa',CUSTOM:'🌍 Custom'};

function safe(v, s='') { return (v!==undefined && v!==null) ? v+s : '—'; }
function toF(c) { return Math.round(c*9/5+32); }
function dispTemp(c) { if(c==='—'||c===null||c===undefined) return '—'; return isCelsius ? c+'°' : toF(Number(c))+'°'; }
function unitLabel() { return isCelsius ? 'Celsius' : 'Fahrenheit'; }

// ── Dark mode ──────────────────────────────────────────────────────────────
function toggleDark() {
  document.body.classList.toggle('dark');
  const on = document.body.classList.contains('dark');
  document.getElementById('dark-btn').textContent = on ? '☀️ Light' : '🌙 Dark';
  document.getElementById('dark-btn').classList.toggle('active', on);
  localStorage.setItem('wd-dark', on);
}
if (localStorage.getItem('wd-dark')==='true') {
  document.body.classList.add('dark');
  document.getElementById('dark-btn').textContent = '☀️ Light';
  document.getElementById('dark-btn').classList.add('active');
}

// ── Unit toggle ────────────────────────────────────────────────────────────
function toggleUnit() {
  isCelsius = !isCelsius;
  document.getElementById('unit-btn').textContent = isCelsius ? '°C / °F' : '°F / °C';
  document.getElementById('feat-unit').textContent = unitLabel();
  const rawC = parseFloat(document.getElementById('feat-temp').dataset.rawc);
  if (!isNaN(rawC)) document.getElementById('feat-temp').textContent = dispTemp(rawC);
  document.querySelectorAll('.city-card').forEach(card => {
    const c = parseFloat(card.dataset.tempC);
    const el = card.querySelector('.city-temp');
    if (!isNaN(c) && el) el.textContent = dispTemp(c);
  });
  updateTicker(allCities);
}

// ── Clocks ─────────────────────────────────────────────────────────────────
const TZ = {IN:'Asia/Kolkata',JP:'Asia/Tokyo',RU:'Europe/Moscow',ZA:'Africa/Johannesburg',UTC:'UTC'};
function updateClocks() {
  const now = new Date();
  for (const [code, tz] of Object.entries(TZ)) {
    try {
      const t = document.getElementById('clock-'+code);
      const d = document.getElementById('date-'+code);
      if(t) t.textContent = now.toLocaleTimeString('en-GB',{timeZone:tz,hour12:false});
      if(d) d.textContent = now.toLocaleDateString('en-GB',{timeZone:tz,weekday:'short',day:'2-digit',month:'short'});
    } catch(e) {
      const t = document.getElementById('clock-'+code);
      const d = document.getElementById('date-'+code);
      if(t) t.textContent = now.toTimeString().slice(0,8);
      if(d) d.textContent = now.toDateString().slice(0,10);
    }
  }
}
updateClocks(); setInterval(updateClocks, 1000);

// ── Search bar — global city search via Nominatim ─────────────────────────
let _searchTimer  = null;
let _searchResults = [];

function handleSearch(q) {
  clearTimeout(_searchTimer);
  const box = document.getElementById('search-results');
  if (!q || !q.trim()) { box.style.display='none'; return; }
  box.style.display='block';

  const ql = q.toLowerCase();
  const local = allCities.filter(c => c.city && c.city.toLowerCase().includes(ql)).slice(0, 4);

  const localHtml = () => local.map(c => {
    const flag = {IN:'🇮🇳',JP:'🇯🇵',RU:'🇷🇺',ZA:'🇿🇦'}[c.country] || '🌍';
    return `<div class="search-result-item" onclick="selectCity(this.dataset.city);document.getElementById('city-search').value='';document.getElementById('search-results').style.display='none';" data-city="${c.city}">
      <span>${flag} ${c.city}</span>
      <span style="color:#e8441a;font-size:.62rem;font-weight:700;">${c.temp!==undefined ? dispTemp(c.temp) : ''}</span>
    </div>`;
  }).join('');

  box.innerHTML = (local.length ? localHtml() : '') +
    `<div style="padding:6px 14px;font-family:monospace;font-size:.6rem;color:#555;border-top:1px solid rgba(255,255,255,.05);">🔍 Searching...</div>`;

  _searchTimer = setTimeout(() => {
    fetch('/api/geocode?q=' + encodeURIComponent(q))
      .then(r => r.json())
      .then(data => {
        _searchResults = data.results || [];
        const TYPE_COLOR = {'City':'#e8441a','Town':'#ff9800','Village':'#4caf50','Hamlet':'#66bb6a','Suburb':'#2196f3','Locality':'#00bcd4','Neighbourhood':'#9c27b0','Municipality':'#ff9800'};
        const TYPE_ICON  = {'City':'🏙️','Town':'🏘️','Village':'🏡','Hamlet':'🛖','Suburb':'🏠','Locality':'📍','Neighbourhood':'🏘️'};
        const globalResults = _searchResults.filter(r => !local.some(l => l.city.toLowerCase() === r.name.toLowerCase())).slice(0, 7);
        const globalHtml = globalResults.map((r, i) => {
          const flag  = r.country_code === 'IN' ? '🇮🇳' : '🌍';
          const color = TYPE_COLOR[r.place_type] || '#888';
          const icon  = TYPE_ICON[r.place_type]  || '📍';
          const sub   = r.district
            ? `<div style="font-size:.56rem;color:#666;margin-top:1px;">${r.district}${r.state ? ', '+r.state : ''}</div>`
            : (r.state ? `<div style="font-size:.56rem;color:#666;margin-top:1px;">${r.state}</div>` : '');
          return `<div class="search-result-item" style="flex-direction:column;align-items:flex-start;gap:1px;" onclick="searchSelectCity(${i})">
            <div style="display:flex;justify-content:space-between;align-items:center;width:100%;">
              <span style="font-weight:600;">${flag} ${r.name}</span>
              <span style="color:${color};font-size:.56rem;font-weight:700;white-space:nowrap;flex-shrink:0;">${icon} ${r.place_type||'Place'}</span>
            </div>
            ${sub}
          </div>`;
        }).join('');
        const sep = local.length && globalResults.length
          ? `<div style="padding:3px 14px;font-family:monospace;font-size:.56rem;color:#444;background:rgba(255,255,255,.03);letter-spacing:1px;">── MORE RESULTS ──</div>`
          : '';
        box.innerHTML = localHtml() + sep + (globalHtml || (!local.length ? `<div style="padding:10px 14px;font-family:monospace;font-size:.65rem;color:#666;">No results — try adding district or state name</div>` : ''));
        box.style.display = 'block';
      })
      .catch(() => {
        if (!local.length) box.innerHTML = `<div style="padding:10px 14px;font-family:monospace;font-size:.65rem;color:#f44336;">Search unavailable.</div>`;
      });
  }, 350);
}
// Called when user clicks a worldwide (non-list) search result
function searchSelectCity(idx) {
  const r = _searchResults[idx]; if (!r) return;
  document.getElementById('city-search').value = '';
  document.getElementById('search-results').style.display = 'none';
  document.getElementById('featured-loading').style.display = 'inline';
  document.querySelector('.featured-section').scrollIntoView({behavior:'smooth', block:'start'});

  // Deselect any card
  document.querySelectorAll('.city-card').forEach(c=>c.classList.remove('selected'));
  currentCity = null;   // not in list — don't track as currentCity for auto-refresh

  // Fetch live weather directly from Open-Meteo via backend
  fetch(`/api/preview?lat=${r.lat}&lon=${r.lon}&name=${encodeURIComponent(r.name)}&country=${encodeURIComponent(r.country_name||'')}`)
    .then(res=>res.json())
    .then(d=>{
      updateFeaturedPanel(d);
      updateForecast(d.city, d.forecast||[]);
      document.getElementById('featured-loading').style.display='none';
      // Show a subtle "preview" badge on featured card
      const badge = document.getElementById('preview-badge');
      if (badge) badge.style.display='inline-flex';
    })
    .catch(()=>{ document.getElementById('featured-loading').style.display='none'; });
}

document.addEventListener('click',e=>{ if(!e.target.closest('.search-wrap')) document.getElementById('search-results').style.display='none'; });

// ── Animated weather background ───────────────────────────────────────────
function setWeatherBg(condition) {
  const bg = document.getElementById('weather-bg');
  bg.innerHTML = '';
  const c = (condition||'').toLowerCase();
  if (c.includes('rain') || c.includes('drizzle') || c.includes('shower')) {
    for (let i=0;i<20;i++) {
      const d = document.createElement('div');
      d.className='rain-drop';
      d.style.cssText=`left:${Math.random()*100}%;top:0;height:${10+Math.random()*20}px;animation-duration:${0.5+Math.random()*.8}s;animation-delay:${Math.random()*2}s;opacity:${.3+Math.random()*.5}`;
      bg.appendChild(d);
    }
  } else if (c.includes('snow')) {
    for (let i=0;i<12;i++) {
      const d=document.createElement('div');
      d.className='snow-flake'; d.textContent='❄';
      d.style.cssText=`left:${Math.random()*100}%;animation-duration:${2+Math.random()*3}s;animation-delay:${Math.random()*3}s;`;
      bg.appendChild(d);
    }
  } else if (c.includes('clear') || c.includes('sunny')) {
    const d=document.createElement('div'); d.className='sun-ray'; bg.appendChild(d);
  } else if (c.includes('cloud') || c.includes('overcast')) {
    for (let i=0;i<3;i++) {
      const d=document.createElement('div'); d.className='cloud-drift'; d.textContent='☁';
      d.style.cssText=`top:${20+i*30}px;animation-duration:${15+i*8}s;animation-delay:${i*4}s;`;
      bg.appendChild(d);
    }
  } else if (c.includes('storm')) {
    for (let i=0;i<15;i++) {
      const d=document.createElement('div'); d.className='rain-drop';
      d.style.cssText=`left:${Math.random()*100}%;height:${15+Math.random()*25}px;animation-duration:${.3+Math.random()*.5}s;animation-delay:${Math.random()*1}s;background:linear-gradient(transparent,rgba(200,200,255,.8));`;
      bg.appendChild(d);
    }
  }
}

// ── Update featured panel ──────────────────────────────────────────────────
function updateFeaturedPanel(d) {
  if (!d) return;
  const cLabel = COUNTRY_NAMES[d.country] || d.country || '—';
  document.getElementById('feat-icon').textContent      = safe(d.icon);
  document.getElementById('feat-city').textContent      = safe(d.city);
  document.getElementById('feat-country').textContent   = cLabel+' · Updated just now';
  document.getElementById('feat-condition').textContent = safe(d.condition)+' — Feels like '+(isCelsius?safe(d.feels_like,'°C'):toF(d.feels_like)+'°F');
  const tempEl = document.getElementById('feat-temp');
  tempEl.textContent = dispTemp(d.temp);
  tempEl.dataset.rawc = d.temp;
  document.getElementById('feat-unit').textContent      = unitLabel();
  document.getElementById('feat-humidity').textContent  = safe(d.humidity,'%');
  document.getElementById('feat-wind').textContent      = safe(d.wind_speed,' km/h');
  document.getElementById('feat-uv').textContent        = safe(d.uv_index);
  document.getElementById('feat-pressure').textContent  = safe(d.pressure,' hPa');
  document.getElementById('feat-visibility').textContent= safe(d.visibility,' km');
  document.getElementById('feat-sunrise').textContent   = safe(d.sunrise);
  document.getElementById('feat-sunset').textContent    = safe(d.sunset);
  // AQI
  if (d.aqi !== undefined) {
    const pct = Math.min(d.aqi/300*100, 100);
    document.getElementById('feat-aqi-bar').style.width = pct+'%';
    document.getElementById('feat-aqi-bar').style.background = d.aqi_color||'#00c853';
    document.getElementById('feat-aqi-label').textContent = 'AQI '+d.aqi+' · '+(d.aqi_label||'Good');
    document.getElementById('feat-aqi-label').style.color = d.aqi_color||'#00c853';
  }
  // Rain gauge
  if (d.rain_prob !== undefined) {
    const circ = document.getElementById('feat-rain-circle');
    if (circ) circ.setAttribute('stroke-dasharray', `${d.rain_prob*1.507} 150.7`);
    document.getElementById('feat-rain-pct').textContent = d.rain_prob+'%';
  }
  // Hourly strip
  if (d.hourly && d.hourly.length) {
    document.getElementById('hourly-strip').innerHTML = d.hourly.map(h=>`
      <div class="hour-block">
        <div class="hour-time">${h.hour}</div>
        <div class="hour-icon">${h.icon}</div>
        <div class="hour-temp">${dispTemp(h.temp)}</div>
        <div class="hour-rain">💧${h.rain}%</div>
      </div>`).join('');
  }
  // Weather alerts
  checkAlerts(d);
  // Animated background
  setWeatherBg(d.condition);
  // History chart
  updateHistoryChart(d.city, d);
  if (typeof twemoji !== 'undefined') twemoji.parse(document.getElementById('featured-card'));
}

// ── Weather alerts ─────────────────────────────────────────────────────────
function checkAlerts(d) {
  const alerts = [];
  if (d.temp >= 40) alerts.push(`🌡️ Extreme heat in ${d.city}: ${d.temp}°C`);
  if (d.temp <= 0)  alerts.push(`🥶 Freezing conditions in ${d.city}: ${d.temp}°C`);
  if (d.wind_speed >= 60) alerts.push(`💨 Strong winds in ${d.city}: ${d.wind_speed} km/h`);
  if (d.rain_prob >= 80)  alerts.push(`🌧️ Heavy rain likely in ${d.city}: ${d.rain_prob}%`);
  if (d.aqi >= 150) alerts.push(`😷 Poor air quality in ${d.city}: AQI ${d.aqi}`);
  const bar = document.getElementById('alert-bar');
  if (alerts.length) {
    document.getElementById('alert-text').textContent = alerts[0];
    bar.classList.add('show');
    if (Notification.permission==='granted') {
      new Notification('AHOY WeatherDrift Alert', {body: alerts[0], icon:'🌤️'});
    }
  } else { bar.classList.remove('show'); }
}

function toggleNotifications() {
  if (Notification.permission === 'granted') {
    alert('Notifications already enabled!');
  } else {
    Notification.requestPermission().then(p => {
      if (p === 'granted') {
        new Notification('AHOY WeatherDrift', {body:'Weather alerts enabled! ✅'});
        document.getElementById('alert-bar') && document.querySelector('[onclick="toggleNotifications()"]').classList.add('active');
      }
    });
  }
}

// ── History Chart ──────────────────────────────────────────────────────────
let chartMode = 'temp';

function setChartMode(mode, btn) {
  chartMode = mode;
  document.querySelectorAll('.chart-tab').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  const city = currentCity || Object.keys(histData)[0];
  if (city && histData[city]) drawChart(histData[city]);
}

function updateHistoryChart(city, weatherObj) {
  if (!histData[city]) histData[city] = [];
  histData[city].push({
    t: new Date().toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit'}),
    temp:     typeof weatherObj === 'object' ? (weatherObj.temp     ?? 25) : weatherObj,
    humidity: typeof weatherObj === 'object' ? (weatherObj.humidity ?? 65) : 65,
    wind:     typeof weatherObj === 'object' ? (weatherObj.wind_speed ?? 12) : 12,
  });
  if (histData[city].length > 20) histData[city].shift();
  document.getElementById('history-city-label').textContent = city;
  drawChart(histData[city]);
}

function drawChart(points) {
  const canvas = document.getElementById('history-chart');
  if (!canvas) return;
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width  = rect.width  * dpr;
  canvas.height = rect.height * dpr;
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  const W = rect.width, H = rect.height;
  const isDark = document.body.classList.contains('dark');
  const PAD = {t:20, r:20, b:40, l:52};
  const cW = W - PAD.l - PAD.r;
  const cH = H - PAD.t - PAD.b;

  // Clear
  ctx.clearRect(0,0,W,H);

  if (!points || points.length < 1) {
    ctx.fillStyle = isDark ? '#555' : '#aaa';
    ctx.font = '13px monospace';
    ctx.textAlign = 'center';
    ctx.fillText('Click a city to begin tracking', W/2, H/2);
    return;
  }

  const vals = points.map(p => chartMode==='temp' ? p.temp : chartMode==='humidity' ? p.humidity : p.wind);
  const minV = Math.min(...vals);
  const maxV = Math.max(...vals);
  const range = maxV - minV || 4;
  const padV  = range * 0.2;
  const yMin  = minV - padV;
  const yMax  = maxV + padV;

  // Update stats
  const cur  = vals[vals.length-1];
  const hi   = Math.max(...vals);
  const lo   = Math.min(...vals);
  const avg  = Math.round(vals.reduce((a,b)=>a+b,0)/vals.length);
  const sfx  = chartMode==='temp' ? '°' : chartMode==='humidity' ? '%' : ' km/h';
  document.getElementById('cs-current').textContent = cur + sfx;
  document.getElementById('cs-high').textContent    = hi  + sfx;
  document.getElementById('cs-low').textContent     = lo  + sfx;
  document.getElementById('cs-avg').textContent     = avg + sfx;

  const toX = i => PAD.l + (i / Math.max(points.length-1,1)) * cW;
  const toY = v => PAD.t + cH - ((v - yMin)/(yMax - yMin)) * cH;

  // Grid lines
  const gridLines = 5;
  ctx.strokeStyle = isDark ? 'rgba(255,255,255,.05)' : 'rgba(0,0,0,.06)';
  ctx.lineWidth = 1;
  for (let i=0;i<=gridLines;i++) {
    const y = PAD.t + (i/gridLines)*cH;
    ctx.beginPath(); ctx.moveTo(PAD.l, y); ctx.lineTo(PAD.l+cW, y); ctx.stroke();
    const labelV = yMax - (yMax-yMin)*(i/gridLines);
    ctx.fillStyle = isDark ? '#666' : '#aaa';
    ctx.font = '10px monospace';
    ctx.textAlign = 'right';
    ctx.fillText(Math.round(labelV)+sfx, PAD.l-6, y+4);
  }

  // Area fill gradient
  const lineColor = chartMode==='temp' ? '#e8441a' : chartMode==='humidity' ? '#4fc3f7' : '#66bb6a';
  const fillColor = chartMode==='temp' ? 'rgba(232,68,26,.18)' : chartMode==='humidity' ? 'rgba(79,195,247,.18)' : 'rgba(102,187,106,.18)';
  const grad = ctx.createLinearGradient(0, PAD.t, 0, PAD.t+cH);
  grad.addColorStop(0, fillColor);
  grad.addColorStop(1, 'rgba(0,0,0,0)');

  // Draw gradient fill (simplified)
  ctx.beginPath();
  points.forEach((p,i) => {
    const v = chartMode==='temp'?p.temp:chartMode==='humidity'?p.humidity:p.wind;
    i===0 ? ctx.moveTo(toX(i), toY(v)) : ctx.lineTo(toX(i), toY(v));
  });
  ctx.lineTo(toX(points.length-1), PAD.t+cH);
  ctx.lineTo(PAD.l, PAD.t+cH);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  // Main line (smooth)
  ctx.beginPath();
  points.forEach((p,i) => {
    const v  = chartMode==='temp'?p.temp:chartMode==='humidity'?p.humidity:p.wind;
    const x  = toX(i), y = toY(v);
    if (i === 0) { ctx.moveTo(x,y); return; }
    const px = toX(i-1);
    const pv = chartMode==='temp'?points[i-1].temp:chartMode==='humidity'?points[i-1].humidity:points[i-1].wind;
    const py = toY(pv);
    const cpx = (px+x)/2;
    ctx.bezierCurveTo(cpx, py, cpx, y, x, y);
  });
  ctx.strokeStyle = lineColor;
  ctx.lineWidth   = 2.5;
  ctx.lineJoin    = 'round';
  ctx.stroke();

  // Dots
  points.forEach((p,i) => {
    const v = chartMode==='temp'?p.temp:chartMode==='humidity'?p.humidity:p.wind;
    const x = toX(i), y = toY(v);
    ctx.beginPath(); ctx.arc(x, y, i===points.length-1?5:3, 0, Math.PI*2);
    ctx.fillStyle = i===points.length-1 ? '#fff' : lineColor;
    ctx.strokeStyle = lineColor; ctx.lineWidth=1.5; ctx.fill(); ctx.stroke();
  });

  // Current value callout (last point)
  if (points.length > 0) {
    const lv = vals[vals.length-1];
    const lx = toX(points.length-1), ly = toY(lv);
    ctx.fillStyle = lineColor;
    ctx.beginPath();
    ctx.roundRect ? ctx.roundRect(lx-22, ly-24, 44, 20, 4) : ctx.rect(lx-22, ly-24, 44, 20);
    ctx.fill();
    ctx.fillStyle = '#fff';
    ctx.font = 'bold 10px monospace';
    ctx.textAlign = 'center';
    ctx.fillText(lv+sfx, lx, ly-10);
  }

  // X labels
  const step = Math.max(1, Math.floor(points.length/6));
  ctx.fillStyle = isDark ? '#555' : '#bbb';
  ctx.font = '9px monospace';
  ctx.textAlign = 'center';
  points.forEach((p,i) => {
    if (i % step === 0 || i===points.length-1) ctx.fillText(p.t, toX(i), PAD.t+cH+18);
  });

  // Y axis line
  ctx.strokeStyle = isDark ? 'rgba(255,255,255,.1)' : 'rgba(0,0,0,.1)';
  ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(PAD.l, PAD.t); ctx.lineTo(PAD.l, PAD.t+cH); ctx.stroke();
}

// ── World Map ──────────────────────────────────────────────────────────────
// ── Leaflet Map ───────────────────────────────────────────────────────────
let _leafletMap    = null;
let _leafletMarkers = [];
let _mapSearchTimer = null;
let _mapSearchResults = [];
let _clickMarker   = null;

function tempColor(t) {
  if (t > 35) return '#f44336';
  if (t > 25) return '#ff9800';
  if (t > 15) return '#4caf50';
  if (t >  5) return '#2196f3';
  return '#9c27b0';
}

// ── Map tile layer definitions (all free, no API key) ─────────────────────
const MAP_VIEWS = {
  dark: {
    url:  'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    opts: { subdomains: 'abcd', maxZoom: 19 },
  },
  satellite: {
    url:  'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    opts: { maxZoom: 19 },
  },
  street: {
    url:  'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    opts: { subdomains: 'abc', maxZoom: 19 },
  },
  topo: {
    url:  'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
    opts: { subdomains: 'abc', maxZoom: 17 },
  },
  light: {
    url:  'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    opts: { subdomains: 'abcd', maxZoom: 19 },
  },
  watercolor: {
    url:  'https://tiles.stadiamaps.com/tiles/stamen_watercolor/{z}/{x}/{y}.jpg',
    opts: { maxZoom: 16 },
  },
};

let _currentTileLayer = null;
let _currentView      = 'dark';

function initLeafletMap() {
  if (_leafletMap || typeof L === 'undefined') return;

  _leafletMap = L.map('map-wrap', {
    center: [20, 0],
    zoom: 2,
    minZoom: 2,
    maxZoom: 19,
    zoomControl: false,
    attributionControl: false,
  });

  // Load default dark tile layer
  const v = MAP_VIEWS['dark'];
  _currentTileLayer = L.tileLayer(v.url, v.opts).addTo(_leafletMap);

  // Click anywhere → fetch weather at that point
  _leafletMap.on('click', function(e) {
    const lat = e.latlng.lat.toFixed(5);
    const lon = e.latlng.lng.toFixed(5);
    mapClickWeather(lat, lon);
  });
}

function setMapView(viewKey) {
  if (!MAP_VIEWS[viewKey]) return;
  if (!_leafletMap) initLeafletMap();

  // Swap tile layer
  if (_currentTileLayer) _leafletMap.removeLayer(_currentTileLayer);
  const v = MAP_VIEWS[viewKey];
  _currentTileLayer = L.tileLayer(v.url, v.opts).addTo(_leafletMap);

  // Bring markers back to front
  _leafletMarkers.forEach(m => m.addTo(_leafletMap));
  if (_clickMarker) _clickMarker.addTo(_leafletMap);

  // Update active button
  _currentView = viewKey;
  document.querySelectorAll('.map-view-btn').forEach(b => b.classList.remove('active'));
  const btn = document.getElementById('mv-' + viewKey);
  if (btn) btn.classList.add('active');
}

function renderMapDots(weatherList) {
  if (typeof L === 'undefined') {
    setTimeout(() => renderMapDots(weatherList), 300);
    return;
  }
  if (!_leafletMap) initLeafletMap();

  // Clear existing markers
  _leafletMarkers.forEach(m => m.remove());
  _leafletMarkers = [];

  weatherList.forEach(w => {
    if (!w.lat || !w.lon) return;
    const color = tempColor(w.temp);
    const size  = 14;

    // Custom pulsing circle marker
    const icon = L.divIcon({
      className: '',
      html: `<div style="
        width:${size}px;height:${size}px;border-radius:50%;
        background:${color};border:2px solid #fff;
        box-shadow:0 0 0 0 ${color};
        animation:mapPulse 2s infinite;position:relative;">
        <div style="
          position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);
          width:${size+8}px;height:${size+8}px;border-radius:50%;
          border:1.5px solid ${color};opacity:.4;
          animation:mapRing 2s infinite;pointer-events:none;"></div>
      </div>`,
      iconSize: [size, size],
      iconAnchor: [size/2, size/2],
    });

    const marker = L.marker([w.lat, w.lon], {icon})
      .addTo(_leafletMap)
      .bindTooltip(`
        <div style="font-family:monospace;font-size:.7rem;line-height:1.7;min-width:150px;">
          <div style="font-weight:700;font-size:.8rem;margin-bottom:4px;">${w.icon||'🌡️'} ${w.city}</div>
          <div>🌡 ${w.temp}°C &nbsp; 💧${w.humidity||'—'}%</div>
          <div>💨 ${w.wind_speed||'—'} km/h &nbsp; UV ${w.uv_index||'—'}</div>
          <div style="color:${w.aqi_color||'#0c8'};margin-top:2px;">AQI ${w.aqi||'—'} · ${w.aqi_label||'—'}</div>
          <div style="color:#888;font-size:.58rem;margin-top:3px;">Click to select</div>
        </div>`, {
          direction: 'top',
          offset: [0, -8],
          className: 'leaflet-weather-tooltip',
        })
      .on('click', () => selectCity(w.city));

    _leafletMarkers.push(marker);
  });
}

function mapReset() {
  if (_leafletMap) _leafletMap.setView([20, 0], 2);
}

// Click anywhere on map to get weather
function mapClickWeather(lat, lon) {
  // Remove previous click marker
  if (_clickMarker) { _clickMarker.remove(); _clickMarker = null; }

  // Show loading pin
  const loadIcon = L.divIcon({
    className: '',
    html: `<div style="width:12px;height:12px;border-radius:50%;background:#e8441a;border:2px solid #fff;animation:mapPulse 1s infinite;"></div>`,
    iconSize: [12, 12], iconAnchor: [6, 6],
  });
  _clickMarker = L.marker([lat, lon], {icon: loadIcon}).addTo(_leafletMap);

  document.getElementById('featured-loading').style.display = 'inline';
  document.querySelector('.featured-section').scrollIntoView({behavior:'smooth', block:'start'});

  // Reverse geocode to get place name, then fetch weather
  const latF = parseFloat(lat), lonF = parseFloat(lon);
  const fallbackName = `${latF.toFixed(2)}°N, ${lonF.toFixed(2)}°E`;
  fetch(`/api/reverse?lat=${lat}&lon=${lon}`)
    .then(r => r.json())
    .then(geo => {
      const name    = geo.name    || fallbackName;
      const country = geo.country || '';
      return fetch(`/api/preview?lat=${lat}&lon=${lon}&name=${encodeURIComponent(name)}&country=${encodeURIComponent(country)}`);
    })
    .catch(() => fetch(`/api/preview?lat=${lat}&lon=${lon}&name=${encodeURIComponent(fallbackName)}&country=`))
    .then(r => r.json())
    .then(d => {
      updateFeaturedPanel(d);
      updateForecast(d.city, d.forecast || []);
      document.getElementById('featured-loading').style.display = 'none';
      document.querySelectorAll('.city-card').forEach(c => c.classList.remove('selected'));
      currentCity = null;
      const badge = document.getElementById('preview-badge');
      if (badge) badge.style.display = 'inline-flex';
      // Update click marker to show result
      if (_clickMarker) {
        _clickMarker.remove();
        const doneIcon = L.divIcon({
          className: '',
          html: `<div style="width:12px;height:12px;border-radius:50%;background:#4caf50;border:2px solid #fff;"></div>`,
          iconSize: [12,12], iconAnchor: [6,6],
        });
        _clickMarker = L.marker([lat, lon], {icon: doneIcon})
          .addTo(_leafletMap)
          .bindTooltip(`📍 ${d.city || name}: ${d.temp}°C`, {direction:'top', offset:[0,-8]})
          .openTooltip();
      }
    })
    .catch(() => {
      document.getElementById('featured-loading').style.display = 'none';
      if (_clickMarker) { _clickMarker.remove(); _clickMarker = null; }
    });
}

// Map search
function mapSearchDebounce(q) {
  clearTimeout(_mapSearchTimer);
  const box = document.getElementById('map-search-results');
  if (!q.trim()) { box.style.display = 'none'; return; }
  _mapSearchTimer = setTimeout(() => mapSearchGo(q), 400);
}

function mapSearchGo(q) {
  q = q || document.getElementById('map-search-input').value.trim();
  if (!q) return;
  const box = document.getElementById('map-search-results');
  box.innerHTML = `<div style="padding:8px 12px;font-family:monospace;font-size:.65rem;color:#666;">Searching...</div>`;
  box.style.display = 'block';

  fetch('/api/geocode?q=' + encodeURIComponent(q))
    .then(r => r.json())
    .then(data => {
      _mapSearchResults = data.results || [];
      if (!_mapSearchResults.length) {
        box.innerHTML = `<div style="padding:8px 12px;font-family:monospace;font-size:.65rem;color:#666;">No results found.</div>`;
        return;
      }
      box.innerHTML = _mapSearchResults.slice(0, 8).map((r, i) => `
        <div onclick="mapSearchSelect(${i})" style="
          padding:9px 12px;font-family:monospace;font-size:.68rem;color:#ccc;
          cursor:pointer;border-bottom:1px solid rgba(255,255,255,.05);
          display:flex;flex-direction:column;gap:2px;"
          onmouseover="this.style.background='rgba(232,68,26,.12)'"
          onmouseout="this.style.background='transparent'">
          <span style="font-weight:600;">${r.country_code==='IN'?'🇮🇳':'🌍'} ${r.name}</span>
          <span style="color:#555;font-size:.58rem;">${r.district ? r.district+', ':''} ${r.state||''}</span>
        </div>`).join('');
    })
    .catch(() => {
      box.innerHTML = `<div style="padding:8px 12px;font-family:monospace;font-size:.65rem;color:#f44336;">Search failed.</div>`;
    });
}

function mapSearchSelect(idx) {
  const r = _mapSearchResults[idx];
  if (!r || !_leafletMap) return;
  document.getElementById('map-search-input').value = r.name;
  document.getElementById('map-search-results').style.display = 'none';
  // Fly to location and fetch weather
  _leafletMap.flyTo([r.lat, r.lon], 12, {duration: 1.2});
  mapClickWeather(r.lat, r.lon);
}

// Close map search on outside click
document.addEventListener('click', e => {
  if (!e.target.closest('#map-search-input') && !e.target.closest('#map-search-results')) {
    const box = document.getElementById('map-search-results');
    if (box) box.style.display = 'none';
  }
});

// Init map after Leaflet loads
if (typeof L !== 'undefined') {
  initLeafletMap();
} else {
  window.addEventListener('load', initLeafletMap);
}
// ── Forecast ───────────────────────────────────────────────────────────────
function updateForecast(cityName, fc) {
  document.getElementById('forecast-label').textContent = '7-Day Outlook · '+cityName;
  document.getElementById('forecast-strip').innerHTML = (fc||[]).map(d=>`
    <div class="forecast-day">
      <div class="forecast-label">${d.day}</div>
      <div class="forecast-icon">${d.icon}</div>
      <div class="forecast-hi">${dispTemp(d.high)}</div>
      <div class="forecast-lo">${dispTemp(d.low)} lo</div>
      <div class="forecast-rain-bar"><div class="forecast-rain-fill" style="width:${d.rain||0}%"></div></div>
    </div>`).join('');
  if (typeof twemoji !== 'undefined') twemoji.parse(document.getElementById('forecast-strip'));
}

// ── Select city ────────────────────────────────────────────────────────────
function selectCity(name) {
  if (!name) return;
  currentCity = name;
  document.querySelectorAll('.city-card').forEach(c=>c.classList.remove('selected'));
  const sel = document.querySelector(`.city-card[data-city="${name}"]`);
  if (sel) sel.classList.add('selected');
  const badge = document.getElementById('preview-badge');
  if (badge) badge.style.display='none';
  document.getElementById('featured-loading').style.display='inline';
  document.querySelector('.featured-section').scrollIntoView({behavior:'smooth',block:'start'});
  fetch(`/api/city/${encodeURIComponent(name)}`)
    .then(r=>r.json())
    .then(d => {
      updateFeaturedPanel(d);
      updateForecast(d.city, d.forecast||[]);
      document.getElementById('featured-loading').style.display='none';
    })
    .catch(()=>{
      document.getElementById('featured-loading').style.display='none';
      const card = document.querySelector(`.city-card[data-city="${name}"]`);
      if (card) updateFeaturedPanel({
        city:name, country:'',
        icon: card.querySelector('.city-icon')?.textContent||'🌡️',
        temp: parseFloat(card.dataset.tempC)||25,
        condition: card.querySelector('.city-condition')?.textContent||'—',
        feels_like:'—',humidity:'—',wind_speed:'—',uv_index:'—',pressure:'—',visibility:'—',
        sunrise:'—',sunset:'—',rain_prob:0,aqi:50,aqi_label:'Good',aqi_color:'#00c853',hourly:[],
      });
    });
}

// ── Update all cards ───────────────────────────────────────────────────────
function updateAllCards(list) {
  allCities = list;
  list.forEach(w => {
    const card = document.querySelector(`.city-card[data-city="${w.city}"]`);
    if (!card) return;
    card.dataset.tempC = w.temp;
    const tempEl = card.querySelector('.city-temp');
    if (tempEl) tempEl.textContent = dispTemp(w.temp);
    const condEl = card.querySelector('.city-condition');
    if (condEl) condEl.textContent = w.condition;
    const iconEl = card.querySelector('.city-icon');
    if (iconEl) iconEl.textContent = w.icon;
    const stats = card.querySelectorAll('.card-stat-value');
    if (stats[0]) stats[0].textContent = w.humidity+'%';
    if (stats[1]) stats[1].textContent = w.wind_speed+' km/h';
    if (stats[2]) stats[2].textContent = w.uv_index;
    if (stats[3]) stats[3].textContent = w.pressure;
    const badges = card.querySelectorAll('.badge');
    if (badges[0]) badges[0].textContent = 'AQI '+w.aqi;
    if (badges[1]) badges[1].textContent = '💧'+w.rain_prob+'%';
  });
  renderMapDots(list);
}

// ── Ticker ─────────────────────────────────────────────────────────────────
function updateTicker(list) {
  const t = document.querySelector('.ticker');
  if (!t) return;
  const items = list.map(w=>`<span class="ticker-item">${w.icon} ${w.city} ${dispTemp(w.temp)} · ${w.condition}</span>`).join('');
  t.innerHTML = items+items;
}

// ── Compare ────────────────────────────────────────────────────────────────
function toggleCompare() {
  const p = document.getElementById('compare-panel');
  const showing = p.style.display==='block';
  p.style.display = showing ? 'none' : 'block';
  document.getElementById('compare-btn').classList.toggle('active', !showing);
  if (!showing) loadCompare();
}
function loadCompare() {
  const a = document.getElementById('compare-a').value;
  const b = document.getElementById('compare-b').value;
  [['a',a],['b',b]].forEach(([slot,city])=>{
    const w = allCities.find(x=>x.city===city);
    if (!w) return;
    document.getElementById('compare-'+slot+'-data').innerHTML = `
      <div class="compare-city">
        <div class="compare-city-name">${w.city} ${w.icon}</div>
        <div class="compare-temp">${dispTemp(w.temp)}</div>
        <div class="compare-row"><span>Condition</span><span>${w.condition}</span></div>
        <div class="compare-row"><span>Humidity</span><span>${w.humidity}%</span></div>
        <div class="compare-row"><span>Wind</span><span>${w.wind_speed} km/h</span></div>
        <div class="compare-row"><span>UV Index</span><span>${w.uv_index}</span></div>
        <div class="compare-row"><span>AQI</span><span style="color:${w.aqi_color}">${w.aqi} · ${w.aqi_label}</span></div>
        <div class="compare-row"><span>Rain Prob.</span><span>${w.rain_prob}%</span></div>
        <div class="compare-row"><span>Sunrise</span><span>${w.sunrise}</span></div>
        <div class="compare-row"><span>Sunset</span><span>${w.sunset}</span></div>
      </div>`;
  });
}

// ── Mode toggle ────────────────────────────────────────────────────────────
function setAddMode(mode) {
  document.getElementById('add-mode-search').style.display = mode==='search' ? 'block' : 'none';
  document.getElementById('add-mode-browse').style.display = mode==='browse' ? 'block' : 'none';
  document.getElementById('mode-search').classList.toggle('active', mode==='search');
  document.getElementById('mode-browse').classList.toggle('active', mode==='browse');
}

// ── Hierarchical browser ───────────────────────────────────────────────────
const HIER_LEVELS = ['country','state','district','subdistrict','mandal','village'];
const HIER_LABELS = {
  country:'Country', state:'State / Province', district:'District',
  subdistrict:'Sub-District', mandal:'Mandal / Taluk', village:'Village / Hamlet'
};
const HIER_ICONS = {
  country:'🌍', state:'🗺️', district:'📍', subdistrict:'🏘️', mandal:'🌾', village:'🏡'
};
// Leaf place types that should be directly selectable (not drilled into)
const LEAF_TYPES = /village|hamlet|locality|neighbourhood|suburb|isolated|quarter|allotments/i;

let hierStack    = [];   // [{level, name, osm_id, lat, lon, country_code, country_name, state, district}]
let hierSelected = null;
let hierTimer    = null;
let _hierResults = [];   // module-level, not stored on DOM

function hierSearch(q) {
  clearTimeout(hierTimer);
  const inner = document.getElementById('hier-results-inner');
  if (!q || !q.trim()) {
    inner.innerHTML = '<div style="padding:12px 16px;font-family:monospace;font-size:.68rem;color:#666;">Type a name to search...</div>';
    return;
  }
  inner.innerHTML = '<div style="padding:12px 16px;font-family:monospace;font-size:.68rem;color:#888;">Searching...</div>';

  const parentId = hierStack.length ? hierStack[hierStack.length-1].osm_id : '';
  const levelIdx = Math.min(hierStack.length, HIER_LEVELS.length - 1);
  const level    = HIER_LEVELS[levelIdx];

  hierTimer = setTimeout(()=>{
    fetch(`/api/hierarchy?q=${encodeURIComponent(q)}&parent_osm_id=${encodeURIComponent(parentId)}&level=${level}`)
      .then(r => r.json())
      .then(d => {
        _hierResults = d.results || [];
        renderHierResults(_hierResults, level);
      })
      .catch(() => {
        inner.innerHTML = '<div style="padding:12px 16px;font-family:monospace;font-size:.68rem;color:#f44336;">Search failed. Try again.</div>';
      });
  }, 380);
}

function renderHierResults(results, level) {
  const inner    = document.getElementById('hier-results-inner');
  const nextIdx  = HIER_LEVELS.indexOf(level) + 1;
  const nextLevel= HIER_LEVELS[nextIdx];

  if (!results || !results.length) {
    inner.innerHTML = '<div style="padding:12px 16px;font-family:monospace;font-size:.68rem;color:#666;">No results found. Try a different name.</div>';
    return;
  }

  inner.innerHTML = results.map((r, i) => {
    const isLeaf = !nextLevel || LEAF_TYPES.test(r.place_type || '');
    const leafFlag = isLeaf ? 1 : 0;
    const rightLabel = isLeaf
      ? `<span style="color:#00c853;font-size:.6rem;font-weight:700;white-space:nowrap;flex-shrink:0;">✓ SELECT</span>`
      : `<span style="color:#e8441a;font-size:.6rem;white-space:nowrap;flex-shrink:0;">${nextLevel ? HIER_ICONS[nextLevel] : '▶'} Drill in →</span>`;
    return `
      <div onclick="selectHierPlace(${i},${leafFlag})" style="
          padding:12px 16px;display:flex;justify-content:space-between;align-items:center;
          border-bottom:1px solid var(--border);cursor:pointer;gap:12px;
          font-family:'Space Mono',monospace;font-size:.68rem;color:var(--ink);transition:background .15s;"
          onmouseover="this.style.background='rgba(232,68,26,.08)'"
          onmouseout="this.style.background='transparent'">
        <div style="min-width:0;">
          <div style="font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
            ${HIER_ICONS[level]||'📍'} ${r.name}
          </div>
          <div style="color:var(--muted);font-size:.58rem;margin-top:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
            ${r.display || r.name}
          </div>
        </div>
        ${rightLabel}
      </div>`;
  }).join('');
}

function selectHierPlace(idx, isLeaf) {
  const r = _hierResults[idx];
  if (!r) return;
  const levelIdx = Math.min(hierStack.length, HIER_LEVELS.length - 1);
  const level    = HIER_LEVELS[levelIdx];

  if (isLeaf) {
    hierSelected = r;
    document.getElementById('hier-selected-name').textContent = r.name;
    document.getElementById('hier-selected-path').textContent =
      (r.display || r.name) + (r.lat ? ` · ${parseFloat(r.lat).toFixed(4)}, ${parseFloat(r.lon).toFixed(4)}` : '');
    document.getElementById('hier-selected').style.display = 'block';
    updateBreadcrumb(r);
  } else {
    // Push to stack and search children
    hierStack.push({ ...r, level });
    hierSelected = null;
    document.getElementById('hier-selected').style.display = 'none';
    updateBreadcrumb(null);
    const searchEl = document.getElementById('hier-search');
    searchEl.value = '';
    searchEl.placeholder = `Search within ${r.name}...`;
    searchEl.focus();
    document.getElementById('hier-results-inner').innerHTML =
      `<div style="padding:12px 16px;font-family:monospace;font-size:.68rem;color:#888;">
        Now inside <b>${r.name}</b> — type to search ${HIER_LABELS[HIER_LEVELS[hierStack.length]] || 'places'} within it.
      </div>`;
  }
}

function updateBreadcrumb(selected) {
  const bc = document.getElementById('hier-breadcrumb');
  const parts = [
    `<span onclick="hierGoHome()" style="cursor:pointer;font-family:'Space Mono',monospace;font-size:.62rem;color:#e8441a;">🌍 Home</span>`
  ];
  hierStack.forEach((s, i) => {
    parts.push(`<span style="color:#888;margin:0 4px;">›</span>`);
    // Clicking a stack entry goes back to that level (keep entries 0..i)
    parts.push(`<span onclick="hierGoBack(${i+1})" style="cursor:pointer;font-family:'Space Mono',monospace;font-size:.62rem;color:var(--ink);text-decoration:underline dotted;">${s.name}</span>`);
  });
  if (selected) {
    parts.push(`<span style="color:#888;margin:0 4px;">›</span>`);
    parts.push(`<span style="font-family:'Space Mono',monospace;font-size:.62rem;color:#00c853;font-weight:700;">${selected.name}</span>`);
  }
  bc.innerHTML = parts.join('');
}

function hierGoHome() {
  hierStack    = [];
  hierSelected = null;
  _hierResults = [];
  document.getElementById('hier-selected').style.display = 'none';
  document.getElementById('hier-search').value = '';
  document.getElementById('hier-search').placeholder = 'Search within current level...';
  document.getElementById('hier-results-inner').innerHTML =
    `<div style="padding:12px 16px;font-family:monospace;font-size:.68rem;color:#666;">Type a country, state or district name to begin browsing.</div>`;
  document.getElementById('hier-breadcrumb').innerHTML =
    `<span style="font-family:'Space Mono',monospace;font-size:.62rem;color:#666;">Start typing to explore...</span>`;
}

function hierGoBack(idx) {
  // idx is the stack position to go BACK TO (keep 0..idx-1, discard idx and above)
  hierStack    = hierStack.slice(0, idx);
  hierSelected = null;
  _hierResults = [];
  document.getElementById('hier-selected').style.display = 'none';
  document.getElementById('hier-search').value = '';
  const parentName = hierStack.length ? hierStack[hierStack.length-1].name : '';
  document.getElementById('hier-search').placeholder = parentName ? `Search within ${parentName}...` : 'Search within current level...';
  document.getElementById('hier-results-inner').innerHTML =
    `<div style="padding:12px 16px;font-family:monospace;font-size:.68rem;color:#888;">Type to search${parentName ? ` within <b>${parentName}</b>` : ''}...</div>`;
  updateBreadcrumb(null);
}

function addHierCity() {
  if (!hierSelected) return;
  const r = hierSelected;
  // Populate the quick-search form fields and call addCustomCity
  const nameEl = document.getElementById('add-city-name');
  nameEl.value = r.name;
  nameEl.dataset.countryCode = r.country_code || 'CUSTOM';
  nameEl.dataset.countryName = r.country_name || 'Custom';
  document.getElementById('add-city-lat').value = parseFloat(r.lat).toFixed(4);
  document.getElementById('add-city-lon').value = parseFloat(r.lon).toFixed(4);
  addCustomCity();
}

function previewHierCity() {
  if (!hierSelected) return;
  const r = hierSelected;
  document.getElementById('featured-loading').style.display = 'inline';
  document.querySelector('.featured-section').scrollIntoView({behavior:'smooth', block:'start'});
  fetch(`/api/preview?lat=${r.lat}&lon=${r.lon}&name=${encodeURIComponent(r.name)}&country=${encodeURIComponent(r.country_name||'')}`)
    .then(res => res.json())
    .then(d => {
      updateFeaturedPanel(d);
      updateForecast(d.city, d.forecast || []);
      document.getElementById('featured-loading').style.display = 'none';
      const badge = document.getElementById('preview-badge');
      if (badge) badge.style.display = 'inline-flex';
    })
    .catch(() => { document.getElementById('featured-loading').style.display = 'none'; });
}

// ── Geocode search (OpenStreetMap Nominatim) ──────────────────────────────
let geocodeTimer = null;
let _geoResults  = [];

function geocodeSearch(q) {
  clearTimeout(geocodeTimer);
  const box = document.getElementById('geocode-results');
  const btn = document.getElementById('add-city-btn');
  btn.disabled=true; btn.style.opacity='.5'; btn.style.cursor='not-allowed';
  document.getElementById('add-city-lat').value='';
  document.getElementById('add-city-lon').value='';
  if (!q || q.length < 2) { box.style.display='none'; return; }
  box.style.display='block';
  box.innerHTML='<div style="padding:12px 14px;font-family:monospace;font-size:.68rem;color:#666;">Searching...</div>';
  geocodeTimer = setTimeout(()=>{
    fetch('/api/geocode?q='+encodeURIComponent(q))
      .then(r=>r.json())
      .then(data=>{
        _geoResults = data.results || [];
        if (!_geoResults.length) {
          box.innerHTML='<div style="padding:12px 14px;font-family:monospace;font-size:.68rem;color:#888;">No results. Try a different spelling.</div>';
          return;
        }
        box.innerHTML = _geoResults.map((r,i)=>`
          <div onclick="selectGeoResult(${i})" style="padding:11px 14px;font-family:'Space Mono',monospace;font-size:.68rem;
            color:#ccc;cursor:pointer;border-bottom:1px solid rgba(255,255,255,.05);
            display:flex;justify-content:space-between;align-items:center;"
            onmouseover="this.style.background='rgba(232,68,26,.15)'"
            onmouseout="this.style.background='transparent'">
            <span>📍 ${r.display}</span>
            <span style="color:#555;font-size:.58rem;">${r.place_type||'Place'} · ${r.lat.toFixed(2)}, ${r.lon.toFixed(2)}</span>
          </div>`).join('');
      })
      .catch(()=>{ box.innerHTML='<div style="padding:12px 14px;font-family:monospace;font-size:.68rem;color:#f44336;">Search failed.</div>'; });
  }, 420);
}

function selectGeoResult(idx) {
  const r = _geoResults[idx]; if (!r) return;
  document.getElementById('add-city-name').value = r.name;
  document.getElementById('add-city-lat').value  = r.lat.toFixed(4);
  document.getElementById('add-city-lon').value  = r.lon.toFixed(4);
  // Store country info on hidden fields for submission
  document.getElementById('add-city-name').dataset.countryCode = r.country_code || 'CUSTOM';
  document.getElementById('add-city-name').dataset.countryName = r.country_name || 'Custom';
  document.getElementById('geocode-results').style.display='none';
  const btn = document.getElementById('add-city-btn');
  btn.disabled=false; btn.style.opacity='1'; btn.style.cursor='pointer';
}

document.addEventListener('click', e=>{
  if (!e.target.closest('.add-city-section')) {
    const b=document.getElementById('geocode-results');
    if (b) b.style.display='none';
  }
});

// ── Add custom city ────────────────────────────────────────────────────────
function addCustomCity() {
  const nameEl = document.getElementById('add-city-name');
  const name   = nameEl.value.trim();
  const lat    = parseFloat(document.getElementById('add-city-lat').value);
  const lon    = parseFloat(document.getElementById('add-city-lon').value);
  const countryCode = nameEl.dataset.countryCode || 'CUSTOM';
  const countryName = nameEl.dataset.countryName || 'Custom';
  const msg  = document.getElementById('add-msg');
  const btn  = document.getElementById('add-city-btn');
  if (!name || isNaN(lat) || isNaN(lon)) {
    msg.innerHTML='⚠️ Please select a city from the dropdown first.';
    msg.style.color='#ff9800'; msg.style.display='block'; return;
  }
  msg.innerHTML=`⏳ Fetching weather for <b>${name}</b>...`;
  msg.style.color='var(--accent)'; msg.style.display='block';
  btn.disabled=true; btn.style.opacity='.5';
  fetch('/api/add-city',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({name, lat, lon, country_code: countryCode, country_name: countryName})
  })
  .then(r=>r.json())
  .then(d=>{
    if (d.success) {
      msg.innerHTML=`✅ <b>${name}</b> added under <b>${countryName}</b>!`;
      msg.style.color='#00c853';
      if (d.weather) {
        allCities.push(d.weather);
        renderNewCityCard(d.weather, countryCode, countryName);
        updateTicker(allCities);
        renderMapDots(allCities);
      }
      nameEl.value=''; nameEl.dataset.countryCode=''; nameEl.dataset.countryName='';
      document.getElementById('add-city-lat').value='';
      document.getElementById('add-city-lon').value='';
      btn.disabled=true; btn.style.opacity='.5'; btn.style.cursor='not-allowed';
    } else {
      msg.textContent='❌ '+(d.error||'Failed to add city.');
      msg.style.color='#f44336';
      btn.disabled=false; btn.style.opacity='1';
    }
  })
  .catch(()=>{
    msg.textContent='❌ Network error. Try again.';
    msg.style.color='#f44336';
    btn.disabled=false; btn.style.opacity='1';
  });
}

function renderNewCityCard(w, countryCode, countryName) {
  countryCode = countryCode || w.country || 'CUSTOM';
  countryName = countryName || w.country_name || 'Custom';

  // Build the card HTML
  const card = document.createElement('div');
  card.className='city-card';
  card.setAttribute('data-city', w.city);
  card.setAttribute('data-temp-c', w.temp);
  card.setAttribute('data-country', countryCode);
  card.onclick = ()=>selectCity(w.city);
  card.innerHTML=`
    <button class="city-delete-btn" onclick="event.stopPropagation();deleteCity('${w.city}')" title="Remove city">✕</button>
    <div class="city-header">
      <div><div class="city-name">${w.city}</div><div class="city-country">${countryName}</div></div>
      <div class="city-icon">${w.icon}</div>
    </div>
    <div class="city-temp">${dispTemp(w.temp)}</div>
    <div class="city-condition">${w.condition}</div>
    <div class="city-badges">
      <span class="badge badge-aqi">AQI ${w.aqi||'—'}</span>
      <span class="badge badge-rain">💧${w.rain_prob||0}%</span>
    </div>
    <div class="card-stats">
      <div><div class="card-stat-label">Humidity</div><div class="card-stat-value">${w.humidity}%</div></div>
      <div><div class="card-stat-label">Wind</div><div class="card-stat-value">${w.wind_speed} km/h</div></div>
      <div><div class="card-stat-label">UV</div><div class="card-stat-value">${w.uv_index}</div></div>
      <div><div class="card-stat-label">Pressure</div><div class="card-stat-value">${w.pressure}</div></div>
    </div>`;

  // Find or create the country section grid
  const gridId = 'grid-' + countryCode;
  let grid = document.getElementById(gridId);

  if (!grid) {
    // Country section doesn't exist yet — create it and insert alphabetically
    const section = document.createElement('section');
    const flagMap = {IN:'🇮🇳',JP:'🇯🇵',RU:'🇷🇺',ZA:'🇿🇦'};
    const flag = flagMap[countryCode] || '🌍';
    section.setAttribute('data-country-name', countryName);
    section.innerHTML=`
      <div class="section-label" style="margin-top:40px;">
        <span class="flag-emoji">${flag}</span> ${countryName}
      </div>
      <div class="city-grid" id="${gridId}"></div>`;

    // Insert section alphabetically among existing country sections
    const allSections = [...document.querySelectorAll('section[data-country-name]')];
    const insertBefore = allSections.find(s =>
      s.getAttribute('data-country-name').localeCompare(countryName) > 0
    );
    const addSection = document.querySelector('.add-city-section');
    if (insertBefore) insertBefore.before(section);
    else addSection.before(section);

    grid = document.getElementById(gridId);
  }

  // Insert card alphabetically within the grid
  const existingCards = [...grid.querySelectorAll('.city-card')];
  const insertCardBefore = existingCards.find(c =>
    c.getAttribute('data-city').localeCompare(w.city) > 0
  );
  if (insertCardBefore) insertCardBefore.before(card);
  else grid.appendChild(card);

  if (typeof twemoji!=='undefined') twemoji.parse(card);
}

// ── Share ──────────────────────────────────────────────────────────────────
// ── Delete / Restore cities (localStorage-backed — survives page refresh) ──
const LS_DELETED = 'wd-deleted-cities';   // key in localStorage

function _getDeleted() {
  try { return new Set(JSON.parse(localStorage.getItem(LS_DELETED) || '[]')); }
  catch(e) { return new Set(); }
}
function _saveDeleted(set) {
  try { localStorage.setItem(LS_DELETED, JSON.stringify([...set])); } catch(e) {}
}

// On every page load: hide any previously deleted city cards immediately
(function applyDeletedOnLoad() {
  const deleted = _getDeleted();
  if (!deleted.size) return;
  deleted.forEach(cityName => {
    const card = document.querySelector(`.city-card[data-city="${cityName}"]`);
    if (card) {
      const grid = card.closest('.city-grid');
      card.remove();
      if (grid && grid.querySelectorAll('.city-card').length === 0) {
        const section = grid.closest('section[data-country-name]');
        if (section) section.remove();
      }
    }
  });
  // Also remove from allCities
  allCities = allCities.filter(c => !deleted.has(c.city));
  renderRestorePanel();
})();

function deleteCity(cityName) {
  if (!confirm(`Remove "${cityName}" from the dashboard?`)) return;

  // 1. Save to localStorage immediately — survives all future refreshes
  const deleted = _getDeleted();
  deleted.add(cityName);
  _saveDeleted(deleted);

  // 2. Remove card from DOM with animation
  const card = document.querySelector(`.city-card[data-city="${cityName}"]`);
  if (card) {
    card.style.transition = 'opacity .3s, transform .3s';
    card.style.opacity = '0';
    card.style.transform = 'scale(.9)';
    setTimeout(() => {
      const grid = card.closest('.city-grid');
      card.remove();
      if (grid && grid.querySelectorAll('.city-card').length === 0) {
        const section = grid.closest('section[data-country-name]');
        if (section) section.remove();
      }
    }, 300);
  }

  // 3. Remove from allCities runtime array
  const idx = allCities.findIndex(c => c.city === cityName);
  if (idx !== -1) allCities.splice(idx, 1);

  // 4. Clear featured panel if this was selected
  if (currentCity === cityName) {
    currentCity = null;
    document.getElementById('feat-city').textContent = '—';
  }

  // 5. Tell backend (best-effort — keeps cache clean for this session)
  fetch('/api/remove-city', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({name: cityName})
  }).catch(() => {});

  // 6. Update restore panel
  renderRestorePanel();
}

// ── Restore panel ─────────────────────────────────────────────────────────
function renderRestorePanel() {
  const deleted = _getDeleted();
  const section = document.getElementById('restore-section');
  const list    = document.getElementById('restore-list');
  const empty   = document.getElementById('restore-empty');
  if (!deleted.size) {
    section.style.display = 'none';
    return;
  }
  section.style.display = 'block';
  empty.style.display = 'none';
  const flagMap = {IN:'🇮🇳',JP:'🇯🇵',RU:'🇷🇺',ZA:'🇿🇦'};
  // Look up country from all known city data
  const allKnown = {};
  document.querySelectorAll('.city-card').forEach(c => {
    allKnown[c.dataset.city] = c.dataset.country;
  });
  list.innerHTML = [...deleted].sort().map(name => {
    const country = allKnown[name] || '';
    const flag    = flagMap[country] || '🌍';
    return `<button onclick="restoreCity('${name}')" style="
      display:inline-flex;align-items:center;gap:6px;
      background:rgba(76,175,80,.12);border:1px solid rgba(76,175,80,.4);
      color:#4caf50;padding:6px 14px;border-radius:4px;cursor:pointer;
      font-family:monospace;font-size:.68rem;letter-spacing:.5px;transition:all .2s;">
      ${flag} ${name} <span style="color:#888;font-size:.6rem;">↩ Restore</span>
    </button>`;
  }).join('');
}

function restoreCity(name) {
  // Remove from localStorage deleted set
  const deleted = _getDeleted();
  deleted.delete(name);
  _saveDeleted(deleted);

  // Tell backend to restore (best-effort)
  fetch('/api/restore-city', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({name})
  }).catch(() => {});

  // Reload page to show restored city card
  window.location.reload();
}

// Render restore panel on initial load
renderRestorePanel();

function shareWhatsApp() {
  const city=document.getElementById('feat-city').textContent;
  const temp=document.getElementById('feat-temp').textContent;
  const cond=document.getElementById('feat-condition').textContent;
  window.open('https://wa.me/?text='+encodeURIComponent(`🌤️ Weather in ${city}: ${temp} — ${cond}\nLive weather: ${window.location.href}`),'_blank');
}
function shareTwitter() {
  const city=document.getElementById('feat-city').textContent;
  const temp=document.getElementById('feat-temp').textContent;
  const cond=document.getElementById('feat-condition').textContent;
  window.open('https://twitter.com/intent/tweet?text='+encodeURIComponent(`🌤️ ${city}: ${temp} — ${cond} | AHOY WeatherDrift`)+'&url='+encodeURIComponent(window.location.href),'_blank');
}
function downloadCard() {
  const city=document.getElementById('feat-city').textContent;
  const temp=document.getElementById('feat-temp').textContent;
  const cond=document.getElementById('feat-condition').textContent;
  const icon=document.getElementById('feat-icon').textContent;
  const aqi =document.getElementById('feat-aqi-label').textContent;
  const sr  =document.getElementById('feat-sunrise').textContent;
  const ss  =document.getElementById('feat-sunset').textContent;
  const date=new Date().toLocaleDateString('en-GB',{weekday:'long',day:'numeric',month:'long',year:'numeric'});
  const canvas=document.createElement('canvas');
  canvas.width=800; canvas.height=480;
  const ctx=canvas.getContext('2d');
  const g=ctx.createLinearGradient(0,0,800,480);
  g.addColorStop(0,'#0a0a0f'); g.addColorStop(1,'#1a1a2e');
  ctx.fillStyle=g; ctx.fillRect(0,0,800,480);
  ctx.fillStyle='#e8441a'; ctx.fillRect(0,0,6,480);
  ctx.font='72px serif'; ctx.fillText(icon,60,110);
  ctx.fillStyle='#f2ede6'; ctx.font='bold 52px sans-serif'; ctx.textAlign='left';
  ctx.fillText(city,60,185);
  ctx.fillStyle='#e8441a'; ctx.font='bold 90px sans-serif'; ctx.textAlign='right';
  ctx.fillText(temp,760,185);
  ctx.fillStyle='#aaa'; ctx.font='20px sans-serif'; ctx.textAlign='left';
  ctx.fillText(cond,60,230);
  ctx.fillStyle='#888'; ctx.font='16px monospace';
  ctx.fillText('🌅 '+sr+'  🌇 '+ss,60,275);
  ctx.fillText(aqi,60,305);
  ctx.fillStyle='#555'; ctx.font='14px monospace';
  ctx.fillText(date,60,360);
  ctx.fillStyle='#e8441a'; ctx.font='bold 16px monospace'; ctx.textAlign='right';
  ctx.fillText('AHOY WeatherDrift',760,460);
  const a=document.createElement('a');
  a.download=`weather-${city.toLowerCase().replace(/ /g,'-')}.png`;
  a.href=canvas.toDataURL();a.click();
}

// ── Auto refresh ───────────────────────────────────────────────────────────
function autoRefresh() {
  fetch('/api/weather').then(r=>r.json()).then(data=>{
    updateAllCards(data.weather);
    updateTicker(data.weather);
    const l=document.getElementById('last-updated-label');
    if(l) l.textContent='Last updated: '+data.last_updated;

    // Always record history for ALL cities so switching tabs shows real data
    data.weather.forEach(w => {
      if (!histData[w.city]) histData[w.city] = [];
      histData[w.city].push({
        t: new Date().toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit'}),
        temp: w.temp,
        humidity: w.humidity ?? 65,
        wind: w.wind_speed ?? 12,
      });
      if (histData[w.city].length > 20) histData[w.city].shift();
    });

    // Update featured panel + redraw chart for current city
    if (currentCity) {
      const w = data.weather.find(x=>x.city===currentCity);
      if (w) {
        updateFeaturedPanel(w);
        drawChart(histData[currentCity]);
      }
    }

    // Refresh map markers with latest temps/conditions
    if (_leafletMap) renderMapDots(data.weather);

  }).catch(()=>{});
}

// ── Init ───────────────────────────────────────────────────────────────────
document.querySelectorAll('.city-card').forEach(card=>{
  const city  = card.dataset.city;
  const rawC  = parseFloat(card.dataset.tempC);
  const stats = card.querySelectorAll('.card-stat-value');
  const humidity  = parseFloat(stats[0]?.textContent) || 65;
  const wind      = parseFloat(stats[1]?.textContent) || 12;
  const icon      = card.querySelector('.city-icon')?.textContent || '🌡️';
  const condition = card.querySelector('.city-condition')?.textContent || '';
  if (city && !isNaN(rawC)) {
    allCities.push({
      city,
      country: card.dataset.country || '',
      temp: rawC,
      icon,
      condition,
      humidity,
      wind_speed: wind,
    });
    // Seed initial history point so chart isn't empty
    if (!histData[city]) histData[city] = [];
    histData[city].push({
      t: new Date().toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit'}),
      temp: rawC, humidity, wind,
    });
  }
});

// Set rawc on feat-temp
const ft=document.getElementById('feat-temp');
if(ft) ft.dataset.rawc = parseFloat(ft.textContent.replace(/[^0-9.\-]/g,'')) || 25;

// Draw chart immediately with seeded data
const _initCity = document.getElementById('history-city-label')?.textContent?.trim();
if (_initCity && histData[_initCity]) {
  setTimeout(()=>drawChart(histData[_initCity]), 200);
}

setInterval(autoRefresh, 60000);

// Twemoji
if (typeof twemoji!=='undefined') {
  window.addEventListener('load',()=>twemoji.parse(document.body));
}

// Initial map render — init Leaflet then plot dots
setTimeout(()=>{
  initLeafletMap();
  if (allCities.length) renderMapDots(allCities);
}, 600);

// Initial bg
setWeatherBg('{{ featured.condition }}');

console.log('AHOY WeatherDrift v2.0 ready ✅');
</script>
</body>
</html>
"""

# ── Flask Routes ─────────────────────────────────────────────────────────────
@app.route("/")
def index():
    weather = get_cached_weather()

    # Map country codes to names for consistent sorting
    CODE_TO_NAME = {
        "IN": "India", "JP": "Japan", "RU": "Russia", "ZA": "South Africa",
    }

    def sort_key(w):
        code = w.get("country", "CUSTOM")
        name = w.get("country_name") or CODE_TO_NAME.get(code, code)
        return (name, w.get("city", ""))

    weather_sorted = sorted(weather, key=sort_key)
    featured = weather_sorted[0] if weather_sorted else {}
    forecast  = get_forecast(featured.get("city","Mumbai"))

    # Build sorted country groups for template
    country_meta = {
        "IN":  ("India",        "🇮🇳"),
        "JP":  ("Japan",        "🇯🇵"),
        "RU":  ("Russia",       "🇷🇺"),
        "ZA":  ("South Africa", "🇿🇦"),
        "CUSTOM": ("Custom",    "🌍"),
    }

    def get_country_name(code, w):
        """Resolve display name: prefer stored country_name, else country_meta, else code."""
        return (w.get("country_name")
                or country_meta.get(code, (code, "🌍"))[0])

    # Gather all country codes present in data
    all_codes = sorted(
        set(w.get("country", "CUSTOM") for w in weather_sorted),
        key=lambda c: country_meta.get(c, (c, ""))[0]
    )

    country_groups = []
    for code in all_codes:
        meta = country_meta.get(code, (code, "🌍"))
        cities = sorted(
            [w for w in weather_sorted if w.get("country", "CUSTOM") == code],
            key=lambda w: w.get("city", "")
        )
        if cities:
            # Use actual country_name from first city if available (for custom countries)
            display_name = cities[0].get("country_name") or meta[0]
            country_groups.append({
                "code":   code,
                "name":   display_name,
                "flag":   meta[1],
                "cities": cities,
            })

    return render_template_string(HTML_TEMPLATE,
        weather_data=weather_sorted,
        country_groups=country_groups,
        featured=featured,
        forecast=forecast,
        datetime=datetime.now().strftime("%A, %d %B %Y · %H:%M UTC"),
        total_cities=len(weather_sorted),
        last_updated=_cache["last_updated"],
    )

@app.route("/api/weather")
def api_weather():
    weather = get_cached_weather()
    return jsonify({"weather": weather, "last_updated": _cache["last_updated"]})

@app.route("/api/city/<path:city_name>")
def city_api(city_name):
    cached = get_cached_weather()
    cached_city = next((w for w in cached if w["city"].lower()==city_name.lower()), None)
    all_c = get_all_cities()
    coords = all_c.get(city_name)
    if not coords:
        for k,v in all_c.items():
            if k.lower()==city_name.lower():
                city_name=k; coords=v; break
    if not coords:
        return jsonify({"error":"City not found"}), 404
    forecast = get_forecast(city_name)
    if cached_city:
        return jsonify({**cached_city, "forecast": forecast})
    # Live fallback
    result = fetch_single_city(city_name, coords)
    return jsonify({**result, "forecast": forecast})

@app.route("/api/reverse")
def reverse_geocode():
    """Reverse geocode lat/lon to a place name using Nominatim."""
    lat = request.args.get("lat", "").strip()
    lon = request.args.get("lon", "").strip()
    if not lat or not lon:
        return jsonify({"error": "Missing lat/lon"}), 400
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": lat, "lon": lon, "format": "json",
                    "zoom": 14, "addressdetails": 1, "accept-language": "en"},
            headers={"User-Agent": "AHOY WeatherDrift/2.0 (weather app)"},
            timeout=8
        )
        data = r.json()
        addr = data.get("address", {})
        name = (
            addr.get("hamlet") or addr.get("village") or
            addr.get("suburb") or addr.get("town") or
            addr.get("city_district") or addr.get("city") or
            addr.get("county") or data.get("name") or
            f"{float(lat):.2f}°N, {float(lon):.2f}°E"
        )
        country      = addr.get("country", "")
        country_code = addr.get("country_code", "").upper()
        state        = addr.get("state", "")
        district     = addr.get("state_district") or addr.get("county", "")
        return jsonify({"name": name, "country": country,
                        "country_code": country_code,
                        "state": state, "district": district})
    except Exception as e:
        return jsonify({"name": f"{float(lat):.2f}°N, {float(lon):.2f}°E",
                        "country": "", "error": str(e)})


@app.route("/api/geocode")
def geocode():
    """Search any named place via OpenStreetMap Nominatim — India-biased, with fallback worldwide."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "No query"}), 400

    def _fetch(params):
        return requests.get(
            "https://nominatim.openstreetmap.org/search",
            params=params,
            headers={"User-Agent": "AHOY WeatherDrift/2.0 (weather app)"},
            timeout=10
        ).json()

    def _parse(results, boost_india=False):
        suggestions = []
        seen = set()

        # Place-type priority — more specific = better
        TYPE_RANK = {
            "hamlet": 1, "isolated_dwelling": 2, "locality": 3,
            "neighbourhood": 4, "suburb": 5, "village": 6,
            "town": 7, "city_district": 8, "city": 9,
            "municipality": 10, "county": 11, "region": 12,
            "state": 13, "country": 14,
        }

        for item in results:
            addr = item.get("address", {})

            # Best place name — most specific first
            place_name = (
                addr.get("hamlet") or
                addr.get("isolated_dwelling") or
                addr.get("locality") or
                addr.get("neighbourhood") or
                addr.get("suburb") or
                addr.get("village") or
                addr.get("town") or
                addr.get("city_district") or
                addr.get("city") or
                addr.get("municipality") or
                addr.get("county") or
                addr.get("region") or
                item.get("name", "")
            )
            if not place_name:
                continue

            country_code = addr.get("country_code", "").upper()
            country_name = addr.get("country", "")
            state        = addr.get("state") or addr.get("province") or addr.get("region") or ""
            district     = addr.get("state_district") or addr.get("county") or ""
            postcode     = addr.get("postcode", "")

            # Build display string: Place, District, State, Country
            ctx = []
            if district and district.lower() != place_name.lower():
                ctx.append(district)
            if state and state.lower() != place_name.lower() and state != district:
                ctx.append(state)
            if country_name and country_code != "IN":  # skip "India" for Indian results — already obvious
                ctx.append(country_name)
            display = f"{place_name}, {', '.join(ctx)}" if ctx else place_name

            # Append postcode for Indian results if available (helps distinguish same-name villages)
            if country_code == "IN" and postcode:
                display += f" ({postcode})"

            osm_type   = item.get("type", "")
            place_type = item.get("addresstype", osm_type).replace("_", " ").title()

            # Importance score: Nominatim importance + India boost + type rank bonus
            importance = float(item.get("importance", 0.5))
            if country_code == "IN":
                importance += 0.4   # strongly prefer Indian results
            type_bonus = 1.0 / (TYPE_RANK.get(osm_type, 15) + 1)
            score = importance + type_bonus

            # Deduplicate by rounded lat/lon
            key = (round(float(item["lat"]), 2), round(float(item["lon"]), 2))
            if key in seen:
                continue
            seen.add(key)

            suggestions.append({
                "display":      display,
                "name":         place_name,
                "place_type":   place_type,
                "lat":          float(item["lat"]),
                "lon":          float(item["lon"]),
                "country_code": country_code,
                "country_name": country_name,
                "state":        state,
                "district":     district,
                "score":        score,
            })

        # Sort by score descending
        suggestions.sort(key=lambda x: x["score"], reverse=True)
        return suggestions

    try:
        all_results = []

        # Pass 1: India-biased search (countrycodes=in)
        india_raw = _fetch({
            "q": q,
            "format": "json",
            "limit": 10,
            "addressdetails": 1,
            "extratags": 1,
            "namedetails": 1,
            "countrycodes": "in",       # restrict to India first
            "accept-language": "en",
        })
        india_suggestions = _parse(india_raw, boost_india=True)
        all_results.extend(india_suggestions)

        # Pass 2: Worldwide fallback (only if India gave < 3 results)
        if len(india_suggestions) < 3:
            world_raw = _fetch({
                "q": q,
                "format": "json",
                "limit": 8,
                "addressdetails": 1,
                "extratags": 1,
                "namedetails": 1,
                "accept-language": "en",
            })
            world_suggestions = _parse(world_raw)
            # Add worldwide results not already in India results
            seen_names = {r["name"].lower() for r in all_results}
            for r in world_suggestions:
                if r["name"].lower() not in seen_names:
                    all_results.append(r)

        # Final dedup by (lat, lon) and cap at 8
        final = []
        seen_coords = set()
        for r in all_results:
            key = (round(r["lat"], 2), round(r["lon"], 2))
            if key not in seen_coords:
                seen_coords.add(key)
                final.append(r)
            if len(final) >= 8:
                break

        return jsonify({"results": final})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/hierarchy")
def api_hierarchy():
    """Search any administrative place using Nominatim free-text search with context."""
    q         = request.args.get("q", "").strip()
    parent_id = request.args.get("parent_osm_id", "").strip()
    level     = request.args.get("level", "place")

    if not q:
        return jsonify({"results": [], "level": level})

    try:
        params = {
            "q": q,
            "format": "json",
            "limit": 12,
            "addressdetails": 1,
            "extratags": 1,
            "namedetails": 1,
        }
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params=params,
            headers={"User-Agent": "WeatherDrift/2.0"},
            timeout=10
        )
        items = r.json()
        seen = set()
        results = []
        for item in items:
            addr = item.get("address", {})
            place_name = (
                addr.get("hamlet") or addr.get("isolated_dwelling") or
                addr.get("locality") or addr.get("neighbourhood") or
                addr.get("suburb") or addr.get("village") or
                addr.get("town") or addr.get("city_district") or
                addr.get("city") or addr.get("municipality") or
                addr.get("county") or item.get("name", "")
            )
            state        = addr.get("state") or addr.get("province") or ""
            district     = addr.get("county") or addr.get("state_district") or ""
            country_name = addr.get("country", "")
            country_code = addr.get("country_code", "").upper()
            place_type   = item.get("type", "place").title()

            context_parts = []
            if district and district.lower() != place_name.lower():
                context_parts.append(district)
            if state and state.lower() not in (place_name.lower(), district.lower()):
                context_parts.append(state)
            if country_name:
                context_parts.append(country_name)

            osm_id = str(item.get("osm_id", ""))
            key = osm_id or f"{round(float(item['lat']),3)},{round(float(item['lon']),3)}"
            if key in seen:
                continue
            seen.add(key)

            results.append({
                "name":         place_name,
                "display":      place_name + (", " + ", ".join(context_parts) if context_parts else ""),
                "osm_id":       osm_id,
                "osm_type":     item.get("osm_type", ""),
                "lat":          float(item["lat"]),
                "lon":          float(item["lon"]),
                "place_type":   place_type,
                "country_code": country_code,
                "country_name": country_name,
                "state":        state,
                "district":     district,
            })
        return jsonify({"results": results, "level": level})
    except Exception as e:
        return jsonify({"error": str(e), "results": []}), 500


@app.route("/api/remove-city", methods=["POST"])
def remove_city():
    """Permanently hide a city — survives server restarts."""
    global _custom_cities, _deleted_cities
    data = request.get_json()
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Missing name"}), 400

    # Remove from custom cities if user-added
    _custom_cities.pop(name, None)

    # Add to deleted set (covers built-in cities too)
    _deleted_cities.add(name)

    # Remove from live weather cache
    if _cache["weather"]:
        _cache["weather"] = [w for w in _cache["weather"] if w["city"] != name]

    # Persist to disk so deletion survives restart
    _save_data()

    return jsonify({"success": True, "removed": name})


@app.route("/api/restore-city", methods=["POST"])
def restore_city():
    """Un-delete a previously removed city."""
    global _deleted_cities
    data = request.get_json()
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Missing name"}), 400
    _deleted_cities.discard(name)
    _save_data()
    return jsonify({"success": True, "restored": name})


@app.route("/api/deleted-cities")
def list_deleted():
    """Return list of deleted built-in cities (for restore UI)."""
    deleted = [
        {"name": n, "country": CITIES[n]["country"]}
        for n in sorted(_deleted_cities)
        if n in CITIES   # only show built-ins, not removed custom cities
    ]
    return jsonify({"deleted": deleted})


@app.route("/api/add-city", methods=["POST"])
def add_city():
    global _custom_cities
    data         = request.get_json()
    name         = data.get("name", "").strip()
    lat          = data.get("lat")
    lon          = data.get("lon")
    country_code = (data.get("country_code", "CUSTOM") or "CUSTOM").upper().strip()
    country_name = (data.get("country_name", "Custom") or "Custom").strip()
    if not name or lat is None or lon is None:
        return jsonify({"error": "Missing fields"}), 400
    try:
        lat = float(lat)
        lon = float(lon)
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid coordinates"}), 400

    _custom_cities[name] = {
        "lat": lat, "lon": lon,
        "country": country_code,
        "country_name": country_name,
    }
    result = fetch_single_city(name, _custom_cities[name])
    result["country_name"] = country_name
    if _cache["weather"] is not None:
        _cache["weather"] = [w for w in _cache["weather"] if w["city"] != name]
        _cache["weather"].append(result)
    else:
        _cache["weather"] = [result]
    _save_data()  # persist new custom city to disk
    return jsonify({"success": True, "city": name, "weather": result, "country_name": country_name})


def _get_forecast_by_coords(lat, lon):
    url = (f"https://api.open-meteo.com/v1/forecast"
           f"?latitude={lat}&longitude={lon}"
           f"&daily=weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max"
           f"&timezone=auto&forecast_days=7")
    try:
        data  = requests.get(url, timeout=10).json()
        daily = data["daily"]
        fc    = []
        for i in range(7):
            d = datetime.strptime(daily["time"][i], "%Y-%m-%d")
            icon, cond = get_weather_icon(daily["weathercode"][i])
            fc.append({
                "day":  "Today" if i == 0 else d.strftime("%a"),
                "icon": icon, "condition": cond,
                "high": round(daily["temperature_2m_max"][i]),
                "low":  round(daily["temperature_2m_min"][i]),
                "rain": daily.get("precipitation_probability_max", [0] * 7)[i],
            })
        return fc
    except:
        return []


@app.route("/api/preview")
def api_preview():
    """Fetch live weather for any lat/lon without adding to the city list."""
    try:
        lat     = float(request.args.get("lat", 0))
        lon     = float(request.args.get("lon", 0))
        name    = request.args.get("name", "Unknown").strip()
        country = request.args.get("country", "").strip()
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid coordinates"}), 400

    coords = {"lat": lat, "lon": lon, "country": "CUSTOM"}
    result = fetch_single_city(name, coords)
    result["country_name"] = country
    result["forecast"]     = _get_forecast_by_coords(lat, lon)
    return jsonify(result)


@app.route("/api/test")
def api_test():
    try:
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast?latitude=17.69&longitude=83.22&current_weather=true",
            timeout=10)
        d = r.json()
        return jsonify({"status": "✅ API working", "temp": d["current_weather"]["temperature"]})
    except Exception as e:
        return jsonify({"status": "❌ API failed", "error": str(e)}), 500


@app.route("/health")
def health():
    return jsonify({"status": "ok", "cities": len(get_all_cities()), "cached": len(_cache["weather"] or [])})


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)