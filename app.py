from flask import Flask, render_template_string, jsonify, request
import requests, json, random, time, threading, math
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

app = Flask(__name__)

# ── Cache ───────────────────────────────────────────────────────────────────
_cache = {"weather": None, "timestamp": 0, "last_updated": "Never"}
_custom_cities = {}   # user-added cities stored in memory
REFRESH_INTERVAL = 60

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
    return {**CITIES, **_custom_cities}

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
<title>WeatherDrift — Global Weather Intelligence</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🌤️</text></svg>">
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@300;400;500;600&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/twemoji.min.js" crossorigin="anonymous"></script>
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
header{background:#0a0a0f;color:#f2ede6;padding:0 40px;display:flex;align-items:center;justify-content:space-between;border-bottom:3px solid var(--accent);position:sticky;top:0;z-index:100;}
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
#search-results{position:absolute;top:calc(100% + 4px);left:0;right:0;background:#1a1a22;border:1px solid rgba(255,255,255,.1);border-radius:6px;z-index:200;max-height:260px;overflow-y:auto;display:none;}
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
.chart-wrap{background:var(--card-bg);border:2px solid var(--border);padding:30px;position:relative;height:220px;}
.chart-canvas{width:100%;height:100%;}
body.dark .chart-wrap{background:#1e1e2a;}

/* ── WORLD MAP ── */
.map-section{margin-bottom:60px;}
.map-wrap{background:#0a0a0f;border:2px solid var(--border);overflow:hidden;position:relative;height:400px;}
#world-map{width:100%;height:100%;}
.map-dot{position:absolute;width:10px;height:10px;border-radius:50%;background:var(--accent);transform:translate(-50%,-50%);cursor:pointer;transition:transform .2s;}
.map-dot:hover{transform:translate(-50%,-50%) scale(2);}
.map-tooltip{position:absolute;background:#0a0a0f;border:1px solid var(--accent);color:#f2ede6;padding:8px 12px;font-family:'Space Mono',monospace;font-size:.65rem;border-radius:4px;pointer-events:none;display:none;z-index:50;white-space:nowrap;}

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
  <div style="font-family:'Bebas Neue',sans-serif;font-size:3rem;color:#f2ede6;letter-spacing:4px;">Weather<span style="color:#e8441a">Drift</span></div>
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
      <div class="logo">Weather<span>Drift</span></div>
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
      <div class="featured-country" id="feat-country">{% set cn = {"IN":"🇮🇳 India","JP":"🇯🇵 Japan","RU":"🇷🇺 Russia","ZA":"🇿🇦 South Africa"} %}{{ cn.get(featured.country, featured.country) }} · Updated just now</div>
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
  <div class="chart-wrap">
    <canvas id="history-chart" class="chart-canvas"></canvas>
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
  <div class="map-wrap" id="map-wrap">
    <svg id="world-map" viewBox="0 0 1000 500" preserveAspectRatio="xMidYMid meet">
      <!-- Simplified world map paths -->
      <rect width="1000" height="500" fill="#0d1117"/>
      <!-- Ocean grid -->
      <line x1="0" y1="250" x2="1000" y2="250" stroke="#1a2030" stroke-width="1"/>
      <line x1="500" y1="0" x2="500" y2="500" stroke="#1a2030" stroke-width="1"/>
      <!-- Continents (simplified) -->
      <!-- Asia -->
      <path d="M550 80 L750 60 L850 120 L900 200 L820 280 L700 300 L620 260 L560 200 Z" fill="#1a2540" stroke="#2a3550" stroke-width="1"/>
      <!-- India -->
      <path d="M620 200 L680 200 L700 280 L650 300 L620 260 Z" fill="#1e3060" stroke="#2a4070" stroke-width="1"/>
      <!-- Europe -->
      <path d="M450 80 L550 80 L560 160 L480 180 L440 140 Z" fill="#1a2540" stroke="#2a3550" stroke-width="1"/>
      <!-- Africa -->
      <path d="M460 200 L560 200 L560 380 L500 400 L440 360 L440 240 Z" fill="#1a2540" stroke="#2a3550" stroke-width="1"/>
      <!-- Russia -->
      <path d="M500 60 L850 40 L860 120 L750 120 L550 120 Z" fill="#1a2540" stroke="#2a3550" stroke-width="1"/>
      <!-- South Africa -->
      <path d="M480 340 L540 340 L540 400 L510 420 L480 400 Z" fill="#1e3060" stroke="#2a4070" stroke-width="1"/>
      <!-- Americas -->
      <path d="M100 80 L250 80 L280 200 L260 320 L220 380 L160 360 L120 280 L80 200 Z" fill="#1a2540" stroke="#2a3550" stroke-width="1"/>
      <!-- Japan -->
      <path d="M820 140 L840 120 L860 160 L840 200 L820 180 Z" fill="#1e3060" stroke="#2a4070" stroke-width="1"/>
      <!-- Australia -->
      <path d="M760 300 L880 280 L900 380 L820 400 L760 360 Z" fill="#1a2540" stroke="#2a3550" stroke-width="1"/>
    </svg>
    <div id="map-dots"></div>
    <div class="map-tooltip" id="map-tooltip"></div>
  </div>
</section>

<!-- CITY CARDS -->
<section>
  {% set countries = {"IN":["🇮🇳","India"],"JP":["🇯🇵","Japan"],"RU":["🇷🇺","Russia"],"ZA":["🇿🇦","South Africa"]} %}
  {% for code, info in countries.items() %}
  <div class="section-label" style="margin-top:40px;"><span class="flag-emoji">{{ info[0] }}</span> {{ info[1] }}</div>
  <div class="city-grid">
    {% for w in weather_data if w.country == code %}
    <div class="city-card" onclick="selectCity('{{ w.city }}')" data-city="{{ w.city }}" data-temp-c="{{ w.temp }}">
      <div class="city-header">
        <div>
          <div class="city-name">{{ w.city }}</div>
          <div class="city-country">{{ info[1] }}</div>
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
  {% endfor %}

  <!-- CUSTOM CITIES -->
  {% if custom_cities %}
  <div class="section-label" style="margin-top:40px;"><span class="flag-emoji">🌍</span> Custom Cities</div>
  <div class="city-grid">
    {% for w in custom_cities %}
    <div class="city-card" onclick="selectCity('{{ w.city }}')" data-city="{{ w.city }}" data-temp-c="{{ w.temp }}">
      <div class="city-header">
        <div><div class="city-name">{{ w.city }}</div><div class="city-country">Custom</div></div>
        <div class="city-icon">{{ w.icon }}</div>
      </div>
      <div class="city-temp">{{ w.temp }}°</div>
      <div class="city-condition">{{ w.condition }}</div>
      <div class="card-stats">
        <div><div class="card-stat-label">Humidity</div><div class="card-stat-value">{{ w.humidity }}%</div></div>
        <div><div class="card-stat-label">Wind</div><div class="card-stat-value">{{ w.wind_speed }} km/h</div></div>
        <div><div class="card-stat-label">UV</div><div class="card-stat-value">{{ w.uv_index }}</div></div>
        <div><div class="card-stat-label">Pressure</div><div class="card-stat-value">{{ w.pressure }}</div></div>
      </div>
    </div>
    {% endfor %}
  </div>
  {% endif %}
</section>

<!-- ADD CUSTOM CITY -->
<section class="add-city-section" style="margin-top:60px;">
  <div class="section-label">➕ Add Custom City</div>
  <div class="add-city-form">
    <div class="form-group">
      <label class="form-label">City Name</label>
      <input class="form-input" id="add-city-name" placeholder="e.g. London" type="text" style="width:180px;">
    </div>
    <div class="form-group">
      <label class="form-label">Latitude</label>
      <input class="form-input" id="add-city-lat" placeholder="e.g. 51.51" type="number" step="0.01" style="width:130px;">
    </div>
    <div class="form-group">
      <label class="form-label">Longitude</label>
      <input class="form-input" id="add-city-lon" placeholder="e.g. -0.12" type="number" step="0.01" style="width:130px;">
    </div>
    <button class="btn-add" onclick="addCustomCity()">+ Add City</button>
  </div>
  <div id="add-msg" class="add-msg" style="display:none;"></div>
</section>

</main>

<footer>
  <div class="footer-logo">Weather<span>Drift</span></div>
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
let historyData = {};   // city -> [temps over time]
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
    const t = document.getElementById('clock-'+code);
    const d = document.getElementById('date-'+code);
    if(t) t.textContent = now.toLocaleTimeString('en-GB',{timeZone:tz,hour12:false});
    if(d) d.textContent = now.toLocaleDateString('en-GB',{timeZone:tz,weekday:'short',day:'2-digit',month:'short'});
  }
}
updateClocks(); setInterval(updateClocks, 1000);

// ── Search ─────────────────────────────────────────────────────────────────
function handleSearch(q) {
  const box = document.getElementById('search-results');
  if (!q.trim()) { box.style.display='none'; return; }
  const matches = allCities.filter(c=>c.city.toLowerCase().includes(q.toLowerCase())).slice(0,8);
  if (!matches.length) { box.style.display='none'; return; }
  box.innerHTML = matches.map(c=>`
    <div class="search-result-item" onclick="selectCity('${c.city}');document.getElementById('city-search').value='';document.getElementById('search-results').style.display='none';">
      <span>${c.city}</span><span>${c.temp!==undefined?dispTemp(c.temp):''}</span>
    </div>`).join('');
  box.style.display='block';
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
  updateHistoryChart(d.city, d.temp);
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
      new Notification('WeatherDrift Alert', {body: alerts[0], icon:'🌤️'});
    }
  } else { bar.classList.remove('show'); }
}

