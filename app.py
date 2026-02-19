# -*- coding: utf-8 -*-
"""
Aplikacja Logistyki Budowlanej — Optymalizacja Dojazdów Mechaników
==================================================================
Jednoplikowa aplikacja Streamlit do analizy kosztów i czasu dojazdu
mechaników na budowy. Gotowa do kompilacji: pyinstaller --onefile app.py

Uruchomienie:  streamlit run app.py

Struktura plików:
  MAPPA/
    app.py                           <- ta aplikacja
    requirements.txt
    MAPPA_Dane/
      Dane_MAPPA.xlsx                <- plik z danymi (MECHANICY, BUDOWY, WARSZTATY)
    cache_mechanicy.csv              <- auto-generowany cache geokodowania
"""

# ── Importy ──────────────────────────────────────────────────────────────────
import os
import io
import csv
import math
import time
import base64
import warnings

import pandas as pd
import requests
import streamlit as st
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import plotly.express as px

warnings.filterwarnings("ignore")

# ── Stałe ────────────────────────────────────────────────────────────────────
APP_TITLE = "MAPPA — Kalkulator dojazdów mechaników"
APP_ICON = "🏗️"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(BASE_DIR, "cache_mechanicy.csv")
OSRM_BASE = "http://router.project-osrm.org/route/v1/driving"
NOMINATIM_USER_AGENT = "logistyka_budowlana_app_v1"

# ── Google Sheets ─────────────────────────────────────────────────────────────
GSHEET_ID = "1yLzRB0v3Um6W4owIQt9-MfL320AxLVl7oY-lfPv7Kug"
APP_PASSWORD = "BE_13!WE"

def gsheet_csv_url(sheet_name: str) -> str:
    """URL do pobrania arkusza Google Sheets jako CSV."""
    return f"https://docs.google.com/spreadsheets/d/{GSHEET_ID}/gviz/tq?tqx=out:csv&sheet={sheet_name}"

# ── Konfiguracja strony ─────────────────────────────────────────────────────
st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": "MAPPA — Kalkulator dojazdów mechaników v3.1",
    },
)

