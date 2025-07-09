import requests
import pandas as pd
from datetime import datetime
import numpy as np
import os

# ========== Helper functions ==========
def degrees_to_compass(deg):
    dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
    ix = int((deg + 22.5) // 45) % 8
    return dirs[ix]

def compass_to_arrow(dir_str):
    arrows = {
        'N': '↓', 'NE': '↙', 'E': '←', 'SE': '↖',
        'S': '↑', 'SW': '↗', 'W': '→', 'NW': '↘'
    }
    return arrows.get(dir_str, "")

# ========== Locations ==========
locations = {
    "Las Palmas": (28.1272, -15.4314),
    "Telde": (27.9924, -15.4192),
    "Arguineguín": (27.7581, -15.6835)
}

# ========== Webcam embeds ==========
webcams = {
    "Las Palmas": '<iframe src="https://in2thebeach.es/callbacks/camviewer_ext2.php?id=57" scrolling="no"></iframe>',
    "Telde": '<iframe src="https://in2thebeach.es/callbacks/camviewer_ext2.php?id=43" scrolling="no"></iframe>',
    "Arguineguín": '<iframe src="https://in2thebeach.es/callbacks/camviewer_ext2.php?id=71" scrolling="no"></iframe>'
}

# ========== Prepare output ==========
os.makedirs("docs", exist_ok=True)

dfs = []

for name, (lat, lon) in locations.items():
    url_weather = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=windspeed_10m,winddirection_10m,temperature_2m&timezone=auto"
    url_marine = f"https://marine-api.open-meteo.com/v1/marine?latitude={lat}&longitude={lon}&hourly=wave_height,wave_direction,wave_period&timezone=auto"
    
    df_weather = pd.DataFrame(requests.get(url_weather).json()["hourly"])
    df_weather["time"] = pd.to_datetime(df_weather["time"])
    df_marine = pd.DataFrame(requests.get(url_marine).json()["hourly"])
    df_marine["time"] = pd.to_datetime(df_marine["time"])

    now = datetime.now()
    next_24h = now + pd.Timedelta(hours=24)
    df_weather_today = df_weather[(df_weather["time"] >= now) & (df_weather["time"] < next_24h)]
    df_marine_today = df_marine[(df_marine["time"] >= now) & (df_marine["time"] < next_24h)]

    df = pd.merge(df_weather_today, df_marine_today, on="time", how="outer").sort_values("time").reset_index(drop=True)
    df = df.rename(columns={
        "windspeed_10m": "Wind Speed (m/s)",
        "winddirection_10m": "Wind Direction",
        "temperature_2m": "Air Temp (°C)",
        "wave_height": "Wave Height (m)",
        "wave_direction": "Wave Direction",
        "wave_period": "Wave Period (s)"
    })
    df["Wind Dir Compass"] = df["Wind Direction"].apply(lambda x: degrees_to_compass(x) if pd.notnull(x) else "")
    df["Wave Dir Compass"] = df["Wave Direction"].apply(lambda x: degrees_to_compass(x) if pd.notnull(x) else "")
    df["Wind Arrow"] = df["Wind Dir Compass"].apply(compass_to_arrow)
    df["Wave Arrow"] = df["Wave Dir Compass"].apply(compass_to_arrow)
    df["Wave Energy (kJ/m²)"] = (125 * (df["Wave Height (m)"]**2) * df["Wave Period (s)"]).round(0)
    df["Wave Power Index"] = (df["Wave Height (m)"] * df["Wave Period (s)"]).round(2)
    for col in ["Wind Speed (m/s)", "Air Temp (°C)", "Wave Height (m)", "Wave Period (s)"]:
        df[col] = df[col].round(1)
    df["Location"] = name
    dfs.append(df)

df_all = pd.concat(dfs).reset_index(drop=True)

def highlight_direction(val):
    return f"color: #33cccc; font-weight: bold" if isinstance(val, str) else ""
def color_wave(val):
    color = int(220 - min(200, val * 50))
    return f"background-color: rgb({color},{color},255);"
def color_energy(val):
    color = int(220 - min(200, val / 4))
    return f"background-color: rgb(255,{color},150);"

for loc in locations.keys():
    styled = df_all[df_all["Location"] == loc][[
        "time",
        "Wind Speed (m/s)", "Wind Arrow", "Air Temp (°C)",
        "Wave Height (m)", "Wave Arrow",
        "Wave Period (s)", "Wave Power Index", "Wave Energy (kJ/m²)"
    ]].style.format({
        "Wind Speed (m/s)": "{:.1f}",
        "Air Temp (°C)": "{:.1f}",
        "Wave Height (m)": "{:.1f}",
        "Wave Period (s)": "{:.1f}",
        "Wave Energy (kJ/m²)": "{:.0f}"
    }).applymap(highlight_direction, subset=["Wind Arrow","Wave Arrow"]) \
     .applymap(color_wave, subset=["Wave Height (m)"]) \
     .applymap(color_energy, subset=["Wave Energy (kJ/m²)"])

    html_table = styled.to_html()

    with open(f"docs/{loc.lower().replace(' ', '_')}.html", "w", encoding="utf-8") as f:
        f.write(f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Surf Forecast {loc}</title>
<style>
body {{ font-family: Arial, sans-serif; background: #0b0c10; color: #c5c6c7; max-width: 1000px; margin: auto; padding: 20px; }}
h1 {{ color: #66fcf1; margin-top: 20px; }}
iframe {{ border: none; margin-bottom: 10px; width: 100%; max-width: 1024px; height: 576px; }}
.table-container {{ background: #1f2833; padding: 10px; border-radius: 8px; overflow-x: auto; margin-bottom: 40px; }}
table {{ width: 100%; border-collapse: collapse; color: #c5c6c7; }}
th, td {{ padding: 6px; text-align: center; }}
th {{ background: #45a29e; color: #0b0c10; }}
</style>
</head>
<body>
<h1>🌊 Surf Forecast & Webcam - {loc}</h1>
{webcams[loc]}
<div class="table-container">{html_table}</div>
</body></html>
""")
    print(f"✅ Created: docs/{loc.lower().replace(' ', '_')}.html")