function toggleNotifications() {
  if (Notification.permission === 'granted') {
    alert('Notifications already enabled!');
  } else {
    Notification.requestPermission().then(p => {
      if (p === 'granted') {
        new Notification('WeatherDrift', {body:'Weather alerts enabled! ✅'});
        document.getElementById('alert-bar') && document.querySelector('[onclick="toggleNotifications()"]').classList.add('active');
      }
    });
  }
}

// ── History chart (simple canvas) ─────────────────────────────────────────
const histChart = {};
function updateHistoryChart(city, temp) {
  if (!histChart[city]) histChart[city] = [];
  histChart[city].push({t: new Date().toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit'}), v: temp});
  if (histChart[city].length > 12) histChart[city].shift();
  document.getElementById('history-city-label').textContent = city;
  drawChart(histChart[city]);
}
function drawChart(points) {
  const canvas = document.getElementById('history-chart');
  const ctx = canvas.getContext('2d');
  canvas.width = canvas.offsetWidth;
  canvas.height = canvas.offsetHeight;
  if (points.length < 2) {
    ctx.fillStyle = document.body.classList.contains('dark') ? '#aaa' : '#888';
    ctx.font = '14px monospace';
    ctx.textAlign = 'center';
    ctx.fillText('Collecting temperature history...', canvas.width/2, canvas.height/2);
    return;
  }
  const pad = {t:20,r:20,b:40,l:50};
  const w = canvas.width - pad.l - pad.r;
  const h = canvas.height - pad.t - pad.b;
  const vals = points.map(p=>p.v);
  const minV = Math.min(...vals) - 2;
  const maxV = Math.max(...vals) + 2;
  ctx.clearRect(0,0,canvas.width,canvas.height);
  // Grid
  ctx.strokeStyle = document.body.classList.contains('dark') ? '#2a2a35' : '#eee';
  ctx.lineWidth = 1;
  for (let i=0;i<=4;i++) {
    const y = pad.t + h - (i/4)*h;
    ctx.beginPath(); ctx.moveTo(pad.l,y); ctx.lineTo(pad.l+w,y); ctx.stroke();
    ctx.fillStyle = document.body.classList.contains('dark') ? '#888' : '#999';
    ctx.font = '10px monospace'; ctx.textAlign = 'right';
    ctx.fillText(Math.round(minV+(maxV-minV)*i/4)+'°', pad.l-6, y+4);
  }
  // Line
  const xStep = w/(points.length-1);
  const yScale = h/(maxV-minV);
  ctx.beginPath();
  points.forEach((p,i) => {
    const x = pad.l + i*xStep;
    const y = pad.t + h - (p.v-minV)*yScale;
    i===0 ? ctx.moveTo(x,y) : ctx.lineTo(x,y);
  });
  ctx.strokeStyle = '#e8441a'; ctx.lineWidth = 2.5; ctx.stroke();
  // Fill
  ctx.lineTo(pad.l+(points.length-1)*xStep, pad.t+h);
  ctx.lineTo(pad.l, pad.t+h); ctx.closePath();
  ctx.fillStyle = 'rgba(232,68,26,.1)'; ctx.fill();
  // Dots + labels
  points.forEach((p,i) => {
    const x = pad.l + i*xStep;
    const y = pad.t + h - (p.v-minV)*yScale;
    ctx.beginPath(); ctx.arc(x,y,4,0,Math.PI*2);
    ctx.fillStyle='#e8441a'; ctx.fill();
    if (i % Math.ceil(points.length/6) === 0 || i===points.length-1) {
      ctx.fillStyle = document.body.classList.contains('dark') ? '#aaa' : '#888';
      ctx.font='9px monospace'; ctx.textAlign='center';
      ctx.fillText(p.t, x, pad.t+h+16);
    }
  });
}

// ── World map dots ─────────────────────────────────────────────────────────
function renderMapDots(weatherList) {
  const wrap = document.getElementById('map-wrap');
  const dotsEl = document.getElementById('map-dots');
  dotsEl.innerHTML = '';
  const W = wrap.offsetWidth, H = wrap.offsetHeight;
  weatherList.forEach(w => {
    // Mercator projection approx
    const x = ((w.lon + 180) / 360) * W;
    const latRad = w.lat * Math.PI / 180;
    const y = (1 - Math.log(Math.tan(latRad) + 1/Math.cos(latRad)) / Math.PI) / 2 * H;
    if (isNaN(x)||isNaN(y)||y<0||y>H) return;
    const dot = document.createElement('div');
    dot.className = 'map-dot';
    dot.style.left = x+'px'; dot.style.top = y+'px';
    // Color by temp
    const t = w.temp;
    dot.style.background = t>35?'#f44336':t>25?'#ff9800':t>15?'#4caf50':t>5?'#2196f3':'#9c27b0';
    dot.title = `${w.city}: ${dispTemp(t)}`;
    dot.addEventListener('mouseenter', e => {
      const tt = document.getElementById('map-tooltip');
      tt.innerHTML = `<b>${w.city}</b><br>${w.icon} ${dispTemp(t)}<br>${w.condition}`;
      tt.style.display='block'; tt.style.left=(x+14)+'px'; tt.style.top=(y-20)+'px';
    });
    dot.addEventListener('mouseleave', ()=>{ document.getElementById('map-tooltip').style.display='none'; });
    dot.addEventListener('click', ()=>selectCity(w.city));
    dotsEl.appendChild(dot);
  });
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

// ── Add custom city ────────────────────────────────────────────────────────
function addCustomCity() {
  const name = document.getElementById('add-city-name').value.trim();
  const lat  = parseFloat(document.getElementById('add-city-lat').value);
  const lon  = parseFloat(document.getElementById('add-city-lon').value);
  const msg  = document.getElementById('add-msg');
  if (!name || isNaN(lat) || isNaN(lon)) {
    msg.textContent='⚠️ Please fill all fields correctly.'; msg.style.display='block'; return;
  }
  msg.textContent='Adding city...'; msg.style.display='block';
  fetch('/api/add-city', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({name, lat, lon})
  })
  .then(r=>r.json())
  .then(d => {
    msg.textContent = d.success ? `✅ ${name} added! Refresh to see it.` : '❌ '+d.error;
    if (d.success) {
      document.getElementById('add-city-name').value='';
      document.getElementById('add-city-lat').value='';
      document.getElementById('add-city-lon').value='';
    }
  })
  .catch(()=>{ msg.textContent='❌ Failed to add city.'; });
}

// ── Share ──────────────────────────────────────────────────────────────────
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
  window.open('https://twitter.com/intent/tweet?text='+encodeURIComponent(`🌤️ ${city}: ${temp} — ${cond} | WeatherDrift`)+'&url='+encodeURIComponent(window.location.href),'_blank');
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
  ctx.fillText('WeatherDrift',760,460);
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
    if (currentCity) {
      const w=data.weather.find(x=>x.city===currentCity);
      if(w) updateFeaturedPanel(w);
    }
  }).catch(()=>{});
}