# ── Styl CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* ── Reset & Layout ───────────────────────────────────────────── */
    .block-container { padding-top: 0.8rem; padding-bottom: 1rem; }

    /* Ukrycie Deploy + przezroczysty toolbar */
    .stDeployButton,
    [data-testid="stAppDeployButton"],
    header .stAppDeployButton { display: none !important; visibility: hidden !important; }
    header[data-testid="stHeader"] { background: transparent !important; }

    /* ── Sidebar ───────────────────────────────────────────────────── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
    }
    [data-testid="stSidebar"] .block-container { padding-top: 0.5rem; }
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] > div { margin-bottom: -0.2rem; }
    [data-testid="stSidebar"] hr { margin: 0.4rem 0; border-color: rgba(148,163,184,0.15); }
    [data-testid="stSidebar"] * { color: #e2e8f0 !important; }
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stSlider label,
    [data-testid="stSidebar"] .stNumberInput label,
    [data-testid="stSidebar"] .stMultiSelect label { color: #94a3b8 !important; }
    [data-testid="stSidebar"] .stMarkdown h2 { color: #f1f5f9 !important; }
    [data-testid="stSidebar"] .stMarkdown h3 { color: #cbd5e1 !important; }

    /* ── Header Banner ─────────────────────────────────────────────── */
    .main-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #1e293b 100%);
        padding: 2.5rem 2rem; border-radius: 16px; margin-bottom: 1.2rem;
        color: white; text-align: center; overflow: visible;
        min-height: 120px; position: relative;
        border: 1px solid rgba(148,163,184,0.12);
        box-shadow: 0 4px 24px rgba(0,0,0,0.25);
    }
    .main-header h1 {
        margin: 0; font-size: 2.6rem; font-weight: 800;
        letter-spacing: 3px; color: #f8fafc;
    }
    .main-header p {
        margin: 0.4rem 0 0 0; font-size: 1.1rem;
        color: #94a3b8; font-weight: 400;
    }

    /* ── Metric Cards ──────────────────────────────────────────────── */
    .metric-card {
        background: rgba(30, 41, 59, 0.6);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(148,163,184,0.12);
        border-radius: 12px;
        padding: 1rem 1.2rem; text-align: center;
        box-shadow: 0 2px 12px rgba(0,0,0,0.15);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 20px rgba(0,0,0,0.25);
    }
    .metric-card .value {
        font-size: 2.4rem; font-weight: 800; color: #60a5fa;
    }
    .metric-card .label {
        font-size: 0.88rem; color: #94a3b8; text-transform: uppercase;
        letter-spacing: 1px; margin-top: 0.2rem;
    }

    /* ── Best Result Card ──────────────────────────────────────────── */
    .best-result {
        background: rgba(16, 185, 129, 0.08);
        border-left: 4px solid #10b981;
        border-radius: 12px;
        padding: 1rem 1.4rem; margin-bottom: 1rem;
        border: 1px solid rgba(16, 185, 129, 0.2);
        border-left: 4px solid #10b981;
    }
    .best-result h4 { margin: 0 0 0.3rem 0; color: #34d399; font-weight: 700; }
    .best-result p  { margin: 0; color: #a7f3d0; font-size: 0.9rem; }

    /* ── DataFrame / Table ─────────────────────────────────────────── */
    .stDataFrame { border-radius: 12px; overflow: hidden; }

    /* ── Contrast fix for checkboxes, toggles, labels ──────────────── */
    .stCheckbox label span,
    .stToggle label span,
    .stRadio label span { color: inherit !important; }

    /* ── Info/Warning/Error boxes ──────────────────────────────────── */
    [data-testid="stAlert"] p { color: inherit !important; }

    /* ── Responsywność mobilna ─────────────────────────────────────── */
    @media (max-width: 768px) {
        .block-container { padding-left: 0.5rem; padding-right: 0.5rem; }
        .main-header h1 { font-size: 1.5rem; }
        .main-header p  { font-size: 0.85rem; }
        .metric-card .value { font-size: 1.3rem; }
        .metric-card .label { font-size: 0.7rem; }
        [data-testid="stHorizontalBlock"] {
            flex-direction: column !important;
        }
        [data-testid="stHorizontalBlock"] > [data-testid="stVerticalBlockBorderWrapper"] {
            width: 100% !important;
            flex: 1 1 100% !important;
        }
    }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  FUNKCJE POMOCNICZE
# ══════════════════════════════════════════════════════════════════════════════



# ── Cache geokodowania ───────────────────────────────────────────────────────
def load_geocode_cache() -> dict:
    """Wczytaj cache adresów → współrzędnych z CSV."""
    cache = {}
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cache[row["adres"]] = (float(row["lat"]), float(row["lon"]))
        except Exception:
            pass
    return cache


def save_geocode_cache(cache: dict) -> None:
    """Zapisz cache do CSV (nadpisz całość)."""
    try:
        with open(CACHE_PATH, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["adres", "lat", "lon"])
            writer.writeheader()
            for adres, (lat, lon) in cache.items():
                writer.writerow({"adres": adres, "lat": lat, "lon": lon})
    except Exception:
        pass


def geocode_address(address: str, geolocator, cache: dict) -> tuple:
    """Geokoduj adres; najpierw sprawdź cache."""
    if address in cache:
        return cache[address]
    try:
        time.sleep(1.1)  # Nominatim rate-limit: 1 req/s
        location = geolocator.geocode(address, timeout=10)
        if location:
            coords = (location.latitude, location.longitude)
            cache[address] = coords
            return coords
    except (GeocoderTimedOut, GeocoderServiceError):
        pass
    return (None, None)


# ── Ładowanie danych ─────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False, ttl=300)
def load_budowy() -> pd.DataFrame:
    """Wczytaj arkusz BUDOWY z Google Sheets — parsuj kolumnę WSPÓŁRZĘDNE."""
    try:
        url = gsheet_csv_url("BUDOWY")
        df = pd.read_csv(url)
    except Exception as e:
        st.error(f"❌ Nie można wczytać arkusza BUDOWY: {e}")
        return pd.DataFrame()

    # Szukaj kolumny współrzędnych (obsługa polskich znaków / wariantów)
    coord_col = None
    for c in df.columns:
        cu = str(c).upper().strip()
        if "WSPÓŁRZĘDNE" in cu or "WSPOLRZEDNE" in cu or "WSPOL" in cu or "COORD" in cu:
            coord_col = c
            break
    if coord_col is None:
        coord_col = df.columns[-1] if len(df.columns) >= 3 else None

    if coord_col is None:
        st.error("❌ Nie znaleziono kolumny ze współrzędnymi w arkuszu BUDOWY.")
        return pd.DataFrame()

    rows = []
    skipped = []
    for idx, (_, row) in enumerate(df.iterrows()):
        try:
            raw = str(row[coord_col]).strip()
            parts = raw.split(",")
            lat = float(parts[0].strip())
            lon = float(parts[1].strip())
            rows.append({
                "nazwa": str(row.get("NAZWA", "")).strip(),
                "kost": str(row.get("KOST", "")).strip(),
                "lat": lat,
                "lon": lon,
            })
        except Exception:
            name = str(row.get("NAZWA", f"wiersz {idx+1}")).strip()
            skipped.append(name)
            continue
    if skipped:
        st.warning(f"⚠️ Pominięto {len(skipped)} budów z błędnymi współrzędnymi: {', '.join(skipped)}")
    return pd.DataFrame(rows)


@st.cache_data(show_spinner=False, ttl=300)
def load_warsztaty() -> pd.DataFrame:
    """Wczytaj arkusz WARSZTATY z Google Sheets."""
    try:
        url = gsheet_csv_url("WARSZTATY")
        df = pd.read_csv(url)
    except Exception:
        return pd.DataFrame()

    coord_col = None
    name_col = None
    for c in df.columns:
        cu = str(c).upper().strip()
        if "WSPÓŁRZĘDNE" in cu or "WSPOLRZEDNE" in cu or "WSPOL" in cu or "COORD" in cu:
            coord_col = c
        if "NAZWA" in cu or "NAME" in cu:
            name_col = c

    if coord_col is None or name_col is None:
        cols = list(df.columns)
        if len(cols) >= 2:
            if name_col is None:
                name_col = cols[0]
            if coord_col is None:
                coord_col = cols[-1]
        else:
            return pd.DataFrame()

    rows = []
    skipped = []
    for idx, (_, row) in enumerate(df.iterrows()):
        try:
            raw = str(row[coord_col]).strip()
            parts = raw.split(",")
            lat = float(parts[0].strip())
            lon = float(parts[1].strip())
            rows.append({
                "nazwa": str(row[name_col]).strip(),
                "lat": lat,
                "lon": lon,
            })
        except Exception:
            name = str(row.get(name_col, f"wiersz {idx+1}")).strip()
            skipped.append(name)
            continue
    if skipped:
        st.warning(f"⚠️ Pominięto {len(skipped)} warsztatów z błędnymi współrzędnymi: {', '.join(skipped)}")
    return pd.DataFrame(rows)


def load_mechanicy() -> pd.DataFrame:
    """Wczytaj arkusz MECHANICY z Google Sheets — geokoduj z cache."""
    try:
        url = gsheet_csv_url("MECHANICY")
        df = pd.read_csv(url)
    except Exception as e:
        st.error(f"❌ Nie można wczytać arkusza MECHANICY: {e}")
        return pd.DataFrame()

    cache = load_geocode_cache()
    geolocator = Nominatim(user_agent=NOMINATIM_USER_AGENT)
    new_geocoded = 0
    skipped_list = []  # A3: śledzenie pominiętych

    rows = []
    progress = st.progress(0, text="🔄 Geokodowanie mechaników…")
    total = len(df)

    for idx, (_, row) in enumerate(df.iterrows()):
        try:
            imie = str(row.get("Imię", "")).strip()
            nazwisko = str(row.get("Nazwisko", "")).strip()
            kod = str(row.get("Kod pocztowy", "")).strip()
            miasto = str(row.get("Miasto", "")).strip()
            warsztat = str(row.get("Warsztat", "")).strip()

            # A5: Ulica — użyj pd.notna() zamiast porównania z "nan"
            ulica_raw = row.get("Ulica", "")
            ulica = str(ulica_raw).strip() if pd.notna(ulica_raw) else ""

            # A5: Budowanie adresu — z pd.notna() zamiast string check
            addr_parts = []
            for p in [ulica, kod, miasto]:
                if pd.notna(p) and str(p).strip() and str(p).strip().lower() != "nan":
                    addr_parts.append(str(p).strip())
            adres = " ".join(addr_parts)

            if not adres:
                skipped_list.append(f"{imie} {nazwisko} (brak adresu)")
                continue

            was_cached = adres in cache
            lat, lon = geocode_address(adres, geolocator, cache)

            if not was_cached and lat is not None:
                new_geocoded += 1

            if lat is not None and lon is not None:
                rows.append({
                    "imie": imie,
                    "nazwisko": nazwisko,
                    "mechanik": f"{imie} {nazwisko}",
                    "adres": adres,
                    "warsztat": warsztat,
                    "lat": lat,
                    "lon": lon,
                })
            else:
                skipped_list.append(f"{imie} {nazwisko} (geokodowanie nieudane)")
        except Exception as e:
            skipped_list.append(f"wiersz {idx+1} ({e})")
            continue

        progress.progress((idx + 1) / total if total > 0 else 1.0,
                          text=f"🔄 Geokodowanie: {idx+1}/{total}")

    progress.empty()

    # A3: Pokaż ostrzeżenie o pominiętych mechanikach
    if skipped_list:
        st.warning(f"⚠️ Pominięto {len(skipped_list)} mechaników: {', '.join(skipped_list[:5])}"
                   + (f" i {len(skipped_list)-5} więcej…" if len(skipped_list) > 5 else ""))

    if new_geocoded > 0:
        save_geocode_cache(cache)

    return pd.DataFrame(rows)


# ── Haversine ────────────────────────────────────────────────────────────────
def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Odległość w linii prostej (km) — wzór Haversine."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── C7: Sprawdzenie dostępności OSRM ─────────────────────────────────────────
def check_osrm_available() -> bool:
    """Testowe zapytanie do OSRM — sprawdza czy serwer odpowiada."""
    try:
        url = f"{OSRM_BASE}/19.945,50.065;20.0,50.0?overview=false"
        resp = requests.get(url, timeout=5)
        return resp.status_code == 200 and resp.json().get("code") == "Ok"
    except Exception:
        return False


# ── OSRM Routing (z geometrią trasy) ────────────────────────────────────────
def get_osrm_route(lat1: float, lon1: float, lat2: float, lon2: float,
                   use_fallback: bool = False):
    """Pobierz dystans (km), czas (min) i geometrię trasy z OSRM.
    A4: Retry 1× przy timeout. Jeśli use_fallback=True, użyj Haversine.
    Zwraca: (distance_km, duration_min, list_of_[lat,lon])"""
    if not use_fallback:
        max_retries = 2  # A4: 1 próba dodatkowa
        for attempt in range(max_retries):
            try:
                url = (f"{OSRM_BASE}/{lon1},{lat1};{lon2},{lat2}"
                       f"?overview=full&geometries=geojson")
                resp = requests.get(url, timeout=10)
                data = resp.json()
                if data.get("code") == "Ok" and data.get("routes"):
                    route = data["routes"][0]
                    distance_km = round(route["distance"] / 1000, 1)
                    duration_min = round(route["duration"] / 60, 1)
                    coords = route["geometry"]["coordinates"]
                    polyline = [[c[1], c[0]] for c in coords]
                    return distance_km, duration_min, polyline
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    time.sleep(0.5)  # krótka pauza przed retry
                    continue
            except Exception:
                break  # inne błędy — nie retry'uj
    # Fallback: Haversine (linia prosta × 1.3 jako przybliżenie drogowe)
    dist = round(haversine_km(lat1, lon1, lat2, lon2) * 1.3, 1)
    dur = round(dist, 1)  # minuty ≈ km przy ~60 km/h (dist_km / 60 * 60 = dist_km)
    polyline = [[lat1, lon1], [lat2, lon2]]
    return dist, dur, polyline





# ── Kolory tras ──────────────────────────────────────────────────────────────
ROUTE_COLORS = [
    "#2ecc71", "#3498db", "#e74c3c", "#9b59b6", "#f39c12",
    "#1abc9c", "#e67e22", "#2980b9", "#c0392b", "#8e44ad",
    "#27ae60", "#d35400", "#16a085", "#f1c40f", "#7f8c8d",
]


def get_route_color(index: int) -> str:
    return ROUTE_COLORS[index % len(ROUTE_COLORS)]


# ── Dostawcy kafelków mapy ──────────────────────────────────────────────────
TILE_PROVIDERS = {
    "🌍 OpenStreetMap": {
        "tiles": "OpenStreetMap",
        "attr": None,
    },
    "🏙️ Esri StreetMap": {
        "tiles": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
        "attr": "Esri, HERE, Garmin, USGS",
    },
    "⛰️ Esri TopoMap": {
        "tiles": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
        "attr": "Esri, HERE, Garmin, USGS",
    },
    "🛰️ Esri Satelita": {
        "tiles": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "attr": "Esri, Maxar, Earthstar",
    },
    "🧪CartoDB Voyager": {
        "tiles": "CartoDB Voyager",
        "attr": None,
    },
    "⚪ CartoDB Positron": {
        "tiles": "CartoDB positron",
        "attr": None,
    },
    "🌙 CartoDB Ciemna": {
        "tiles": "CartoDB dark_matter",
        "attr": None,
    },
}


# ── Mapa Folium ──────────────────────────────────────────────────────────────
def build_map(mechanicy_df, budowy_df, warsztaty_df,
              selected_budowa=None, routes=None,
              tile_key="🌍 OpenStreetMap", use_clusters=True,
              show_budowy=True, show_warsztaty=True,
              show_mechanicy=True, show_trasy=True):
    """Zbuduj mapę Folium z warstwami i opcjonalnymi trasami."""
    all_lats, all_lons = [], []
    for df in [mechanicy_df, budowy_df, warsztaty_df]:
        if df is not None and not df.empty:
            all_lats.extend(df["lat"].tolist())
            all_lons.extend(df["lon"].tolist())

    if all_lats:
        center = [sum(all_lats) / len(all_lats), sum(all_lons) / len(all_lons)]
    else:
        center = [51.1, 17.0]

    # Pobierz kafelki z słownika
    provider = TILE_PROVIDERS.get(tile_key, TILE_PROVIDERS["🌍 OpenStreetMap"])
    tile_url = provider["tiles"]
    tile_attr = provider["attr"]

    if tile_attr:
        m = folium.Map(location=center, zoom_start=8,
                       tiles=tile_url, attr=tile_attr)
    else:
        m = folium.Map(location=center, zoom_start=8, tiles=tile_url)

    # ── Warstwa: Budowy (czerwone) ───────────────────────────────────────
    fg_budowy = folium.FeatureGroup(name="🏢 Budowy", show=show_budowy)
    if budowy_df is not None and not budowy_df.empty:
        for _, row in budowy_df.iterrows():
            popup_html = (
                f"<div style='min-width:180px'>"
                f"<b style='color:#c0392b; font-size:1.05em'>🏢 {row['nazwa']}</b><br>"
                f"<span style='color:#555'>KOST: <b>{row['kost']}</b></span>"
                f"</div>"
            )
            icon_color = "darkred" if (selected_budowa and row["nazwa"] == selected_budowa) else "red"
            folium.Marker(
                location=[row["lat"], row["lon"]],
                popup=folium.Popup(popup_html, max_width=280),
                tooltip=row["nazwa"],
                icon=folium.Icon(color=icon_color, icon="industry", prefix="fa"),
            ).add_to(fg_budowy)
    fg_budowy.add_to(m)

    # ── Warstwa: Warsztaty (niebieskie) ──────────────────────────────────
    fg_warsztaty = folium.FeatureGroup(name="🔧 Warsztaty", show=show_warsztaty)
    if warsztaty_df is not None and not warsztaty_df.empty:
        for _, row in warsztaty_df.iterrows():
            popup_html = (
                f"<div style='min-width:160px'>"
                f"<b style='color:#2980b9; font-size:1.05em'>🔧 {row['nazwa']}</b><br>"
                f"<span style='color:#777; font-size:0.85em'>Warsztat stały</span>"
                f"</div>"
            )
            folium.Marker(
                location=[row["lat"], row["lon"]],
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=row["nazwa"],
                icon=folium.Icon(color="blue", icon="wrench", prefix="fa"),
            ).add_to(fg_warsztaty)
    fg_warsztaty.add_to(m)

    # ── Warstwa: Mechanicy (zielone) — C3: z klastrowaniem ────────────────
    fg_mechanicy = folium.FeatureGroup(name="👷 Mechanicy", show=show_mechanicy)
    if mechanicy_df is not None and not mechanicy_df.empty:
        # C3: Użyj MarkerCluster jeśli włączone
        marker_target = MarkerCluster().add_to(fg_mechanicy) if use_clusters else fg_mechanicy
        for _, row in mechanicy_df.iterrows():
            popup_html = (
                f"<div style='min-width:180px'>"
                f"<b style='color:#27ae60; font-size:1.05em'>👷 {row['mechanik']}</b><br>"
                f"<span style='color:#555'>Warsztat: <b>{row['warsztat']}</b></span><br>"
                f"<span style='color:#777; font-size:0.85em'>{row['adres']}</span>"
                f"</div>"
            )
            folium.Marker(
                location=[row["lat"], row["lon"]],
                popup=folium.Popup(popup_html, max_width=280),
                tooltip=f"{row['mechanik']} ({row['warsztat']})",
                icon=folium.Icon(color="green", icon="user", prefix="fa"),
            ).add_to(marker_target)
    fg_mechanicy.add_to(m)

    # ── Warstwa: Trasy (kolorowe polilinie) ──────────────────────────────
    if routes:
        fg_trasy = folium.FeatureGroup(name="🛣️ Trasy dojazdowe", show=show_trasy)
        for i, route_info in enumerate(routes):
            polyline = route_info.get("polyline")
            label = route_info.get("label", "")
            dist = route_info.get("dist", "")
            dur = route_info.get("dur", "")
            color = get_route_color(i)
            is_best = route_info.get("is_best", False)
            rank = f"#{i+1}"
            best_star = " ⭐" if is_best else ""

            weight = 7 if is_best else 4
            opacity = 0.9 if is_best else 0.75

            if polyline and len(polyline) > 1:
                folium.PolyLine(
                    locations=polyline,
                    color=color,
                    weight=weight,
                    opacity=opacity,
                    tooltip=f"{rank} {label} — {dist} km, {dur} min{best_star}",
                ).add_to(fg_trasy)

                # Kolorowy CircleMarker na początku trasy (skaluje się z zoomem)
                folium.CircleMarker(
                    location=polyline[0],
                    radius=7,
                    color="#333",
                    weight=1,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.9,
                    tooltip=f"{rank} {label} — {dist} km, {dur} min{best_star}",
                ).add_to(fg_trasy)
        fg_trasy.add_to(m)

    return m


# ══════════════════════════════════════════════════════════════════════════════
#  APLIKACJA GŁÓWNA
# ══════════════════════════════════════════════════════════════════════════════
def main():
    # ── Bramka hasła ──────────────────────────────────────────────────────
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if not st.session_state["authenticated"]:
        st.markdown("## 🔐 MAPPA — Logowanie")
        pwd = st.text_input("Hasło:", type="password", key="login_pwd")
        if st.button("Zaloguj"):
            if pwd == APP_PASSWORD:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("❌ Nieprawidłowe hasło.")
        st.stop()

    # ── Nagłówek ─────────────────────────────────────────────────────────
    # Ładowanie obrazów jako base64
    _assets = os.path.join(os.path.dirname(__file__), "assets")
    def _img_b64(fname):
        path = os.path.join(_assets, fname)
        if os.path.exists(path):
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode()
        return ""
    _kask_b64 = _img_b64("kask.png")
    _pojazd_b64 = _img_b64("pojazd.png")

    st.markdown(
        '<div class="main-header" style="position:relative;">'
        '<h1>🌍 MAPPA 🚚</h1>'
        '<p>Kalkulator dojazdów mechaników</p>'
        f'<img src="data:image/png;base64,{_kask_b64}" '
        'style="position:absolute; right:20px; top:50%; transform:translateY(-50%); '
        'height:150px; object-fit:contain;" />'
        '</div>',
        unsafe_allow_html=True,
    )

    # 🌙 Tryb ciemny/jasny
    _theme = st.radio("Motyw:", ["🌙 Ciemny", "☀️ Jasny"], horizontal=True, key="dark_mode_radio", label_visibility="collapsed")
    dark_mode = (_theme == "🌙 Ciemny")
    if dark_mode:
        st.markdown("""
        <style>
            /* ── Dark Mode ────────────────────────────────────────── */
            .stApp { background-color: #0f172a; color: #e2e8f0; }

            /* Metric cards */
            .metric-card { background: rgba(30,41,59,0.7); border-color: rgba(148,163,184,0.12); }
            .metric-card .value { color: #60a5fa; }
            .metric-card .label { color: #94a3b8; }

            /* Best result */
            .best-result { background: rgba(16,185,129,0.08); border-color: rgba(16,185,129,0.2); }
            .best-result h4 { color: #34d399; }
            .best-result p  { color: #a7f3d0; }

            /* Checkboxes, toggles, labels — biały tekst */
            .stCheckbox label, .stCheckbox label span,
            .stToggle label, .stToggle label span,
            .stRadio label, .stRadio label span { color: #e2e8f0 !important; }

            /* Info / warning / success / error boxes */
            [data-testid="stAlert"] { background: rgba(30,41,59,0.6) !important; border-color: rgba(148,163,184,0.15) !important; }
            [data-testid="stAlert"] p, [data-testid="stAlert"] span { color: #e2e8f0 !important; }

            /* Section headers */
            .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 { color: #f1f5f9 !important; }

            /* Selectbox, number input text */
            .stSelectbox [data-baseweb="select"] span,
            .stNumberInput input { color: #e2e8f0 !important; }

        </style>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <style>
            /* ── Light Mode ───────────────────────────────────────── */
            .stApp {
                background-color: #f8fafc !important;
                color: #1e293b !important;
            }

            /* Force text dark everywhere */
            .stApp p, .stApp span, .stApp label,
            .stApp li, .stApp summary,
            .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5 {
                color: #1e293b !important;
            }

            /* Sidebar — soft pastel blue-gray */
            [data-testid="stSidebar"],
            [data-testid="stSidebar"] > div:first-child {
                background: linear-gradient(180deg, #e2e8f0 0%, #cbd5e1 40%, #bfcad8 100%) !important;
            }
            [data-testid="stSidebar"] p, [data-testid="stSidebar"] span,
            [data-testid="stSidebar"] label, [data-testid="stSidebar"] h2,
            [data-testid="stSidebar"] h3, [data-testid="stSidebar"] h4 {
                color: #0f172a !important;
            }
            [data-testid="stSidebar"] hr { border-color: rgba(0,0,0,0.08) !important; }

            /* Sidebar inputs — white fields */
            [data-testid="stSidebar"] [data-baseweb="select"],
            [data-testid="stSidebar"] [data-baseweb="select"] > div,
            [data-testid="stSidebar"] [data-baseweb="input"],
            [data-testid="stSidebar"] input {
                background-color: #ffffff !important;
                color: #1e293b !important;
            }
            [data-testid="stSidebar"] [data-baseweb="select"] span,
            [data-testid="stSidebar"] [data-baseweb="select"] div,
            [data-testid="stSidebar"] [data-baseweb="select"] svg {
                color: #1e293b !important;
                fill: #1e293b !important;
            }

            /* Main-area selectbox (tile picker etc) — also white */
            .stSelectbox [data-baseweb="select"],
            .stSelectbox [data-baseweb="select"] > div {
                background-color: #ffffff !important;
                color: #1e293b !important;
            }
            .stSelectbox [data-baseweb="select"] span,
            .stSelectbox [data-baseweb="select"] svg {
                color: #1e293b !important;
                fill: #1e293b !important;
            }

            /* Sidebar "Panel Sterowania" title — force black */
            [data-testid="stSidebar"] [data-testid="stMarkdown"] h2,
            [data-testid="stSidebar"] .stMarkdown h2 {
                color: #0f172a !important;
            }

            /* Sidebar "Odśwież dane" button — salmon */
            [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"],
            [data-testid="stSidebar"] .stButton > button:not([kind="primary"]) {
                background-color: #fa8072 !important;
                color: #ffffff !important;
                border-color: #e76f61 !important;
            }
            [data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:hover,
            [data-testid="stSidebar"] .stButton > button:not([kind="primary"]):hover {
                background-color: #e76f61 !important;
            }

            /* Number input +/- steppers */
            [data-testid="stSidebar"] .stNumberInput button,
            .stNumberInput [data-testid="stNumberInputStepUp"],
            .stNumberInput [data-testid="stNumberInputStepDown"] {
                background-color: #cbd5e1 !important;
                color: #1e293b !important;
                border-color: rgba(0,0,0,0.1) !important;
            }

            /* Header banner — soft pastel */
            .main-header {
                background: linear-gradient(135deg, #cbd5e1 0%, #94a3b8 50%, #b0becf 100%) !important;
                border-color: rgba(0,0,0,0.06) !important;
                box-shadow: 0 2px 12px rgba(0,0,0,0.08) !important;
            }

            /* Metric cards */
            .metric-card {
                background: rgba(255,255,255,0.9) !important;
                border-color: rgba(0,0,0,0.06) !important;
                box-shadow: 0 2px 8px rgba(0,0,0,0.06) !important;
            }
            .metric-card .value { color: #1e3a5f !important; }
            .metric-card .label { color: #64748b !important; }

            /* Best result */
            .best-result {
                background: rgba(16,185,129,0.08) !important;
                border-color: rgba(16,185,129,0.18) !important;
            }
            .best-result h4 { color: #047857 !important; }
            .best-result p  { color: #065f46 !important; }

            /* Expanders */
            [data-testid="stExpander"] {
                background: #f1f5f9 !important;
                border-color: rgba(0,0,0,0.08) !important;
                border-radius: 12px !important;
            }
            [data-testid="stExpander"] details {
                background: #f1f5f9 !important;
            }

            /* Download button */
            [data-testid="stDownloadButton"] > button {
                background-color: #cbd5e1 !important;
                color: #1e293b !important;
                border-color: rgba(0,0,0,0.08) !important;
            }

            /* Alerts — including bold/strong text */
            [data-testid="stAlert"] {
                background: #f1f5f9 !important;
                border-color: rgba(0,0,0,0.08) !important;
            }
            [data-testid="stAlert"] p,
            [data-testid="stAlert"] span,
            [data-testid="stAlert"] strong,
            [data-testid="stAlert"] b,
            [data-testid="stAlert"] code {
                color: #1e293b !important;
            }

            /* Selectbox dropdown popover — light bg */
            [data-baseweb="popover"],
            [data-baseweb="popover"] > div,
            [data-baseweb="menu"],
            [data-baseweb="menu"] ul,
            [role="listbox"],
            [role="listbox"] li,
            [role="option"] {
                background-color: #ffffff !important;
                color: #1e293b !important;
            }
            [role="option"]:hover,
            [data-baseweb="menu"] li:hover {
                background-color: #e2e8f0 !important;
            }
            [role="option"][aria-selected="true"] {
                background-color: #dbeafe !important;
            }

            /* Plotly */
            .stPlotlyChart { background: transparent !important; }

            /* Checkboxes / toggles / radio */
            .stCheckbox label span, .stToggle label span,
            .stRadio label span { color: #1e293b !important; }

        </style>
        """, unsafe_allow_html=True)

    # ── Helper: renderuj DataFrame jako tabelę HTML ─────────────────
    def _render_table(df, highlight_row=None):
        """Pełna kontrola kolorów — st.dataframe używa canvas i CSS go nie obejmie."""
        dk = dark_mode
        bg     = "#1e293b" if dk else "#ffffff"
        txt    = "#e2e8f0" if dk else "#1e293b"
        hd_bg  = "#0f172a" if dk else "#e2e8f0"
        brd    = "rgba(148,163,184,0.15)" if dk else "rgba(0,0,0,0.08)"
        alt_bg = "rgba(255,255,255,0.03)" if dk else "rgba(0,0,0,0.02)"
        html = (f'<div style="overflow-x:auto;border-radius:12px;'
                f'border:1px solid {brd};margin:0.5rem 0">'
                f'<table style="width:100%;border-collapse:collapse;'
                f'background:{bg};color:{txt};font-size:0.85rem">')
        html += '<thead><tr>'
        for col in df.columns:
            html += (f'<th style="padding:8px 12px;background:{hd_bg};'
                     f'border-bottom:2px solid {brd};text-align:left;'
                     f'font-weight:600;white-space:nowrap">{col}</th>')
        html += '</tr></thead><tbody>'
        for i, (_, row) in enumerate(df.iterrows()):
            if highlight_row is not None and i == highlight_row:
                rbg, rtxt, fw = "#1565c0", "#ffffff", "bold"
            elif i % 2 == 1:
                rbg, rtxt, fw = alt_bg, txt, "normal"
            else:
                rbg, rtxt, fw = bg, txt, "normal"
            html += f'<tr style="background:{rbg};color:{rtxt};font-weight:{fw}">'
            for val in row:
                html += (f'<td style="padding:6px 12px;'
                         f'border-bottom:1px solid {brd};'
                         f'white-space:nowrap">{val}</td>')
            html += '</tr>'
        html += '</tbody></table></div>'
        return html

    # ── Ładowanie danych z Google Sheets ────────────────────────────────
    with st.spinner("📂 Wczytywanie budów…"):
        budowy_df = load_budowy()

    with st.spinner("📂 Wczytywanie warsztatów…"):
        warsztaty_df = load_warsztaty()

    if "mechanicy_df" not in st.session_state:
        with st.spinner("📂 Wczytywanie i geokodowanie mechaników…"):
            st.session_state["mechanicy_df"] = load_mechanicy()

    mechanicy_df = st.session_state["mechanicy_df"]

    if mechanicy_df.empty and budowy_df.empty:
        st.warning("⚠️ Brak danych do wyświetlenia. Sprawdź arkusz Google Sheets.")
        st.stop()

    # ── Sidebar ──────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("## ⚙️ Panel Sterowania")
        st.markdown("---")

        # 📍 Miejsce docelowe (na górze)
        dest_options = []
        if not budowy_df.empty:
            dest_options += ["🏢 " + n for n in budowy_df["nazwa"].tolist()]
        if warsztaty_df is not None and not warsztaty_df.empty:
            dest_options += ["🔧 " + n for n in warsztaty_df["nazwa"].tolist()]

        if dest_options:
            selected_dest = st.selectbox(
                "📍 Miejsce docelowe",
                options=dest_options,
                index=0,
                help="Wybierz budowę lub warsztat jako cel dojazdu.",
            )
        else:
            selected_dest = None
            st.warning("Brak miejsc docelowych w danych.")

        # Parsowanie wybranego celu
        selected_budowa = None
        dest_name = None
        dest_lat = None
        dest_lon = None
        if selected_dest:
            if selected_dest.startswith("🏢 "):
                dest_name = selected_dest.split(" ", 1)[1].strip()
                selected_budowa = dest_name
                match = budowy_df[budowy_df["nazwa"] == dest_name]
                if not match.empty:
                    dest_lat, dest_lon = match.iloc[0]["lat"], match.iloc[0]["lon"]
            elif selected_dest.startswith("🔧 "):
                dest_name = selected_dest.split(" ", 1)[1].strip()
                if warsztaty_df is not None:
                    match = warsztaty_df[warsztaty_df["nazwa"] == dest_name]
                    if not match.empty:
                        dest_lat, dest_lon = match.iloc[0]["lat"], match.iloc[0]["lon"]

        st.markdown("---")

        # 🔧 Filtruj wg warsztatu — checkboxy w expanderze
        if not mechanicy_df.empty:
            all_warsztaty = sorted(mechanicy_df["warsztat"].unique().tolist())

            if "_ws_open" not in st.session_state:
                st.session_state["_ws_open"] = False
            def _keep_ws_open():
                st.session_state["_ws_open"] = True

            _ws_count = sum(1 for ws in all_warsztaty if st.session_state.get(f"ws_cb_{ws}", True))
            with st.expander(f"🔧 Warsztaty (wybrano {_ws_count})", expanded=st.session_state["_ws_open"]):
                ws_all = st.checkbox("Zaznacz wszystkie", value=True, key="ws_toggle_all",
                                     on_change=_keep_ws_open)
                selected_warsztaty = []
                for ws in all_warsztaty:
                    checked = st.checkbox(ws, value=ws_all, key=f"ws_cb_{ws}",
                                          on_change=_keep_ws_open)
                    if checked:
                        selected_warsztaty.append(ws)
        else:
            selected_warsztaty = []

        # 👷 Wybór mechaników — checkboxy w expanderze
        if not mechanicy_df.empty:
            if selected_warsztaty:
                available_mechanicy = sorted(
                    mechanicy_df[mechanicy_df["warsztat"].isin(selected_warsztaty)]["mechanik"].tolist()
                )
            else:
                available_mechanicy = sorted(mechanicy_df["mechanik"].tolist())

            if "_mc_open" not in st.session_state:
                st.session_state["_mc_open"] = False
            def _keep_mc_open():
                st.session_state["_mc_open"] = True

            _mc_count = sum(1 for m in available_mechanicy if st.session_state.get(f"mc_cb_{m}", True))
            with st.expander(f"👷 Mechanicy (wybrano {_mc_count})", expanded=st.session_state["_mc_open"]):
                mc_all = st.checkbox("Zaznacz wszystkich", value=True, key="mc_toggle_all",
                                     on_change=_keep_mc_open)
                selected_mechanicy = []
                for mech in available_mechanicy:
                    checked = st.checkbox(mech, value=mc_all, key=f"mc_cb_{mech}",
                                          on_change=_keep_mc_open)
                    if checked:
                        selected_mechanicy.append(mech)
        else:
            selected_mechanicy = []

        st.markdown("---")

        # 💰 Kalkulator kosztów
        st.markdown("### 💰 Kalkulator kosztów")
        cena_paliwa = st.number_input(
            "⛽ Cena paliwa (PLN/litr)",
            min_value=0.0, max_value=20.0,
            value=6.50, step=0.10, format="%.2f",
        )
        spalanie = st.number_input(
            "🚗 Spalanie (l/100 km)",
            min_value=0.0, max_value=50.0,
            value=10.0, step=0.5, format="%.1f",
        )
        koszt_za_km = round((cena_paliwa * spalanie) / 100, 4) if spalanie > 0 else 0
        st.info(f"📊 Koszt dojazdu: **{koszt_za_km:.2f} PLN/km**")

        st.markdown("---")

        # 🔍 Analizuj dojazdy
        analyze_clicked = st.button(
            "🔍 Analizuj dojazdy",
            type="primary",
            use_container_width=True,
            help="Oblicz trasy dojazdu dla wybranych parametrów.",
        )

        # 🔄 Odśwież dane (na dole)
        if st.button("🔄 Odśwież dane", use_container_width=True,
                     help="Wyczyść cache i wczytaj dane ponownie z Excela."):
            st.cache_data.clear()
            for key in list(st.session_state.keys()):
                if key.startswith(("mechanicy_df", "osrm_available", "saved_", "analysis_")):
                    del st.session_state[key]
            st.rerun()

        st.markdown("---")

        # Pojazd na samym dole sidebaru (przyklejony)
        if _pojazd_b64:
            st.markdown(
                f'<div style="position:fixed; bottom:10px; left:0; '
                f'width:var(--sidebar-width, 21rem); text-align:center; '
                f'pointer-events:none; z-index:1;">'
                f'<img src="data:image/png;base64,{_pojazd_b64}" '
                f'style="max-width:100%; height:auto; opacity:0.85;" />'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ── Filtrowanie mechaników wg warsztatu + wg selekcji ────────────────
    if selected_warsztaty and not mechanicy_df.empty:
        filtered_mechanicy = mechanicy_df[
            mechanicy_df["warsztat"].isin(selected_warsztaty)
        ].copy()
    else:
        filtered_mechanicy = mechanicy_df.copy()

    # Filtrowanie wg wybranych mechaników (żeby mapa też pokazywała tylko wybranych)
    if selected_mechanicy and not filtered_mechanicy.empty:
        filtered_mechanicy = filtered_mechanicy[
            filtered_mechanicy["mechanik"].isin(selected_mechanicy)
        ].copy()

    # Dodatkowy filtr wg wybranych mechaników (multiselect)
    if selected_mechanicy and not filtered_mechanicy.empty:
        analysis_mechanicy = filtered_mechanicy[
            filtered_mechanicy["mechanik"].isin(selected_mechanicy)
        ].copy()
    else:
        analysis_mechanicy = filtered_mechanicy.copy()

    # ── Metryki proaktywne ───────────────────────────────────────────────

    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="value">{len(mechanicy_df)}</div>'
            f'<div class="label">Mechanicy ogółem</div></div>',
            unsafe_allow_html=True,
        )
    with col_m2:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="value">{len(budowy_df)}</div>'
            f'<div class="label">Budowy</div></div>',
            unsafe_allow_html=True,
        )
    with col_m3:
        w_count = len(warsztaty_df) if warsztaty_df is not None and not warsztaty_df.empty else 0
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="value">{w_count}</div>'
            f'<div class="label">Warsztaty</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("")

    # ── C7: Sprawdź dostępność OSRM ──────────────────────────────────────
    if "osrm_available" not in st.session_state:
        st.session_state["osrm_available"] = check_osrm_available()
    osrm_down = not st.session_state["osrm_available"]
    if osrm_down:
        st.warning(
            "⚠️ Serwer OSRM niedostępny — trasy obliczane w linii prostej "
            "(Haversine × 1.3). Wyniki mogą być niedokładne."
        )

    # ── Routing OSRM — TYLKO po kliknięciu Analizuj ──────────────────────
    # ℹ️ Czas trasy pochodzi z OSRM (OpenStreetMap) — nie uwzględnia korków.
    # Dane drogowe aktualizowane co kilka tygodni. Dokładność ±5-15% vs Google Maps.
    if analyze_clicked and dest_name and dest_lat is not None and not analysis_mechanicy.empty:
        results = []

        progress_bar = st.progress(0, text="🛣️ Obliczanie tras OSRM…")
        total = len(analysis_mechanicy)

        for i, (_, mech) in enumerate(analysis_mechanicy.iterrows()):
            origin_lat, origin_lon = mech["lat"], mech["lon"]

            dist_km, dur_min, polyline = get_osrm_route(
                origin_lat, origin_lon, dest_lat, dest_lon,
                use_fallback=osrm_down,
            )
            if dist_km is not None:
                koszt = round(dist_km * koszt_za_km, 2)
                results.append({
                    "Mechanik": mech["mechanik"],
                    "Warsztat": mech["warsztat"],
                    "Dystans (km)": dist_km,
                    "Czas (min)": dur_min,
                    "Koszt paliwa (PLN)": koszt,
                    "_polyline": polyline,
                })
            progress_bar.progress((i + 1) / total, text=f"🛣️ Trasa {i+1}/{total}")

        progress_bar.empty()

        if results:
            result_df = pd.DataFrame(results).sort_values(
                "Dystans (km)"
            ).reset_index(drop=True)

            routes_for_map = []
            for i, (_, row) in enumerate(result_df.iterrows()):
                if row["_polyline"]:
                    routes_for_map.append({
                        "polyline": row["_polyline"],
                        "label": row["Mechanik"],
                        "dist": row["Dystans (km)"],
                        "dur": row["Czas (min)"],
                        "is_best": i == 0,
                    })

            # Zapisz wyniki do session_state
            st.session_state["analysis_results"] = result_df
            st.session_state["analysis_routes"] = routes_for_map
            st.session_state["analysis_target"] = dest_name
            st.session_state["analysis_koszt_za_km"] = koszt_za_km
        else:
            # Brak wyników — wyczyść
            st.session_state.pop("analysis_results", None)
            st.session_state.pop("analysis_routes", None)

    # ── Odczytaj wyniki z session_state ───────────────────────────────────
    result_df = st.session_state.get("analysis_results", None)
    routes_for_map = st.session_state.get("analysis_routes", [])
    analysis_target = st.session_state.get("analysis_target", None)

    # ── Layout: Mapa + Tabela ────────────────────────────────────────────
    col_map, col_table = st.columns([3, 2])

    with col_map:
        # Nagłówek mapy + wybór stylu + filtry warstw
        map_hdr_col, map_tile_col = st.columns([1, 2])
        with map_hdr_col:
            st.markdown("### 🗺️ Mapa")
        with map_tile_col:
            tile_key = st.selectbox(
                "Styl mapy",
                options=list(TILE_PROVIDERS.keys()),
                index=0,
                key="tile_select",
                label_visibility="collapsed",
            )

        # Filtry warstw mapy
        lf1, lf2, lf3, lf4 = st.columns(4)
        with lf1:
            show_budowy = st.checkbox("🏢 Budowy", value=True, key="lf_budowy")
        with lf2:
            show_warsztaty = st.checkbox("🔧 Warsztaty", value=True, key="lf_warsztaty")
        with lf3:
            show_mechanicy = st.checkbox("👷 Mechanicy", value=True, key="lf_mechanicy")
        with lf4:
            show_trasy = st.checkbox("🛣️ Trasy", value=True, key="lf_trasy")

        fmap = build_map(
            filtered_mechanicy, budowy_df, warsztaty_df,
            selected_budowa=selected_budowa,
            routes=routes_for_map,
            tile_key=tile_key,
            use_clusters=True,
            show_budowy=show_budowy,
            show_warsztaty=show_warsztaty,
            show_mechanicy=show_mechanicy,
            show_trasy=show_trasy,
        )
        # returned_objects=[] → brak rerun przy zoom/pan mapy
        st_folium(fmap, use_container_width=True, height=580, returned_objects=[])

        # Legenda tras (pod mapą)
        if routes_for_map:
            legend_items = []
            for i, rt in enumerate(routes_for_map):
                color = get_route_color(i)
                name = rt.get("label", "")
                dist = rt.get("dist", "")
                dur = rt.get("dur", "")
                best_tag = " ⭐" if rt.get("is_best") else ""
                rank = f"#{i+1}"
                legend_items.append(
                    f'<span style="display:inline-flex;align-items:center;margin:2px 8px 2px 0">'
                    f'<span style="display:inline-block;width:14px;height:14px;'
                    f'background:{color};border-radius:2px;margin-right:4px"></span>'
                    f'<span style="font-size:0.8rem">{rank} {name} ({dist} km, {dur} min){best_tag}</span></span>'
                )
            st.markdown(
                '<div style="padding:6px 0;line-height:1.8">'
                + "".join(legend_items) + "</div>",
                unsafe_allow_html=True,
            )

    with col_table:
        st.markdown("### 📊 Analiza Dojazdów")

        if result_df is not None and not result_df.empty:
            display_df = result_df.drop(columns=["_polyline"])

            # Najlepszy wynik
            best = display_df.iloc[0]
            st.markdown(
                f'<div class="best-result">'
                f'<h4>🏆 Najlepszy wybór</h4>'
                f'<p><b>{best["Mechanik"]}</b> ({best["Warsztat"]})<br>'
                f'📏 {best["Dystans (km)"]} km &nbsp;·&nbsp; '
                f'⏱️ {best["Czas (min)"]} min &nbsp;·&nbsp; '
                f'💰 {best["Koszt paliwa (PLN)"]} PLN</p></div>',
                unsafe_allow_html=True,
            )

            # Tabela z podświetleniem najlepszego
            fmt_df = display_df.copy()
            fmt_df["Dystans (km)"] = fmt_df["Dystans (km)"].apply(lambda x: f"{x:.1f}")
            fmt_df["Czas (min)"] = fmt_df["Czas (min)"].apply(lambda x: f"{x:.1f}")
            fmt_df["Koszt paliwa (PLN)"] = fmt_df["Koszt paliwa (PLN)"].apply(lambda x: f"{x:.2f}")
            st.markdown(_render_table(fmt_df, highlight_row=0), unsafe_allow_html=True)

            # Eksport CSV
            csv_data = display_df.to_csv(index=False, sep=";", decimal=",")
            target_name = analysis_target or selected_budowa or "analiza"
            st.download_button(
                label="📥 Pobierz Raport (.csv)",
                data=csv_data.encode("utf-8-sig"),
                file_name=f"raport_{target_name.replace(' ', '_')}.csv",
                mime="text/csv",
                use_container_width=True,
            )



            # Breakdown per warsztat
            st.markdown("---")
            st.markdown("#### 🔧 Podział wg warsztatów")
            ws_summary = display_df.groupby("Warsztat").agg(
                Mechaników=("Mechanik", "count"),
                Śr_dystans_km=("Dystans (km)", "mean"),
                Śr_koszt_PLN=("Koszt paliwa (PLN)", "mean"),
            ).round(1).reset_index()
            st.markdown(_render_table(ws_summary), unsafe_allow_html=True)

        elif dest_name and analysis_mechanicy.empty:
            st.info(
                "ℹ️ Brak mechaników do analizy. "
                "Zmień filtr warsztatów lub wybierz mechaników."
            )
        else:
            st.info("ℹ️ Wybierz cel i kliknij **🔍 Analizuj dojazdy** w panelu bocznym.")

    # ── C1: Wykres porównawczy mechaników ─────────────────────────────
    if result_df is not None and not result_df.empty:
        chart_budowa = analysis_target or selected_budowa or ""
        st.markdown("---")
        st.markdown("### 📊 Wykres porównawczy")
        chart_df = result_df.drop(columns=["_polyline"]).copy()
        chart_metric = st.radio(
            "Metryka wykresu:",
            ["Dystans (km)", "Czas (min)", "Koszt paliwa (PLN)"],
            horizontal=True,
            key="chart_metric",
        )
        fig = px.bar(
            chart_df.sort_values(chart_metric),
            x="Mechanik",
            y=chart_metric,
            color="Warsztat",
            text_auto=True,
            title=f"{chart_metric} — dojazd na {chart_budowa}",
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig.update_layout(
            xaxis_tickangle=-45,
            height=400,
            margin=dict(t=40, b=80),
            template="plotly_dark" if dark_mode else "plotly",
            paper_bgcolor="rgba(0,0,0,0)" if dark_mode else "#ffffff",
            plot_bgcolor="rgba(0,0,0,0)" if dark_mode else "#f8fafc",
            font_color="#e2e8f0" if dark_mode else "#1e293b",
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── C2: Porównanie wielu budów ───────────────────────────────────
    if not budowy_df.empty and not analysis_mechanicy.empty:
        with st.expander("🔁 Porównanie wielu budów — najlepszy mechanik dla każdej"):
            comparison_rows = []
            for _, bud in budowy_df.iterrows():
                best_dist = float("inf")
                best_name = ""
                best_warsz = ""
                for _, mech in analysis_mechanicy.iterrows():
                    d = haversine_km(mech["lat"], mech["lon"], bud["lat"], bud["lon"])
                    if d < best_dist:
                        best_dist = d
                        best_name = mech["mechanik"]
                        best_warsz = mech["warsztat"]
                comparison_rows.append({
                    "Budowa": bud["nazwa"],
                    "Najlepszy mechanik": best_name,
                    "Warsztat": best_warsz,
                    "Dystans (km, linia prosta)": round(best_dist, 1),
                })
            comp_df = pd.DataFrame(comparison_rows)
            st.markdown(_render_table(comp_df), unsafe_allow_html=True)

    # ── Stopka centralna ──────────────────────────────────────────────────
    st.markdown(
        '<p style="text-align:center; font-size:0.75rem; opacity:0.5; margin-top:2rem;">'
        "MAPPA v3.1 · © 2026</p>",
        unsafe_allow_html=True,
    )

# ── Punkt wejścia ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()
