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
REFRESH_INTERVAL  = 900   # 15 min — open-meteo data updates every 15min anyway
CACHE_STALE_SECS  = 840   # consider stale after 14 min
STARTUP_FETCH_DELAY = 2   # seconds before first fetch after server start

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
    # Use current= (not deprecated current_weather=) for accurate real-time data
    # Request all fields we need directly as current values — no index guessing
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
        f"weather_code,wind_speed_10m,surface_pressure,visibility,"
        f"uv_index,precipitation_probability,is_day"
        f"&hourly=temperature_2m,relative_humidity_2m,apparent_temperature,"
        f"weather_code,wind_speed_10m,precipitation_probability,visibility,uv_index"
        f"&daily=weather_code,temperature_2m_max,temperature_2m_min,"
        f"sunrise,sunset,precipitation_probability_max"
        f"&timezone=auto&forecast_days=2"
    )
    aqi_url = (
        f"https://air-quality-api.open-meteo.com/v1/air-quality"
        f"?latitude={lat}&longitude={lon}&current=us_aqi&timezone=auto"
    )
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            data = r.json()

            # ── Current conditions (accurate real-time values) ──────────────
            cur  = data["current"]
            temp     = round(cur["temperature_2m"])
            humidity = cur.get("relative_humidity_2m", 60)
            feels    = round(cur.get("apparent_temperature", temp))
            wind     = round(cur.get("wind_speed_10m", 0))
            pressure = round(cur.get("surface_pressure", 1013))
            vis      = round(cur.get("visibility", 10000) / 1000, 1)
            uv       = round(cur.get("uv_index", 0), 1)
            rain_now = cur.get("precipitation_probability", 0) or 0
            wcode    = cur.get("weather_code", 0)
            icon, condition = get_weather_icon(wcode)

            # ── Find current hour index in hourly array ─────────────────────
            hourly     = data.get("hourly", {})
            h_times    = hourly.get("time", [])
            now_str    = cur.get("time", "")[:13]   # "2024-03-08T14"
            try:
                now_h = next(i for i, t in enumerate(h_times) if t[:13] == now_str)
            except StopIteration:
                now_h = datetime.now().hour

            # ── Sunrise / Sunset ────────────────────────────────────────────
            daily   = data.get("daily", {})
            sunrise = daily.get("sunrise", [""])[0]
            sunset  = daily.get("sunset",  [""])[0]
            sunrise_t = sunrise.split("T")[-1][:5] if sunrise else "06:00"
            sunset_t  = sunset.split("T")[-1][:5]  if sunset  else "18:00"

            # ── AQI ─────────────────────────────────────────────────────────
            aqi_val = 50
            try:
                aq      = requests.get(aqi_url, timeout=8).json()
                aqi_val = int(aq.get("current", {}).get("us_aqi") or 50)
            except: pass
            aqi_label, aqi_color = get_aqi_label(aqi_val)

            # ── Hourly strip (next 8 slots × 3h) ───────────────────────────
            hourly_fc = []
            h_wcode   = hourly.get("weather_code",             [wcode]*48)
            h_temp    = hourly.get("apparent_temperature",     [feels]*48)
            h_rain    = hourly.get("precipitation_probability",[0]*48)
            h_times_full = hourly.get("time", [])
            for offset in range(0, 24, 3):
                idx = min(now_h + offset, len(h_wcode) - 1)
                if idx < 0 or idx >= len(h_times_full): continue
                h_icon, _ = get_weather_icon(h_wcode[idx])
                slot_time = h_times_full[idx][11:16] if idx < len(h_times_full) else f"{(now_h+offset)%24:02d}:00"
                hourly_fc.append({
                    "hour": slot_time,
                    "temp": round(h_temp[idx]) if idx < len(h_temp) else temp,
                    "icon": h_icon,
                    "rain": h_rain[idx] if idx < len(h_rain) else 0,
                })

            return {
                "city": city, "country": coords["country"],
                "temp": temp, "feels_like": feels,
                "humidity": humidity, "wind_speed": wind,
                "condition": condition, "icon": icon,
                "uv_index": uv, "visibility": vis, "pressure": pressure,
                "sunrise": sunrise_t, "sunset": sunset_t,
                "rain_prob": rain_now,
                "aqi": aqi_val, "aqi_label": aqi_label, "aqi_color": aqi_color,
                "hourly": hourly_fc, "lat": lat, "lon": lon,
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
    """Fetch fresh weather for all cities and update cache."""
    global _cache
    t0 = time.time()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching weather for all cities...")
    try:
        data = get_weather_data()
        if data:                        # only update if we got real data
            _cache["weather"]      = data
            _cache["timestamp"]    = time.time()
            _cache["last_updated"] = datetime.now().strftime("%H:%M IST")
            elapsed = round(time.time() - t0, 1)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Cache refreshed — {len(data)} cities in {elapsed}s")
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Refresh skipped — no data returned")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Refresh error: {e}")

def is_cache_stale():
    """True if cache is empty or older than CACHE_STALE_SECS."""
    return (_cache["weather"] is None or
            (time.time() - _cache["timestamp"]) > CACHE_STALE_SECS)

def background_refresh():
    """Background thread: wait briefly after startup, then refresh on schedule."""
    time.sleep(STARTUP_FETCH_DELAY)   # let gunicorn fully start
    while True:
        try:
            refresh_cache()
        except Exception as e:
            print(f"BG refresh error: {e}")
        time.sleep(REFRESH_INTERVAL)

def get_cached_weather():
    """Return cached data. If stale/missing, trigger immediate refresh."""
    if is_cache_stale():
        refresh_cache()
    return _cache["weather"] or []

_bg = threading.Thread(target=background_refresh, daemon=True)
_bg.start()

def get_forecast(city_name):
    all_c = get_all_cities()
    coords = all_c.get(city_name)
    if not coords: return []
    return _get_forecast_by_coords(coords["lat"], coords["lon"])

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
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
      integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin=""/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
        integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin="" defer></script>
