import requests
import pandas as pd
from datetime import datetime
import numpy as np
import os
import unicodedata

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

def slugify(name):
    # remove accents, lowercase, spaces → underscores
    nfkd = unicodedata.normalize("NFKD", name)
    only_ascii = "".join(c for c in nfkd if not unicodedata.combining(c))
    return only_ascii.lower().replace(" ", "_")

# ========== Locations & webcams ==========
locations = {
    "Las Palmas": (28.1272, -15.4314),
    "Telde": (27.9924, -15.4192),
    "Arguineguín": (27.7581, -15.6835)
}
webcams = {
    "Las Palmas": '<iframe src="https://in2thebeach.es/callbacks/camviewer_ext2.php?id=57" scrolling="no"></iframe>',
    "Telde":     '<iframe src="https://in2thebeach.es/callbacks/camviewer_ext2.php?id=43" scrolling="no"></iframe>',
    "Arguineguín":'<iframe src="https://in2thebeach.es/callbacks/camviewer_ext2.php?id=71" scrolling="no"></iframe>'
}

# ========== Prepare docs folder ==========
docs_dir = "docs"
os.makedirs(docs_dir, exist_ok=True)
print(">>> Writing files into:", os.path.abspath(docs_dir))

# ========== Fetch & process data ==========
dfs = []
for name, (lat, lon) in locations.items():
    # 1) Weather
    url_w = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        "&hourly=windspeed_10m,winddirection_10m,temperature_2m"
        "&timezone=auto"
    )
    df_w = pd.DataFrame(requests.get(url_w).json()["hourly"])
    df_w["time"] = pd.to_datetime(df_w["time"])

    # 2) Marine
    url_m = (
        f"https://marine-api.open-meteo.com/v1/marine?"
        f"latitude={lat}&longitude={lon}"
        "&hourly=wave_height,wave_direction,wave_period"
        "&timezone=auto"
    )
    df_m = pd.DataFrame(requests.get(url_m).json()["hourly"])
    df_m["time"] = pd.to_datetime(df_m["time"])

    # 3) Next 24h slice
    now = datetime.now()
    cutoff = now + pd.Timedelta(hours=24)
    df_w = df_w[(df_w["time"] >= now) & (df_w["time"] < cutoff)]
    df_m = df_m[(df_m["time"] >= now) & (df_m["time"] < cutoff)]

    # 4) Merge & rename
    df = pd.merge(df_w, df_m, on="time", how="outer") \
           .rename(columns={
               "windspeed_10m":"Wind Speed (m/s)",
               "winddirection_10m":"Wind Direction",
               "temperature_2m":"Air Temp (°C)",
               "wave_height":"Wave Height (m)",
               "wave_direction":"Wave Direction",
               "wave_period":"Wave Period (s)"
           }) \
           .sort_values("time") \
           .reset_index(drop=True)

    # 5) Compass & arrows
    df["Wind Dir Compass"] = df["Wind Direction"].apply(
        lambda x: degrees_to_compass(x) if pd.notnull(x) else ""
    )
    df["Wave Dir Compass"] = df["Wave Direction"].apply(
        lambda x: degrees_to_compass(x) if pd.notnull(x) else ""
    )
    df["Wind Arrow"] = df["Wind Dir Compass"].apply(compass_to_arrow)
    df["Wave Arrow"] = df["Wave Dir Compass"].apply(compass_to_arrow)

    # 6) Energy & power
    df["Wave Energy (kJ/m²)"] = (
        125 * (df["Wave Height (m)"]**2) * df["Wave Period (s)"]
    ).round(0)
    df["Wave Power Index"] = (
        df["Wave Height (m)"] * df["Wave Period (s)"]
    ).round(2)

    # 7) Round numeric
    for col in ["Wind Speed (m/s)", "Air Temp (°C)", "Wave Height (m)", "Wave Period (s)"]:
        df[col] = df[col].round(1)

    df["Location"] = name
    dfs.append(df)

df_all = pd.concat(dfs, ignore_index=True)

# ========== Styling helpers ==========
def highlight_direction(val):
    return "color: #33cccc; font-weight: bold" if isinstance(val, str) else ""
def color_wave(val):
    c = int(220 - min(200, val * 50))
    return f"background-color: rgb({c},{c},255);"
def color_energy(val):
    c = int(220 - min(200, val / 4))
    return f"background-color: rgb(255,{c},150);"

# ========== Write one page per location ==========
for name in locations:
    slug = slugify(name)
    page_file = f"{slug}.html"
    print("Generating:", page_file)

    styled = df_all[df_all["Location"] == name][[
        "time","Wind Speed (m/s)","Wind Arrow","Air Temp (°C)",
        "Wave Height (m)","Wave Arrow","Wave Period (s)",
        "Wave Power Index","Wave Energy (kJ/m²)"
    ]].style.format({
        "Wind Speed (m/s)":"{:.1f}",
        "Air Temp (°C)":"{:.1f}",
        "Wave Height (m)":"{:.1f}",
        "Wave Period (s)":"{:.1f}",
        "Wave Energy (kJ/m²)":"{:.0f}"
    }).applymap(highlight_direction, subset=["Wind Arrow","Wave Arrow"]) \
      .applymap(color_wave, subset=["Wave Height (m)"]) \
      .applymap(color_energy, subset=["Wave Energy (kJ/m²)"])

    html_table = styled.to_html()

    outpath = os.path.join(docs_dir, page_file)
    with open(outpath, "w", encoding="utf-8") as f:
        f.write(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Surf Forecast – {name}</title>
<style>
  body {{ font-family:Arial; background:#0b0c10; color:#c5c6c7; max-width:1000px; margin:auto; padding:20px }}
  h1 {{ color:#66fcf1; }}
  iframe {{ border:none; width:100%; max-width:1024px; height:576px; margin-bottom:10px }}
  .table-container {{ background:#1f2833; padding:10px; border-radius:8px; overflow-x:auto }}
  table {{ width:100%; border-collapse:collapse; color:#c5c6c7 }}
  th,td {{ padding:6px; text-align:center }}
  th {{ background:#45a29e; color:#0b0c10 }}
</style>
</head><body>
<h1>🌊 Surf Forecast & Webcam – {name}</h1>
{webcams[name]}
<div class="table-container">{html_table}</div>
</body></html>""")
    print(f"✅ Created docs/{page_file}")

print("All done.")