// ── Init ───────────────────────────────────────────────────────────────────
document.querySelectorAll('.city-card').forEach(card=>{
  const city=card.dataset.city;
  const rawC=parseFloat(card.dataset.tempC);
  if(city && !isNaN(rawC)) allCities.push({city, country:card.querySelector('.city-country')?.textContent||'', temp:rawC});
});

// Set rawc on feat-temp
const ft=document.getElementById('feat-temp');
if(ft) ft.dataset.rawc=parseFloat(ft.textContent)||25;

setInterval(autoRefresh, 60000);

// Twemoji
if (typeof twemoji!=='undefined') {
  window.addEventListener('load',()=>twemoji.parse(document.body));
}

// Initial map render after a moment
setTimeout(()=>{
  if (allCities.length) renderMapDots(allCities);
}, 500);

// Initial bg
setWeatherBg('{{ featured.condition }}');

console.log('WeatherDrift v2.0 ready ✅');
</script>
</body>
</html>
"""

# ── Flask Routes ─────────────────────────────────────────────────────────────
@app.route("/")
def index():
    weather = get_cached_weather()
    featured = weather[0] if weather else {}
    forecast  = get_forecast(featured.get("city","Mumbai"))
    all_c = get_all_cities()
    custom_weather = [w for w in weather if w["city"] in _custom_cities]
    return render_template_string(HTML_TEMPLATE,
        weather_data=weather,
        custom_cities=custom_weather,
        featured=featured,
        forecast=forecast,
        datetime=datetime.now().strftime("%A, %d %B %Y · %H:%M UTC"),
        total_cities=len(weather),
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

@app.route("/api/add-city", methods=["POST"])
def add_city():
    global _custom_cities
    data = request.get_json()
    name = data.get("name","").strip()
    lat  = data.get("lat")
    lon  = data.get("lon")
    if not name or lat is None or lon is None:
        return jsonify({"error":"Missing fields"}), 400
    try:
        lat = float(lat); lon = float(lon)
        if not (-90<=lat<=90 and -180<=lon<=180):
            raise ValueError
    except:
        return jsonify({"error":"Invalid coordinates"}), 400
    _custom_cities[name] = {"lat":lat,"lon":lon,"country":"CUSTOM"}
    # Fetch and add to cache immediately
    result = fetch_single_city(name, _custom_cities[name])
    if _cache["weather"]: _cache["weather"].append(result)
    return jsonify({"success":True,"city":name})

@app.route("/api/test")
def api_test():
    try:
        r=requests.get("https://api.open-meteo.com/v1/forecast?latitude=17.69&longitude=83.22&current_weather=true",timeout=10)
        d=r.json()
        return jsonify({"status":"✅ API working","temp":d["current_weather"]["temperature"]})
    except Exception as e:
        return jsonify({"status":"❌ API failed","error":str(e)}), 500

@app.route("/health")
def health():
    return jsonify({"status":"ok","cities":len(get_all_cities()),"cached":len(_cache["weather"] or [])})

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)