<!-- PWA -->
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#0a0a0f">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="WeatherDrift">
<link rel="apple-touch-icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' fill='%230a0a0f'/><text y='.9em' font-size='80'>🌤️</text></svg>">
<style>
:root {
  --ink:#0d0d12; --paper:#f5f0eb; --accent:#e8441a; --accent2:#ff6b35;
  --muted:#8a8070; --card-bg:#ffffff; --border:#ddd8d0;
  --toolbar-bg:#13131a; --success:#00e676; --warn:#ffab00;
  --glass:rgba(255,255,255,.06); --glass-border:rgba(255,255,255,.1);
  --shadow:0 8px 32px rgba(0,0,0,.18);
  --radius:12px; --radius-sm:8px;
}
body.dark {
  --ink:#eeeae4; --paper:#0d0d12; --muted:#7a7a8a;
  --card-bg:#16161e; --border:#222230; --toolbar-bg:#0a0a0f;
  --glass:rgba(255,255,255,.04); --glass-border:rgba(255,255,255,.08);
}
*{margin:0;padding:0;box-sizing:border-box;}
html{overflow-x:hidden;}body{font-family:'DM Sans',sans-serif;background:var(--paper);color:var(--ink);min-height:100vh;transition:background .3s,color .3s;position:relative;}
body.dark{background:var(--paper);}
body.dark::before{content:'';position:fixed;inset:0;background:radial-gradient(ellipse 80% 50% at 50% -20%,rgba(232,68,26,.08) 0%,transparent 60%);pointer-events:none;z-index:0;}
body>*{position:relative;z-index:1;}
::selection{background:var(--accent);color:#fff;}
::-webkit-scrollbar{width:6px;height:6px;}
::-webkit-scrollbar-track{background:transparent;}
::-webkit-scrollbar-thumb{background:var(--accent);border-radius:3px;}

/* ── HEADER ── */
header{background:rgba(10,10,15,.96);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);color:#f2ede6;padding:0 40px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid rgba(232,68,26,.3);position:sticky;top:0;z-index:1000;box-shadow:0 4px 30px rgba(0,0,0,.3);}
.logo-block{display:flex;align-items:baseline;gap:12px;padding:16px 0;}
.logo{font-family:'Bebas Neue',sans-serif;font-size:2.4rem;letter-spacing:4px;color:#f2ede6;background:linear-gradient(135deg,#f2ede6 0%,#e8441a 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.logo span{-webkit-text-fill-color:var(--accent);}
.tagline{font-family:'Space Mono',monospace;font-size:.6rem;color:#666;letter-spacing:3px;text-transform:uppercase;}
.header-meta{font-family:'Space Mono',monospace;font-size:.68rem;color:#777;text-align:right;line-height:1.9;}
.live-badge{display:inline-flex;align-items:center;gap:6px;background:linear-gradient(135deg,var(--accent),var(--accent2));color:white;padding:3px 12px;font-size:.6rem;letter-spacing:2px;font-weight:700;margin-bottom:4px;border-radius:20px;box-shadow:0 2px 12px rgba(232,68,26,.4);}
.live-dot{width:6px;height:6px;background:white;border-radius:50%;animation:pulse 1.5s infinite;}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}

/* ── TOOLBAR ── */
.toolbar{background:var(--toolbar-bg);padding:10px 40px;display:flex;align-items:center;gap:10px;flex-wrap:wrap;border-bottom:1px solid rgba(255,255,255,.06);position:relative;z-index:500;}
.search-wrap{position:relative;flex:1;min-width:200px;max-width:360px;overflow:visible;}
.search-wrap input{width:100%;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.12);border-radius:6px;padding:8px 14px 8px 36px;color:#f2ede6;font-family:'Space Mono',monospace;font-size:.72rem;letter-spacing:1px;outline:none;transition:border .2s;}
.search-wrap input::placeholder{color:#666;}
.search-wrap input:focus{border-color:var(--accent);}
.search-icon{position:absolute;left:10px;top:50%;transform:translateY(-50%);font-size:.9rem;pointer-events:none;}
/* #search-results styled via JS for guaranteed z-index above all stacking contexts */
.search-result-item{padding:10px 14px;font-family:'Space Mono',monospace;font-size:.7rem;color:#ccc;cursor:pointer;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid rgba(255,255,255,.05);}
.search-result-item:hover{background:rgba(232,68,26,.15);color:white;}
.toolbar-btn{background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.12);border-radius:6px;padding:7px 14px;color:#ccc;font-family:'Space Mono',monospace;font-size:.68rem;letter-spacing:1px;cursor:pointer;transition:all .2s;white-space:nowrap;}
.toolbar-btn:hover,.toolbar-btn.active{background:var(--accent);color:white;border-color:var(--accent);}

/* ── CLOCKS ── */
.clocks-bar{background:#111118;padding:8px 40px;display:flex;gap:30px;overflow-x:auto;border-bottom:1px solid rgba(255,255,255,.04);position:relative;z-index:10;}
.clocks-bar::-webkit-scrollbar{height:3px;}
.clocks-bar::-webkit-scrollbar-thumb{background:var(--accent);}
.clock-item{display:flex;align-items:center;gap:10px;white-space:nowrap;}
.clock-flag{font-size:1.2rem;font-family:"Segoe UI Emoji","Apple Color Emoji","Noto Color Emoji",sans-serif;}
.clock-info{display:flex;flex-direction:column;}
.clock-country{font-family:'Space Mono',monospace;font-size:.55rem;color:#666;letter-spacing:2px;text-transform:uppercase;}
.clock-time{font-family:'Space Mono',monospace;font-size:.85rem;color:#f2ede6;font-weight:700;}
.clock-date{font-family:'Space Mono',monospace;font-size:.55rem;color:var(--accent);}

/* ── TICKER ── */
.ticker-wrap{background:var(--accent);overflow:hidden;padding:10px 0;position:relative;z-index:10;}
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
.city-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:12px;margin-bottom:60px;}
.city-card{background:var(--card-bg);border:1px solid var(--border);border-radius:var(--radius);padding:24px;cursor:pointer;transition:transform .25s cubic-bezier(.34,1.56,.64,1),box-shadow .25s,border-color .25s;animation:fadeUp .5s ease both;position:relative;overflow:hidden;}
.city-card::after{content:'';position:absolute;inset:0;border-radius:var(--radius);background:linear-gradient(135deg,rgba(232,68,26,.06) 0%,transparent 60%);opacity:0;transition:opacity .25s;}
body.dark .city-card{background:#13131c;border-color:#1e1e2e;}
.city-card.selected{border-color:var(--accent);box-shadow:0 0 0 2px var(--accent),var(--shadow);transform:translateY(-3px);}
.city-card.selected::after{opacity:1;}
.city-card.selected .city-name,.city-card.selected .city-temp,.city-card.selected .card-stat-value{color:var(--accent)!important;}
.city-card:hover{border-color:rgba(232,68,26,.5);box-shadow:var(--shadow);transform:translateY(-4px);}
.city-card:hover::after{opacity:1;}
body.dark .city-card:hover{background:#1a1a26;}
.city-delete-btn{position:absolute;top:10px;right:10px;background:rgba(244,67,54,.1);border:1px solid rgba(244,67,54,.3);color:#f44336;width:26px;height:26px;border-radius:50%;font-size:.7rem;cursor:pointer;display:none;align-items:center;justify-content:center;z-index:20;transition:all .2s;line-height:1;}
.city-card:hover .city-delete-btn{display:flex;}
.city-delete-btn:hover{background:#f44336;color:#fff;transform:scale(1.1);}
.city-header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px;}
.city-name{font-family:'Bebas Neue',sans-serif;font-size:1.7rem;letter-spacing:2px;color:var(--ink);transition:color .2s;line-height:1;}
.city-country{font-family:'Space Mono',monospace;font-size:.58rem;letter-spacing:1.5px;color:var(--muted);text-transform:uppercase;margin-top:4px;}
.city-icon{font-size:2rem;font-family:"Segoe UI Emoji","Apple Color Emoji","Noto Color Emoji",sans-serif;filter:drop-shadow(0 2px 6px rgba(0,0,0,.2));}
.city-temp{font-family:'Bebas Neue',sans-serif;font-size:3.2rem;background:linear-gradient(135deg,var(--accent),var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;line-height:1;margin-bottom:4px;}
.city-condition{font-size:.8rem;color:var(--muted);font-weight:500;margin-bottom:10px;}
.city-badges{display:flex;gap:5px;margin-bottom:10px;flex-wrap:wrap;}
.badge{font-family:'Space Mono',monospace;font-size:.52rem;padding:2px 8px;border-radius:20px;font-weight:700;letter-spacing:.5px;}
.badge-aqi{background:rgba(0,230,118,.12);color:#00e676;border:1px solid rgba(0,230,118,.2);}
.badge-rain{background:rgba(79,195,247,.12);color:#4fc3f7;border:1px solid rgba(79,195,247,.2);}
.card-stats{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding-top:14px;border-top:1px solid var(--border);}
.card-stat-label{font-family:'Space Mono',monospace;font-size:.52rem;letter-spacing:1.5px;color:var(--muted);text-transform:uppercase;}
.card-stat-value{font-size:.88rem;font-weight:600;color:var(--ink);margin-top:2px;}

/* ── FORECAST ── */
.forecast-section{margin-bottom:60px;}
.forecast-strip{display:grid;grid-template-columns:repeat(7,1fr);gap:8px;margin-bottom:60px;}
.forecast-day{background:var(--card-bg);border:1px solid var(--border);border-radius:var(--radius);padding:18px 12px;text-align:center;animation:fadeUp .5s ease both;transition:transform .2s,box-shadow .2s,border-color .2s;cursor:default;}
body.dark .forecast-day{background:#13131c;border-color:#1e1e2e;}
.forecast-day:hover{transform:translateY(-3px);box-shadow:var(--shadow);border-color:rgba(232,68,26,.4);}
.forecast-label{font-family:'Space Mono',monospace;font-size:.58rem;letter-spacing:2px;color:var(--muted);text-transform:uppercase;margin-bottom:10px;}
.forecast-icon{font-size:1.8rem;margin-bottom:8px;font-family:"Segoe UI Emoji","Apple Color Emoji","Noto Color Emoji",sans-serif;filter:drop-shadow(0 2px 4px rgba(0,0,0,.2));}
.forecast-hi{font-family:'Bebas Neue',sans-serif;font-size:1.8rem;background:linear-gradient(135deg,var(--accent),var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.forecast-lo{font-family:'Space Mono',monospace;font-size:.6rem;color:var(--muted);margin-top:2px;}
.forecast-rain-bar{height:4px;background:rgba(79,195,247,.15);border-radius:2px;margin-top:8px;overflow:hidden;}
.forecast-rain-fill{height:100%;background:linear-gradient(90deg,#4fc3f7,#0288d1);border-radius:2px;transition:width .5s ease;}

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
.leaflet-weather-tooltip{background:#0d1a2a!important;border:1px solid #e8441a!important;color:#f2ede6!important;border-radius:6px!important;font-family:monospace!important;padding:10px 14px!important;box-shadow:0 6px 24px rgba(0,0,0,.7)!important;}
.leaflet-weather-tooltip::before{border-top-color:#e8441a!important;}
.leaflet-tooltip-top::before{border-top-color:#e8441a!important;}
.leaflet-weather-popup .leaflet-popup-content-wrapper{background:#0d1a2a!important;border:1px solid #e8441a!important;color:#f2ede6!important;border-radius:8px!important;font-family:monospace!important;box-shadow:0 8px 32px rgba(0,0,0,.8)!important;padding:0!important;}
.leaflet-weather-popup .leaflet-popup-content{margin:14px 16px!important;color:#f2ede6!important;}
.leaflet-weather-popup .leaflet-popup-tip{background:#e8441a!important;}
.leaflet-weather-popup .leaflet-popup-close-button{color:#e8441a!important;font-size:1rem!important;top:8px!important;right:10px!important;}
.leaflet-container{font-family:monospace!important;background:#050d1a!important;}
.leaflet-control-scale-line{background:rgba(5,13,26,.8)!important;border-color:#555!important;color:#888!important;font-family:monospace!important;font-size:.55rem!important;letter-spacing:.5px!important;}
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
footer{background:rgba(10,10,15,.98);backdrop-filter:blur(10px);color:#f2ede6;padding:40px;display:flex;justify-content:space-between;align-items:center;border-top:1px solid rgba(232,68,26,.25);}
.footer-logo{font-family:'Bebas Neue',sans-serif;font-size:2rem;letter-spacing:3px;background:linear-gradient(135deg,#f2ede6,var(--accent));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.footer-logo span{-webkit-text-fill-color:var(--accent);}
.footer-info{font-family:'Space Mono',monospace;font-size:.65rem;color:#555;text-align:right;line-height:2;}

/* ── LANGUAGE TRANSLATIONS ── */
[data-lang="te"] .lang-en{display:none!important;}
[data-lang="hi"] .lang-en{display:none!important;}
[data-lang="en"] .lang-te{display:none!important;}
[data-lang="en"] .lang-hi{display:none!important;}
[data-lang="te"] .lang-hi{display:none!important;}
[data-lang="hi"] .lang-te{display:none!important;}

/* ── PWA INSTALL BANNER ── */
.pwa-banner{position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:#13131c;border:1px solid var(--accent);border-radius:var(--radius);padding:14px 24px;display:flex;align-items:center;gap:14px;z-index:9999;box-shadow:0 8px 32px rgba(0,0,0,.5);font-family:'Space Mono',monospace;font-size:.7rem;color:#f2ede6;animation:fadeUp .4s ease;display:none;}
.pwa-banner.show{display:flex;}
.pwa-banner button{background:var(--accent);border:none;color:#fff;padding:7px 16px;border-radius:var(--radius-sm);cursor:pointer;font-family:'Space Mono',monospace;font-size:.68rem;font-weight:700;}

/* ── WEATHER ALERTS PANEL ── */
.alerts-panel{display:none;background:#13131c;border:1px solid rgba(232,68,26,.3);border-radius:var(--radius);padding:20px 24px;margin-bottom:30px;animation:fadeUp .3s ease;}
.alerts-panel.show{display:block;}
.alert-item{display:flex;align-items:flex-start;gap:12px;padding:12px 0;border-bottom:1px solid rgba(255,255,255,.06);}
.alert-item:last-child{border-bottom:none;}
.alert-icon{font-size:1.4rem;flex-shrink:0;}
.alert-body{flex:1;}
.alert-title{font-family:'Space Mono',monospace;font-size:.7rem;font-weight:700;color:#f2ede6;margin-bottom:3px;}
.alert-desc{font-family:'Space Mono',monospace;font-size:.6rem;color:#888;}
.alert-severity-high{border-left:3px solid #f44336;padding-left:12px;}
.alert-severity-med{border-left:3px solid #ff9800;padding-left:12px;}
.alert-severity-low{border-left:3px solid #4caf50;padding-left:12px;}

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

<!-- PWA INSTALL BANNER -->
<div class="pwa-banner" id="pwa-banner">
  <span>📲</span>
  <span>
    <span class="lang-en">Install WeatherDrift as an app</span>
    <span class="lang-te">WeatherDrift app గా install చేయండి</span>
    <span class="lang-hi">WeatherDrift को app की तरह install करें</span>
  </span>
  <button onclick="installPWA()">
    <span class="lang-en">Install</span>
    <span class="lang-te">Install</span>
    <span class="lang-hi">Install</span>
  </button>
  <button onclick="document.getElementById('pwa-banner').classList.remove('show')" style="background:none;color:#888;padding:4px 8px;">✕</button>
</div>

<header>
  <div class="logo-block">
    <div>
      <div class="logo">AHOY Weather<span>Drift</span></div>
      <div class="tagline" data-i18n="tagline">Global Atmospheric Intelligence</div>
    </div>
  </div>
  <div class="header-meta">
    <div class="live-badge"><span class="live-dot"></span> <span data-i18n="live">LIVE</span></div>
    <div>{{ datetime }}</div>
    <div>{{ total_cities }} cities monitored</div>
    <div id="last-updated-label" style="color:#e8441a;font-size:.6rem;">Last updated: {{ last_updated }}</div>
  </div>
</header>

<!-- TOOLBAR -->
<div class="toolbar">
  <div class="search-wrap">
    <span class="search-icon">🔍</span>
    <input type="text" id="city-search" placeholder="Search any city..."
      autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false"
      role="combobox" aria-autocomplete="list" aria-expanded="false"
      oninput="handleSearch(this.value)"
      onfocus="if(this.value.trim()) { document.getElementById('search-results').style.display='block'; _positionSearchDrop(); }">
  </div>
  <button class="toolbar-btn" id="unit-btn" onclick="toggleUnit()">°C / °F</button>
  <button class="toolbar-btn" id="dark-btn" onclick="toggleDark()"><span class="lang-en">🌙 Dark</span><span class="lang-te">🌙 చీకటి</span><span class="lang-hi">🌙 डार्क</span></button>
  <button class="toolbar-btn" id="compare-btn" onclick="toggleCompare()"><span class="lang-en">⚖️ Compare</span><span class="lang-te">⚖️ పోలిక</span><span class="lang-hi">⚖️ तुलना</span></button>
  <button class="toolbar-btn" onclick="toggleNotifications()"><span class="lang-en">🔔 Alerts</span><span class="lang-te">🔔 హెచ్చరికలు</span><span class="lang-hi">🔔 चेतावनी</span></button>
  <button class="toolbar-btn" id="lang-btn" onclick="toggleLang()" title="Language / భాష">🌐 EN</button>
  <button class="toolbar-btn" id="install-btn" onclick="installPWA()" style="display:none;" title="Install App">📲 <span class="lang-en">Install</span><span class="lang-te">ఇన్‌స్టాల్</span><span class="lang-hi">इंस्टॉल</span></button>
</div>

<!-- CLOCKS + TICKER wrapped in low-z container so search dropdown always above -->
<div style="position:relative;z-index:1;">
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
</div><!-- end low-z container -->

<main>

<!-- COMPARE PANEL -->
<div class="compare-panel" id="compare-panel">
  <div class="section-label" data-i18n="compare">⚖️ City Comparison</div>
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

<!-- WEATHER ALERTS PANEL -->
<div class="alerts-panel" id="alerts-panel">
  <div class="section-label" style="margin-bottom:16px;">
    ⚡ <span class="lang-en">Active Weather Alerts</span>
    <span class="lang-te">వాతావరణ హెచ్చరికలు</span>
    <span class="lang-hi">मौसम चेतावनियां</span>
  </div>
  <div id="alerts-list">
    <div style="font-family:monospace;font-size:.7rem;color:#666;">
      <span class="lang-en">No active alerts. All clear ✅</span>
      <span class="lang-te">హెచ్చరికలు లేవు ✅</span>
      <span class="lang-hi">कोई चेतावनी नहीं ✅</span>
    </div>
  </div>
</div>

<!-- FEATURED -->
<section class="featured-section">
  <div class="section-label"><span data-i18n="featured">Featured City</span> <span id="featured-loading" style="display:none;color:var(--accent);font-size:.7rem;" data-i18n="loading">· Loading...</span></div>
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
        <div class="sun-item"><span data-i18n="sunrise">🌅 Sunrise</span> <span id="feat-sunrise">{{ featured.sunrise }}</span></div>
        <div class="sun-item"><span data-i18n="sunset">🌇 Sunset</span> <span id="feat-sunset">{{ featured.sunset }}</span></div>
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
        <div style="font-family:'Space Mono',monospace;font-size:.65rem;color:#aaa;" data-i18n="rain_prob">Rain Probability</div>
      </div>

      <div class="stats-row">
        <div class="stat"><span class="stat-label" data-i18n="humidity">Humidity</span><span class="stat-value" id="feat-humidity">{{ featured.humidity }}%</span></div>
        <div class="stat"><span class="stat-label" data-i18n="wind">Wind</span><span class="stat-value" id="feat-wind">{{ featured.wind_speed }} km/h</span></div>
        <div class="stat"><span class="stat-label" data-i18n="uv">UV Index</span><span class="stat-value" id="feat-uv">{{ featured.uv_index }}</span></div>
        <div class="stat"><span class="stat-label" data-i18n="pressure">Pressure</span><span class="stat-value" id="feat-pressure">{{ featured.pressure }} hPa</span></div>
        <div class="stat"><span class="stat-label" data-i18n="visibility">Visibility</span><span class="stat-value" id="feat-visibility">{{ featured.visibility }} km</span></div>
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
  <div class="section-label"><span data-i18n="history">📈 Temperature History</span> — <span id="history-city-label">{{ featured.city }}</span></div>
  <div class="chart-outer">
    <div class="chart-toolbar">
      <div class="chart-title">Live Temperature Trend</div>
      <div class="chart-tabs">
        <button class="chart-tab active" onclick="setChartMode('temp',this)" data-i18n="temp_chart">🌡 Temp</button>
        <button class="chart-tab" onclick="setChartMode('humidity',this)" data-i18n="hum_chart">💧 Humidity</button>
        <button class="chart-tab" onclick="setChartMode('wind',this)" data-i18n="wind_chart">💨 Wind</button>
      </div>
    </div>
    <div class="chart-stats-row">
      <div class="chart-stat"><div class="chart-stat-label" data-i18n="current">Current</div><div class="chart-stat-value" id="cs-current">--°</div></div>
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
  <div class="section-label" id="forecast-label"><span data-i18n="forecast">7-Day Outlook</span> · {{ featured.city }}</div>
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
  <div class="section-label" data-i18n="map">🗺️ World Weather Map</div>
  <div class="map-outer" style="isolation:isolate;">
    <div class="map-toolbar" style="flex-direction:column;align-items:stretch;gap:10px;">
      <!-- Row 1: view toggles + search + zoom -->
      <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;">
        <div class="map-view-btns">
          <button class="map-view-btn active" onclick="setMapView('dark')"      id="mv-dark">🌑 Dark</button>
          <button class="map-view-btn"        onclick="setMapView('night')"     id="mv-night">🌙 Night</button>
          <button class="map-view-btn"        onclick="setMapView('satellite')" id="mv-satellite">🛰️ Satellite</button>
          <button class="map-view-btn"        onclick="setMapView('street')"    id="mv-street">🗺️ Street</button>
          <button class="map-view-btn"        onclick="setMapView('topo')"      id="mv-topo">⛰️ Terrain</button>
          <button class="map-view-btn"        onclick="setMapView('outdoor')"   id="mv-outdoor">🥾 Outdoors</button>
          <button class="map-view-btn"        onclick="setMapView('light')"     id="mv-light">☀️ Light</button>
          <button class="map-view-btn"        onclick="setMapView('smooth')"    id="mv-smooth">🎨 Smooth</button>
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
            <button class="map-zoom-btn" onclick="mapLocateMe()" title="My location">📍</button>
            <button class="map-zoom-btn" onclick="mapFitAll()" title="Fit all cities">⊞</button>
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
  <div class="section-label" style="margin-top:40px;" data-country-label="{{ group.code }}">
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
        <div><div class="card-stat-label" data-i18n="humidity">Humidity</div><div class="card-stat-value">{{ w.humidity }}%</div></div>
        <div><div class="card-stat-label" data-i18n="wind">Wind</div><div class="card-stat-value">{{ w.wind_speed }} km/h</div></div>
        <div><div class="card-stat-label" data-i18n="uv">UV Index</div><div class="card-stat-value">{{ w.uv_index }}</div></div>
        <div><div class="card-stat-label" data-i18n="pressure">Pressure</div><div class="card-stat-value">{{ w.pressure }}</div></div>
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
  <div class="section-label" data-i18n="restore">♻️ Restore Removed Cities</div>
  <div style="background:var(--card-bg);border:2px solid var(--border);padding:24px;">
    <div id="restore-list" style="display:flex;flex-wrap:wrap;gap:10px;"></div>
    <div id="restore-empty" style="font-family:monospace;font-size:.7rem;color:#666;">No cities have been removed.</div>
  </div>
</section>

<section class="add-city-section" style="margin-top:60px;">
  <div class="section-label" data-i18n="addloc">➕ Add Location</div>
  <div style="background:var(--card-bg);border:2px solid var(--border);padding:30px;">

    <!-- Mode toggle -->
    <div style="display:flex;gap:8px;margin-bottom:20px;flex-wrap:wrap;">
      <button class="chart-tab active" id="mode-search" onclick="setAddMode('search')" data-i18n="quick_search">🔍 Quick Search</button>
      <button class="chart-tab" id="mode-browse" onclick="setAddMode('browse')" data-i18n="browse_region">🗂 Browse by Region</button>
    </div>

    <!-- QUICK SEARCH MODE -->
    <div id="add-mode-search">
      <div style="font-family:'Space Mono',monospace;font-size:.68rem;color:var(--muted);margin-bottom:16px;letter-spacing:1px;">
        Search any city, town, village, hamlet or rural area worldwide.
      </div>
      <div class="add-city-form">
        <div class="form-group" style="flex:1;min-width:220px;position:relative;">
          <label class="form-label" data-i18n="place_name">Place Name</label>
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
          style="opacity:.5;cursor:not-allowed;" data-i18n="add_btn">+ Add</button>
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
    <div data-i18n="footer_tagline">Real-time weather intelligence</div>
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

// Reposition search dropdown
// Uses position:absolute on body + scrollY — avoids backdrop-filter stacking context trap
function _positionSearchDrop() {
  const inp = document.getElementById('city-search');
  const box = document.getElementById('search-results');
  if (!inp || !box) return;
  document.body.appendChild(box);  // always last DOM node
  const r = inp.getBoundingClientRect();
  box.style.top   = (r.bottom + 4) + 'px';  // fixed = viewport coords, no scrollY
  box.style.left  = r.left + 'px';
  box.style.width = Math.max(r.width, 300) + 'px';
}
// Reposition on scroll/resize
window.addEventListener('scroll', _positionSearchDrop, true);
window.addEventListener('resize', _positionSearchDrop);

function handleSearch(q) {
  clearTimeout(_searchTimer);
  const box = document.getElementById('search-results');
  if (!q || !q.trim()) { box.style.display='none'; return; }
  box.style.display='block';
  _positionSearchDrop();   // position AFTER display:block so rect is valid

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
  // Use rich subtitle (district/state/country) if provided by map click, else country label
  const subtitle = d._subtitle || '';
  const countryLine = subtitle || cLabel;
  document.getElementById('feat-country').textContent = countryLine + ' · ' + t('updated');
  document.getElementById('feat-condition').textContent = safe(d.condition)+' — '+t('feels_like')+' '+(isCelsius?safe(d.feels_like,'°C'):toF(d.feels_like)+'°F');
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
let _leafletMap       = null;
let _leafletMarkers   = [];
let _lastWeatherList  = [];   // persists across zoom re-renders
let _onMapZoom        = null; // registered once in initLeafletMap
let _zoomTimer        = null; // debounce handle for zoom re-render
let _mapSearchTimer   = null;
let _mapSearchResults = [];
let _clickMarker      = null;

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
    // CartoDB Dark Matter — sleek dark base
    url:  'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    opts: { subdomains: 'abcd', maxZoom: 20, detectRetina: true },
  },
  satellite: {
    // ESRI World Imagery — free high-res satellite
    url:  'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    opts: { maxZoom: 19 },
  },
  street: {
    // OpenStreetMap standard tiles (official CDN)
    url:  'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    opts: { maxZoom: 19 },
  },
  topo: {
    // OpenTopoMap — elevation contours + terrain shading
    url:  'https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png',
    opts: { subdomains: 'abc', maxZoom: 17 },
  },
  light: {
    // CartoDB Positron — minimal light theme
    url:  'https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
    opts: { subdomains: 'abcd', maxZoom: 20, detectRetina: true },
  },
  smooth: {
    // Stadia Alidade Smooth — soft muted palette, great contrast for markers
    url:  'https://tiles.stadiamaps.com/tiles/alidade_smooth/{z}/{x}/{y}{r}.png',
    opts: { maxZoom: 20, detectRetina: true },
  },
  night: {
    // CartoDB Dark Matter (no labels) — pure dark night sky
    url:  'https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png',
    opts: { subdomains: 'abcd', maxZoom: 20, detectRetina: true },
  },
  outdoor: {
    // Stadia Outdoors — hiking trails, parks, nature features
    url:  'https://tiles.stadiamaps.com/tiles/outdoors/{z}/{x}/{y}{r}.png',
    opts: { maxZoom: 20, detectRetina: true },
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
    maxZoom: 20,
    zoomControl: false,
    attributionControl: false,
    preferCanvas: false,
  });

  // Default dark tile layer
  const v = MAP_VIEWS['dark'];
  _currentTileLayer = L.tileLayer(v.url, v.opts).addTo(_leafletMap);

  // Subtle scale bar bottom-left
  L.control.scale({ imperial: false, maxWidth: 120 }).addTo(_leafletMap);

  // Click anywhere → fetch weather at that point
  _leafletMap.on('click', function(e) {
    if (e.originalEvent && e.originalEvent.target.closest &&
        e.originalEvent.target.closest('.leaflet-popup')) return;
    mapClickWeather(e.latlng.lat.toFixed(5), e.latlng.lng.toFixed(5));
  });

  // Register zoomend ONCE here — debounced so it fires once after zoom settles
  _onMapZoom = function() {
    clearTimeout(_zoomTimer);
    _zoomTimer = setTimeout(function() {
      if (_lastWeatherList && _lastWeatherList.length) renderMapDots(null);
    }, 200);
  };
  _leafletMap.on('zoomend', _onMapZoom);
}

function setMapView(viewKey) {
  if (!MAP_VIEWS[viewKey]) return;
  if (!_leafletMap) initLeafletMap();

  // Swap tile layer
  if (_currentTileLayer) _leafletMap.removeLayer(_currentTileLayer);
  const v = MAP_VIEWS[viewKey];
  _currentTileLayer = L.tileLayer(v.url, v.opts).addTo(_leafletMap);

  // Ensure marker layer group is on top of new tile layer
  if (_markerLayer) {
    _markerLayer.remove();
    _markerLayer.addTo(_leafletMap);
  }
  if (_clickMarker) {
    _clickMarker.remove();
    _clickMarker.addTo(_leafletMap);
  }

  // Update active button
  _currentView = viewKey;
  document.querySelectorAll('.map-view-btn').forEach(b => b.classList.remove('active'));
  const btn = document.getElementById('mv-' + viewKey);
  if (btn) btn.classList.add('active');
}

// ── Marker layer group — keeps markers alive through tile swaps and zooms ──
let _markerLayer = null;

function _ensureMarkerLayer() {
  if (!_markerLayer) {
    _markerLayer = L.layerGroup().addTo(_leafletMap);
  }
}

function renderMapDots(weatherList) {
  if (typeof L === 'undefined') {
    setTimeout(() => renderMapDots(weatherList), 300);
    return;
  }
  if (!_leafletMap) initLeafletMap();
  _ensureMarkerLayer();

  // Persist list — pass null on zoom re-renders to reuse last list
  if (weatherList && weatherList.length) _lastWeatherList = weatherList;
  const list = _lastWeatherList;
  if (!list || !list.length) return;

  // Clear the layer group (markers detach cleanly, no map flicker)
  _markerLayer.clearLayers();
  _leafletMarkers = [];

  const zoom = _leafletMap.getZoom();

  list.forEach(w => {
    if (w.lat == null || w.lon == null) return;
    const color    = tempColor(w.temp);
    const temp     = w.temp !== undefined ? Math.round(w.temp) : '—';
    const safeCity = (w.city || '').replace(/'/g, "&#39;");

    // Dot size scales with zoom level
    const size      = zoom >= 10 ? 44 : zoom >= 7 ? 36 : zoom >= 5 ? 28 : zoom >= 4 ? 22 : 16;
    const fontSize  = size >= 36 ? '.62rem' : size >= 28 ? '.56rem' : '.48rem';
    const showLabel = size >= 22;
    const border    = size >= 28 ? 2.5 : 1.5;

    const icon = L.divIcon({
      className: '',
      html: `<div style="
          width:${size}px;height:${size}px;border-radius:50%;
          background:${color};
          border:${border}px solid rgba(255,255,255,.85);
          box-shadow:0 2px 10px rgba(0,0,0,.5),0 0 0 1px ${color}44;
          display:flex;align-items:center;justify-content:center;
          position:relative;cursor:pointer;user-select:none;
          animation:mapPulse 3s ease-in-out infinite;">
          ${showLabel ? `<span style="
            font-family:monospace;font-weight:700;font-size:${fontSize};
            color:#fff;text-shadow:0 1px 3px rgba(0,0,0,.9);
            line-height:1;pointer-events:none;">${temp}°</span>` : ''}
          <div style="
            position:absolute;inset:-6px;border-radius:50%;
            border:1px solid ${color};opacity:.25;
            animation:mapRing 3s ease-in-out infinite;
            pointer-events:none;"></div>
        </div>`,
      iconSize:   [size, size],
      iconAnchor: [size/2, size/2],
    });

    const tooltipHtml = `
      <div style="font-family:monospace;font-size:.68rem;line-height:1.75;min-width:170px;">
        <div style="font-weight:700;font-size:.8rem;margin-bottom:5px;color:${color};">
          ${w.icon||'&#x1F321;'} ${w.city}
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:2px 10px;">
          <div>Temp: ${temp}°C</div>
          <div>Feels: ${w.feels_like!==undefined?Math.round(w.feels_like)+'°C':'—'}</div>
          <div>Humidity: ${w.humidity||'—'}%</div>
          <div>Wind: ${w.wind_speed||'—'} km/h</div>
          <div>UV: ${w.uv_index||'—'}</div>
          <div>Rain: ${w.rain_prob||0}%</div>
        </div>
        <div style="margin-top:5px;padding-top:4px;border-top:1px solid rgba(255,255,255,.12);
          color:${w.aqi_color||'#4caf50'};font-size:.6rem;">
          AQI ${w.aqi||'—'} · ${w.aqi_label||'—'}
        </div>
      </div>`;

    const popupHtml = `
      <div style="font-family:monospace;font-size:.68rem;line-height:1.8;min-width:200px;padding:2px;">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
          <span style="font-size:1.6rem;">${w.icon||'&#x1F321;'}</span>
          <div>
            <div style="font-weight:700;font-size:.85rem;color:${color};">${w.city}</div>
            <div style="color:#aaa;font-size:.6rem;">${w.condition||'—'}</div>
          </div>
        </div>
        <div style="font-size:1.8rem;font-weight:700;color:${color};margin-bottom:6px;text-align:center;">
          ${temp}°C
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:3px 12px;font-size:.62rem;color:#ccc;">
          <div>Humidity: ${w.humidity||'—'}%</div>
          <div>Wind: ${w.wind_speed||'—'} km/h</div>
          <div>Sunrise: ${w.sunrise||'—'}</div>
          <div>Sunset: ${w.sunset||'—'}</div>
          <div>UV: ${w.uv_index||'—'}</div>
          <div>Rain: ${w.rain_prob||0}%</div>
        </div>
        <div style="margin-top:8px;padding-top:6px;border-top:1px solid rgba(255,255,255,.1);
          display:flex;align-items:center;justify-content:space-between;">
          <span style="color:${w.aqi_color||'#4caf50'};font-size:.6rem;">
            AQI ${w.aqi||'—'} · ${w.aqi_label||'—'}
          </span>
          <button onclick="selectCity('${safeCity}');_leafletMap.closePopup();"
            style="background:${color};border:none;color:#fff;padding:3px 10px;
              font-family:monospace;font-size:.58rem;border-radius:3px;cursor:pointer;
              font-weight:700;">SELECT</button>
        </div>
      </div>`;

    const marker = L.marker([w.lat, w.lon], {
        icon,
        zIndexOffset: Math.round((w.temp || 0) * 10),
      })
      .bindTooltip(tooltipHtml, {
        direction: 'top',
        offset:    [0, -(size / 2 + 4)],
        className: 'leaflet-weather-tooltip',
        sticky:    false,
      })
      .bindPopup(popupHtml, {
        className:   'leaflet-weather-popup',
        maxWidth:    240,
        offset:      [0, -(size / 2)],
        closeButton: true,
      })
      .on('click', function() { this.openPopup(); });

    _markerLayer.addLayer(marker);
    _leafletMarkers.push(marker);
  });

  // zoomend registered once in initLeafletMap — not here
}

// Fit map to show all city markers
function mapFitAll() {
  if (!_leafletMap || !_leafletMarkers.length) return;
  try {
    const group = L.featureGroup(_leafletMarkers);
    const bounds = group.getBounds();
    if (bounds.isValid()) {
      // animate:false prevents cascading zoomend events during bounds animation
      _leafletMap.fitBounds(bounds.pad(0.08), { animate: false, maxZoom: 6 });
    }
  } catch(e) {}
}

// Fly to user's GPS location
function mapLocateMe() {
  if (!navigator.geolocation) { alert('Geolocation not supported'); return; }
  navigator.geolocation.getCurrentPosition(
    pos => {
      const {latitude: lat, longitude: lon} = pos.coords;
      if (_leafletMap) _leafletMap.flyTo([lat, lon], 11, {duration: 1.5});
      mapClickWeather(lat.toFixed(5), lon.toFixed(5));
    },
    err => alert('Could not get your location: ' + err.message)
  );
}

function mapReset() {
  if (_leafletMap) _leafletMap.setView([20, 0], 2);
}

// Click anywhere on map to get weather
async function mapClickWeather(lat, lon) {
  // Remove previous click marker
  if (_clickMarker) { _clickMarker.remove(); _clickMarker = null; }

  // Show pulsing loading pin on map
  const loadIcon = L.divIcon({
    className: '',
    html: `<div style="width:12px;height:12px;border-radius:50%;background:#e8441a;border:2px solid #fff;animation:mapPulse 1s infinite;"></div>`,
    iconSize: [12, 12], iconAnchor: [6, 6],
  });
  _clickMarker = L.marker([lat, lon], {icon: loadIcon}).addTo(_leafletMap);

  // Show loading in featured panel and scroll to it
  document.getElementById('featured-loading').style.display = 'inline';
  document.querySelector('.featured-section').scrollIntoView({behavior:'smooth', block:'start'});

  const latF = parseFloat(lat), lonF = parseFloat(lon);
  const fallbackName = `${latF.toFixed(2)}°N, ${lonF.toFixed(2)}°E`;

  try {
    // Step 1: Reverse geocode → get full place name, district, state, country
    let placeName = fallbackName, country = '', countryCode = '', subtitle = '';
    try {
      const geoR = await fetch(`/api/reverse?lat=${lat}&lon=${lon}`);
      const geo  = await geoR.json();
      placeName   = geo.name    || fallbackName;
      country     = geo.country || '';
      countryCode = geo.country_code || '';
      // Build a rich subtitle: "District, State · Country"
      const parts = [];
      if (geo.district && geo.district !== placeName) parts.push(geo.district);
      if (geo.state    && geo.state    !== placeName) parts.push(geo.state);
      subtitle = parts.join(', ');
      if (country && country !== placeName) subtitle += (subtitle ? ' · ' : '') + country;
    } catch (_) { /* fallback name already set */ }

    // Step 2: Fetch live weather + 7-day forecast for this location
    const wxR = await fetch(
      `/api/preview?lat=${lat}&lon=${lon}` +
      `&name=${encodeURIComponent(placeName)}` +
      `&country=${encodeURIComponent(country)}`
    );
    const d = await wxR.json();

    // Step 3: Update featured panel with resolved name + subtitle
    d.city         = placeName;          // use resolved place name
    d.country      = countryCode || d.country;
    d._subtitle    = subtitle;           // district/state/country line
    updateFeaturedPanel(d);

    // Step 4: Update 7-day forecast with full area name
    updateForecast(placeName, d.forecast || []);

    document.getElementById('featured-loading').style.display = 'none';
    document.querySelectorAll('.city-card').forEach(c => c.classList.remove('selected'));
    currentCity = null;
    const badge = document.getElementById('preview-badge');
    if (badge) badge.style.display = 'inline-flex';

    // Step 5: Replace loading pin with green done marker
    if (_clickMarker) { _clickMarker.remove(); _clickMarker = null; }
    const doneIcon = L.divIcon({
      className: '',
      html: `<div style="width:14px;height:14px;border-radius:50%;background:#4caf50;border:2.5px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,.5);"></div>`,
      iconSize: [14, 14], iconAnchor: [7, 7],
    });
    _clickMarker = L.marker([lat, lon], {icon: doneIcon})
      .addTo(_leafletMap)
      .bindTooltip(
        `<div style="font-family:monospace;font-size:.68rem;line-height:1.6;">
          <div style="font-weight:700;">📍 ${placeName}</div>
          ${subtitle ? `<div style="color:#aaa;font-size:.6rem;">${subtitle}</div>` : ''}
          <div style="margin-top:3px;">🌡 ${d.temp !== undefined ? dispTemp(d.temp) : '—'} · ${d.condition || '—'}</div>
        </div>`,
        {direction: 'top', offset: [0, -10], className: 'leaflet-weather-tooltip'}
      )
      .openTooltip();

  } catch (err) {
    document.getElementById('featured-loading').style.display = 'none';
    if (_clickMarker) { _clickMarker.remove(); _clickMarker = null; }
  }
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
  // Update section label with location name
  const label = document.getElementById('forecast-label');
  if (label) label.textContent = t('forecast') + ' · ' + (cityName || '—');

  const strip = document.getElementById('forecast-strip');
  if (!strip) return;

  if (!fc || !fc.length) {
    strip.innerHTML = `<div style="font-family:monospace;font-size:.68rem;color:#555;padding:20px 0;">
      No forecast data available for this location.</div>`;
    return;
  }

  strip.innerHTML = fc.map(d => `
    <div class="forecast-day">
      <div class="forecast-label">${d.day}</div>
      <div class="forecast-icon">${d.icon}</div>
      <div class="forecast-hi">${dispTemp(d.high)}</div>
      <div class="forecast-lo">${dispTemp(d.low)} lo</div>
      <div class="forecast-rain-bar"><div class="forecast-rain-fill" style="width:${d.rain||0}%"></div></div>
    </div>`).join('');

  if (typeof twemoji !== 'undefined') twemoji.parse(strip);
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
        <div class="compare-row"><span>${t('condition')}</span><span>${w.condition}</span></div>
        <div class="compare-row"><span>${t('humidity')}</span><span>${w.humidity}%</span></div>
        <div class="compare-row"><span>${t('wind')}</span><span>${w.wind_speed} km/h</span></div>
        <div class="compare-row"><span>${t('uv')}</span><span>${w.uv_index}</span></div>
        <div class="compare-row"><span>AQI</span><span style="color:${w.aqi_color}">${w.aqi} · ${w.aqi_label}</span></div>
        <div class="compare-row"><span>${t('rain_label')}</span><span>${w.rain_prob}%</span></div>
        <div class="compare-row"><span>${t('sunrise')}</span><span>${w.sunrise}</span></div>
        <div class="compare-row"><span>${t('sunset')}</span><span>${w.sunset}</span></div>
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
    const ctrl = new AbortController();
    const timeoutId = setTimeout(() => ctrl.abort(), 14000);
    fetch('/api/geocode?q='+encodeURIComponent(q), {signal: ctrl.signal})
      .then(r => { clearTimeout(timeoutId); return r.json(); })
      .then(data => {
        _geoResults = data.results || [];
        if (data.error && !_geoResults.length) {
          box.innerHTML=`<div style="padding:12px 14px;font-family:monospace;font-size:.68rem;color:#f44336;">
            ✕ Search service unavailable. <span onclick="geocodeSearch('${q.replace(/'/g,"\\'")}');return false;"
              style="color:#e8441a;cursor:pointer;text-decoration:underline;">Retry</span>
          </div>`;
          return;
        }
        if (!_geoResults.length) {
          box.innerHTML='<div style="padding:12px 14px;font-family:monospace;font-size:.68rem;color:#888;">No results found. Try a different spelling or add country name.</div>';
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
      .catch(err => {
        clearTimeout(timeoutId);
        const isTimeout = err.name === 'AbortError';
        box.innerHTML=`<div style="padding:12px 14px;font-family:monospace;font-size:.68rem;color:#f44336;">
          ✕ ${isTimeout ? 'Search timed out.' : 'Search failed.'} 
          <span onclick="geocodeSearch(document.getElementById('add-city-name').value);return false;"
            style="color:#e8441a;cursor:pointer;text-decoration:underline;">Retry</span>
        </div>`;
      });
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
  if (!name) {
    msg.innerHTML='⚠️ Type a city name and select from the dropdown.';
    msg.style.color='#ff9800'; msg.style.display='block'; return;
  }
  if (isNaN(lat) || isNaN(lon)) {
    msg.innerHTML='⚠️ Select a result from the dropdown list first.';
    msg.style.color='#ff9800'; msg.style.display='block';
    // Re-trigger search so dropdown reappears
    const box = document.getElementById('geocode-results');
    if (box && name.length >= 2 && !_geoResults.length) geocodeSearch(name);
    return;
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
    if (!data.weather || !data.weather.length) return;

    updateAllCards(data.weather);
    updateTicker(data.weather);

    // Update last-updated label — show stale warning if data is old
    const l = document.getElementById('last-updated-label');
    if (l) {
      const ageMin = Math.round((data.cache_age || 0) / 60);
      if (data.is_stale) {
        l.textContent = 'Updating weather data...';
        l.style.color = '#ff9800';
      } else {
        l.textContent = 'Last updated: ' + data.last_updated +
          (ageMin > 0 ? ' (' + ageMin + ' min ago)' : ' (just now)');
        l.style.color = '#e8441a';
      }
    }

    // Record history for all cities
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

    // Update featured panel + chart for current city
    if (currentCity) {
      const w = data.weather.find(x => x.city === currentCity);
      if (w) { updateFeaturedPanel(w); drawChart(histData[currentCity]); }
    }

    // Refresh map markers
    if (_leafletMap) renderMapDots(data.weather);

    // Update alerts panel with fresh data
    updateAlertsPanel(data.weather);

    // If still stale, poll again in 15s to catch the in-progress refresh
    if (data.is_stale) setTimeout(autoRefresh, 15000);

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

// Run immediately after 3s (catches fresh data from server startup refresh)
// then poll every 15 min (matches server REFRESH_INTERVAL)
setTimeout(() => {
  autoRefresh();
  setInterval(autoRefresh, 900000);   // 15 min
}, 3000);

// Twemoji
if (typeof twemoji!=='undefined') {
  window.addEventListener('load',()=>twemoji.parse(document.body));
}

// ── Search dropdown portal — runs after full DOM load ──────────────────────
// Appended to body so it's outside ALL stacking contexts
(function() {
  const existing = document.getElementById('search-results');
  if (existing) existing.remove();          // remove any old one
  const el = document.createElement('div');
  el.id = 'search-results';
  Object.assign(el.style, {
    display:    'none',
    position:   'fixed',                  // fixed from viewport — body overflow-x no longer traps it
    zIndex:     '2147483647',
    background: '#1a1a22',
    border:     '1px solid rgba(255,255,255,.15)',
    borderRadius: '8px',
    maxHeight:  '340px',
    overflowY:  'auto',
    boxShadow:  '0 16px 48px rgba(0,0,0,.95)',
    minWidth:   '300px',
    pointerEvents: 'auto',
    fontFamily: 'monospace',
  });
  document.body.appendChild(el);
  console.log('[WeatherDrift] Search portal injected ✅');
})();

// Initial map render — init Leaflet then plot dots
setTimeout(()=>{
  initLeafletMap();
  if (allCities.length) {
    renderMapDots(allCities);
    // Auto-fit to show all markers on first load (slight delay for tiles to load)
    setTimeout(() => { if (_leafletMap && _leafletMarkers.length) mapFitAll(); }, 600);
  }
}, 600);

// Initial bg
setWeatherBg('{{ featured.condition }}');

console.log('AHOY WeatherDrift v3.0 ready ✅');

// ── LANGUAGE SWITCHER ──────────────────────────────────────────────────────
const LANGS = ['en', 'te', 'hi'];
const LANG_LABELS = { en: '🌐 EN', te: '🌐 తె', hi: '🌐 हि' };
let _currentLang = localStorage.getItem('wd-lang') || 'en';

// ── Complete Translation System ──────────────────────────────────────────
const T = {
  en: {
    // Header
    tagline:'Global Atmospheric Intelligence', live:'LIVE',
    // Toolbar
    dark:'🌙 Dark', compare:'⚖️ Compare', alerts:'🔔 Alerts', install:'📲 Install',
    search_ph:'Search any city...',
    // Section labels
    featured:'Featured City', loading:'· Loading...',
    history:'📈 Temperature History',
    forecast:'7-Day Outlook',
    map:'🗺️ World Weather Map',
    restore:'♻️ Restore Removed Cities',
    addloc:'➕ Add Location',
    compare_sec:'⚖️ City Comparison',
    alerts_title:'⚡ Active Weather Alerts',
    no_alerts:'No active alerts. All clear ✅',
    // Stats
    humidity:'Humidity', wind:'Wind', uv:'UV Index',
    pressure:'Pressure', visibility:'Visibility',
    sunrise:'🌅 Sunrise', sunset:'🌇 Sunset',
    rain_prob:'Rain Probability', feels_like:'Feels like',
    updated:'Updated just now', last_updated:'Last updated',
    current:'Current', condition:'Condition', rain_label:'Rain Prob.',
    // Chart tabs
    temp_chart:'🌡 Temp', hum_chart:'💧 Humidity', wind_chart:'💨 Wind',
    // Add form
    quick_search:'🔍 Quick Search', browse_region:'🗂 Browse by Region',
    place_name:'Place Name', add_btn:'+ Add',
    // Footer
    footer_tagline:'Real-time weather intelligence',
    // Countries
    india:'India', japan:'Japan', russia:'Russia', safrica:'South Africa', custom:'Custom',
    // Clocks
    clock_india:'India (IST)', clock_japan:'Japan (JST)',
    clock_russia:'Russia (MSK)', clock_safrica:'S.Africa (SAST)', clock_utc:'UTC',
    // Preview
    preview_only:'👁 PREVIEW ONLY',
    // Misc
    no_data:'No data', select_city:'Click to select',
    today:'Today',
  },
  te: {
    tagline:'ప్రపంచ వాతావరణ వేదిక', live:'లైవ్',
    dark:'🌙 చీకటి', compare:'⚖️ పోలిక', alerts:'🔔 హెచ్చరికలు', install:'📲 ఇన్‌స్టాల్',
    search_ph:'ఏ నగరైనా వెతకండి...',
    featured:'ఎంచుకున్న నగరం', loading:'· లోడవుతోంది...',
    history:'📈 ఉష్ణోగ్రత చరిత్ర',
    forecast:'7 రోజుల అంచనా',
    map:'🗺️ ప్రపంచ వాతావరణ మ్యాప్',
    restore:'♻️ తొలగించిన నగరాలు పునరుద్ధరించు',
    addloc:'➕ స్థానం జోడించు',
    compare_sec:'⚖️ నగర పోలిక',
    alerts_title:'⚡ వాతావరణ హెచ్చరికలు',
    no_alerts:'హెచ్చరికలు లేవు ✅',
    humidity:'తేమ', wind:'గాలి వేగం', uv:'UV సూచిక',
    pressure:'పీడనం', visibility:'దృశ్యమానత',
    sunrise:'🌅 సూర్యోదయం', sunset:'🌇 సూర్యాస్తమయం',
    rain_prob:'వర్షం సంభావ్యత', feels_like:'అనుభవమయ్యే',
    updated:'ఇప్పుడే నవీకరించబడింది', last_updated:'చివరి నవీకరణ',
    current:'ప్రస్తుతం', condition:'పరిస్థితి', rain_label:'వర్షం %',
    temp_chart:'🌡 ఉష్ణోగ్రత', hum_chart:'💧 తేమ', wind_chart:'💨 గాలి',
    quick_search:'🔍 త్వరిత శోధన', browse_region:'🗂 ప్రాంతం చూడు',
    place_name:'స్థల పేరు', add_btn:'+ జోడించు',
    footer_tagline:'రియల్-టైమ్ వాతావరణ సమాచారం',
    india:'భారతదేశం', japan:'జపాన్', russia:'రష్యా', safrica:'దక్షిణ ఆఫ్రికా', custom:'కస్టమ్',
    clock_india:'భారతదేశం (IST)', clock_japan:'జపాన్ (JST)',
    clock_russia:'రష్యా (MSK)', clock_safrica:'దక్షిణ ఆఫ్రికా (SAST)', clock_utc:'UTC',
    preview_only:'👁 ప్రివ్యూ మాత్రమే',
    no_data:'డేటా లేదు', select_city:'క్లిక్ చేయండి',
    today:'నేడు',
  },
  hi: {
    tagline:'वैश्विक मौसम केंद्र', live:'लाइव',
    dark:'🌙 डार्क', compare:'⚖️ तुलना', alerts:'🔔 चेतावनी', install:'📲 इंस्टॉल',
    search_ph:'कोई भी शहर खोजें...',
    featured:'चुना हुआ शहर', loading:'· लोड हो रहा है...',
    history:'📈 तापमान इतिहास',
    forecast:'7 दिन का पूर्वानुमान',
    map:'🗺️ विश्व मौसम मानचित्र',
    restore:'♻️ हटाए गए शहर वापस लाएं',
    addloc:'➕ स्थान जोड़ें',
    compare_sec:'⚖️ शहर तुलना',
    alerts_title:'⚡ मौसम चेतावनियां',
    no_alerts:'कोई चेतावनी नहीं ✅',
    humidity:'नमी', wind:'हवा', uv:'UV सूचकांक',
    pressure:'दबाव', visibility:'दृश्यता',
    sunrise:'🌅 सूर्योदय', sunset:'🌇 सूर्यास्त',
    rain_prob:'बारिश की संभावना', feels_like:'महसूस होता है',
    updated:'अभी अपडेट किया', last_updated:'अंतिम अपडेट',
    current:'वर्तमान', condition:'स्थिति', rain_label:'बारिश %',
    temp_chart:'🌡 तापमान', hum_chart:'💧 नमी', wind_chart:'💨 हवा',
    quick_search:'🔍 त्वरित खोज', browse_region:'🗂 क्षेत्र देखें',
    place_name:'स्थान का नाम', add_btn:'+ जोड़ें',
    footer_tagline:'रियल-टाइम मौसम जानकारी',
    india:'भारत', japan:'जापान', russia:'रूस', safrica:'दक्षिण अफ्रीका', custom:'कस्टम',
    clock_india:'भारत (IST)', clock_japan:'जापान (JST)',
    clock_russia:'रूस (MSK)', clock_safrica:'दक्षिण अफ्रीका (SAST)', clock_utc:'UTC',
    preview_only:'👁 केवल पूर्वावलोकन',
    no_data:'डेटा नहीं', select_city:'क्लिक करें',
    today:'आज',
  },
};

function t(key) { return (T[_currentLang]||T.en)[key] || T.en[key] || key; }

function applyTranslations() {
  const lang = _currentLang;

  // 1. data-i18n attributes
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const v = t(el.getAttribute('data-i18n'));
    if (v) el.textContent = v;
  });

  // 2. Toolbar buttons
  const darkBtn = document.getElementById('dark-btn');
  if (darkBtn) darkBtn.innerHTML = t('dark');
  const compareBtn = document.getElementById('compare-btn');
  if (compareBtn) compareBtn.innerHTML = t('compare');
  const alertsBtn = document.querySelector('.toolbar-btn[onclick="toggleNotifications()"]');
  if (alertsBtn) alertsBtn.innerHTML = t('alerts');
  const installBtn = document.getElementById('install-btn');
  if (installBtn && installBtn.style.display !== 'none') installBtn.innerHTML = t('install');

  // 3. Search placeholder
  const si = document.getElementById('city-search');
  if (si) si.placeholder = t('search_ph');

  // 4. Featured section
  const featLabel = document.querySelector('.featured-section .section-label');
  if (featLabel) {
    const loading = document.getElementById('featured-loading');
    featLabel.textContent = t('featured') + ' ';
    if (loading) { loading.textContent = t('loading'); featLabel.appendChild(loading); }
  }
  const fl = document.getElementById('featured-loading');
  if (fl) fl.textContent = t('loading');

  // 5. Clocks bar
  const clockMap = {
    'India (IST)':'clock_india','Japan (JST)':'clock_japan',
    'Russia (MSK)':'clock_russia','S.Africa (SAST)':'clock_safrica','UTC':'clock_utc'
  };
  document.querySelectorAll('.clock-country').forEach(el => {
    const key = Object.keys(clockMap).find(k => el.textContent.includes(k.split(' ')[0]));
    if (key) el.textContent = t(clockMap[key]);
  });

  // 6. Country section labels (flag emoji + translated name)
  document.querySelectorAll('.section-label[data-country-label]').forEach(el => {
    const code = el.getAttribute('data-country-label');
    const flagMap = {IN:'🇮🇳',JP:'🇯🇵',RU:'🇷🇺',ZA:'🇿🇦',CUSTOM:'🌍'};
    const nameMap = {IN:'india',JP:'japan',RU:'russia',ZA:'safrica',CUSTOM:'custom'};
    const flag = flagMap[code] || '';
    const name = t(nameMap[code] || 'custom');
    el.textContent = flag + ' ' + name;
  });

  // 7. Section labels (by content matching)
  document.querySelectorAll('.section-label').forEach(el => {
    const txt = el.textContent.trim();
    if (txt.includes('Temperature History'))    { const city = document.getElementById('history-city-label')?.textContent; el.textContent = t('history') + ' — '; if(city) { const s=document.createElement('span'); s.id='history-city-label'; s.textContent=city; el.appendChild(s); } }
    if (txt.includes('City Comparison'))        el.textContent = t('compare_sec');
    if (txt.includes('Restore Removed'))        el.textContent = t('restore');
    if (txt.includes('Add Location'))           el.textContent = t('addloc');
    if (txt.includes('World Weather'))          el.textContent = t('map');
  });

  // 8. Forecast label (keep city)
  const fc = document.getElementById('forecast-label');
  if (fc) {
    const city = fc.textContent.split('·')[1]?.trim() || '';
    fc.textContent = t('forecast') + (city ? ' · ' + city : '');
  }

  // 9. Last updated
  const lu = document.getElementById('last-updated-label');
  if (lu && lu.textContent && !lu.textContent.includes('Updating')) {
    const parts = lu.textContent.split(':');
    if (parts.length > 1) lu.textContent = t('last_updated') + ':' + parts.slice(1).join(':');
  }

  // 10. Preview badge
  const pb = document.getElementById('preview-badge');
  if (pb) pb.textContent = t('preview_only');

  // 11. Compare panel re-render if open
  const cp = document.getElementById('compare-panel');
  if (cp && cp.style.display !== 'none') setTimeout(loadCompare, 50);

  // 12. Alerts panel title & no-alerts text
  const at = document.querySelector('.alerts-panel .section-label');
  if (at) at.textContent = t('alerts_title');
  const al = document.getElementById('alerts-list');
  if (al && al.children.length === 1 && al.firstElementChild?.textContent?.includes('No active')) {
    al.firstElementChild.textContent = t('no_alerts');
  }
}

function applyLang(lang) {
  _currentLang = lang;
  localStorage.setItem('wd-lang', lang);
  document.documentElement.setAttribute('data-lang', lang);
  const btn = document.getElementById('lang-btn');
  if (btn) btn.textContent = LANG_LABELS[lang] || '🌐 EN';
  applyTranslations();
}
function toggleLang() {
  const idx  = LANGS.indexOf(_currentLang);
  const next = LANGS[(idx + 1) % LANGS.length];
  applyLang(next);
}

// Apply saved language on load
applyLang(_currentLang);

// ── PWA INSTALL ────────────────────────────────────────────────────────────
let _pwaPrompt = null;

window.addEventListener('beforeinstallprompt', e => {
  e.preventDefault();
  _pwaPrompt = e;
  // Show install button in toolbar
  const btn = document.getElementById('install-btn');
  if (btn) btn.style.display = 'inline-flex';
  // Show banner after 5 seconds
  setTimeout(() => {
    const banner = document.getElementById('pwa-banner');
    if (banner && !localStorage.getItem('wd-pwa-dismissed')) {
      banner.classList.add('show');
    }
  }, 5000);
});

async function installPWA() {
  if (!_pwaPrompt) return;
  _pwaPrompt.prompt();
  const { outcome } = await _pwaPrompt.userChoice;
  if (outcome === 'accepted') {
    localStorage.setItem('wd-pwa-dismissed', '1');
    const banner = document.getElementById('pwa-banner');
    if (banner) banner.classList.remove('show');
    const btn = document.getElementById('install-btn');
    if (btn) btn.style.display = 'none';
  }
  _pwaPrompt = null;
}

// Register service worker for PWA
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch(() => {});
}

// ── SMART WEATHER ALERTS ──────────────────────────────────────────────────
function updateAlertsPanel(weatherList) {
  const panel = document.getElementById('alerts-panel');
  const list  = document.getElementById('alerts-list');
  if (!panel || !list || !weatherList) return;

  const alerts = [];
  weatherList.forEach(w => {
    if (!w || !w.city) return;
    if (w.temp >= 42)
      alerts.push({ sev:'high', icon:'🌡️', city:w.city, en:`Extreme heat: ${w.temp}°C`, te:`అత్యధిక వేడి: ${w.temp}°C`, hi:`अत्यधिक गर्मी: ${w.temp}°C` });
    else if (w.temp >= 38)
      alerts.push({ sev:'med', icon:'☀️', city:w.city, en:`High heat: ${w.temp}°C`, te:`అధిక వేడి: ${w.temp}°C`, hi:`अधिक गर्मी: ${w.temp}°C` });
    if (w.temp <= 0)
      alerts.push({ sev:'high', icon:'🥶', city:w.city, en:`Freezing: ${w.temp}°C`, te:`మంచు చలి: ${w.temp}°C`, hi:`हिमशीत: ${w.temp}°C` });
    if (w.rain_prob >= 85)
      alerts.push({ sev:'high', icon:'🌧️', city:w.city, en:`Heavy rain likely: ${w.rain_prob}%`, te:`భారీ వర్షం: ${w.rain_prob}%`, hi:`भारी बारिश: ${w.rain_prob}%` });
    else if (w.rain_prob >= 65)
      alerts.push({ sev:'med', icon:'🌦️', city:w.city, en:`Rain possible: ${w.rain_prob}%`, te:`వర్షం సాధ్యమే: ${w.rain_prob}%`, hi:`बारिश संभव: ${w.rain_prob}%` });
    if (w.wind_speed >= 70)
      alerts.push({ sev:'high', icon:'💨', city:w.city, en:`Strong winds: ${w.wind_speed} km/h`, te:`బలమైన గాలులు: ${w.wind_speed} km/h`, hi:`तेज़ हवाएं: ${w.wind_speed} km/h` });
    if (w.aqi >= 200)
      alerts.push({ sev:'high', icon:'😷', city:w.city, en:`Hazardous air quality: AQI ${w.aqi}`, te:`ప్రమాదకర గాలి: AQI ${w.aqi}`, hi:`खतरनाक वायु: AQI ${w.aqi}` });
    else if (w.aqi >= 150)
      alerts.push({ sev:'med', icon:'😮', city:w.city, en:`Poor air quality: AQI ${w.aqi}`, te:`వాయు నాణ్యత తక్కువ: AQI ${w.aqi}`, hi:`खराब वायु: AQI ${w.aqi}` });
  });

  if (!alerts.length) {
    panel.classList.remove('show');
    return;
  }

  panel.classList.add('show');
  list.innerHTML = alerts.slice(0, 8).map(a => `
    <div class="alert-item alert-severity-${a.sev}">
      <span class="alert-icon">${a.icon}</span>
      <div class="alert-body">
        <div class="alert-title">${a.city}</div>
        <div class="alert-desc">
          <span class="lang-en">${a.en}</span>
          <span class="lang-te">${a.te}</span>
          <span class="lang-hi">${a.hi}</span>
        </div>
      </div>
    </div>`).join('');
}

// ── NOTIFICATIONS TOGGLE ──────────────────────────────────────────────────
function toggleNotifications() {
  const panel = document.getElementById('alerts-panel');
  if (panel) panel.classList.toggle('show');
}

// Run alerts on initial data
if (allCities && allCities.length) updateAlertsPanel(allCities);
</script>
</body>
</html>
"""

# ── Flask Routes ─────────────────────────────────────────────────────────────
@app.route("/")
def index():
    # If cache is stale, serve what we have and trigger background refresh
    # so next request gets fresh data (avoids blocking the page load)
    if is_cache_stale() and _cache["weather"] is not None:
        threading.Thread(target=refresh_cache, daemon=True).start()
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
    # Trigger background refresh if stale (non-blocking)
    if is_cache_stale() and _cache["weather"] is not None:
        threading.Thread(target=refresh_cache, daemon=True).start()
    weather = get_cached_weather()
    cache_age = round(time.time() - _cache["timestamp"])
    return jsonify({
        "weather":      weather,
        "last_updated": _cache["last_updated"],
        "cache_age":    cache_age,           # seconds since last refresh
        "is_stale":     is_cache_stale(),    # JS can show warning if True
    })

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
            headers={"User-Agent": "AHOY WeatherDrift/2.0 (railway.app; weather dashboard)"},
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
        """Fetch from Nominatim with retry on timeout."""
        for attempt in range(2):
            try:
                r = requests.get(
                    "https://nominatim.openstreetmap.org/search",
                    params=params,
                    headers={"User-Agent": "AHOY WeatherDrift/2.0 (railway.app; weather dashboard)"},
                    timeout=12
                )
                r.raise_for_status()
                return r.json()
            except requests.exceptions.Timeout:
                if attempt == 0: continue
                return []
            except Exception:
                return []
        return []

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
        print(f"Geocode error: {e}")
        return jsonify({"results": [], "error": str(e)}), 200   # 200 so JS can show friendly message

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
            headers={"User-Agent": "AHOY WeatherDrift/2.0 (railway.app; weather dashboard)"},
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
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&daily=weather_code,temperature_2m_max,temperature_2m_min,"
        f"precipitation_probability_max,wind_speed_10m_max"
        f"&timezone=auto&forecast_days=7"
    )
    try:
        data  = requests.get(url, timeout=10).json()
        daily = data["daily"]
        fc    = []
        for i in range(min(7, len(daily.get("time", [])))):
            d    = datetime.strptime(daily["time"][i], "%Y-%m-%d")
            icon, cond = get_weather_icon(daily["weather_code"][i])
            fc.append({
                "day":  "Today" if i == 0 else d.strftime("%a"),
                "date": daily["time"][i],
                "icon": icon, "condition": cond,
                "high": round(daily["temperature_2m_max"][i]),
                "low":  round(daily["temperature_2m_min"][i]),
                "rain": daily.get("precipitation_probability_max", [0]*7)[i] or 0,
                "wind": round(daily.get("wind_speed_10m_max", [0]*7)[i] or 0),
            })
        return fc
    except Exception as e:
        print(f"Forecast error: {e}")
        days  = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
        today = datetime.now().weekday()
        return [{"day": "Today" if i==0 else days[(today+i)%7],
                 "icon":"⛅","condition":"Partly Cloudy",
                 "high":28,"low":20,"rain":20,"wind":10}
                for i in range(7)]
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
            "https://api.open-meteo.com/v1/forecast?latitude=17.69&longitude=83.22"
            "&current=temperature_2m,weather_code&timezone=auto",
            timeout=10)
        d = r.json()
        return jsonify({"status": "✅ API working", "temp": d["current"]["temperature_2m"]})
    except Exception as e:
        return jsonify({"status": "❌ API failed", "error": str(e)}), 500


@app.route("/health")
def health():
    return jsonify({"status": "ok", "cities": len(get_all_cities()), "cached": len(_cache["weather"] or [])})


@app.route("/manifest.json")
def pwa_manifest():
    """PWA Web App Manifest — enables Add to Home Screen / Install."""
    manifest = {
        "name": "AHOY WeatherDrift",
        "short_name": "WeatherDrift",
        "description": "Global Weather Intelligence — Live weather for 60+ cities",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0a0a0f",
        "theme_color": "#e8441a",
        "orientation": "any",
        "icons": [
            {"src": "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' rx='20' fill='%230a0a0f'/><text y='.9em' font-size='80'>🌤️</text></svg>",
             "sizes": "192x192", "type": "image/svg+xml", "purpose": "any maskable"},
            {"src": "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><rect width='100' height='100' rx='20' fill='%230a0a0f'/><text y='.9em' font-size='80'>🌤️</text></svg>",
             "sizes": "512x512", "type": "image/svg+xml", "purpose": "any maskable"},
        ],
        "categories": ["weather", "utilities"],
        "lang": "en",
    }
    from flask import Response
    import json as _json
    return Response(_json.dumps(manifest), mimetype="application/manifest+json")


@app.route("/sw.js")
def service_worker():
    """Minimal service worker for PWA — cache-first for static, network-first for API."""
    sw_code = """
const CACHE = 'weatherdrift-v3';
const STATIC = ['/'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(STATIC)));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
  ));
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  // Network-first for API calls
  if (url.pathname.startsWith('/api/')) {
    e.respondWith(
      fetch(e.request).catch(() => caches.match(e.request))
    );
    return;
  }
  // Cache-first for everything else
  e.respondWith(
    caches.match(e.request).then(cached => {
      if (cached) return cached;
      return fetch(e.request).then(resp => {
        if (resp && resp.status === 200) {
          const clone = resp.clone();
          caches.open(CACHE).then(c => c.put(e.request, clone));
        }
        return resp;
      });
    })
  );
});
"""
    from flask import Response
    return Response(sw_code, mimetype="application/javascript",
                    headers={"Service-Worker-Allowed": "/"})


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)