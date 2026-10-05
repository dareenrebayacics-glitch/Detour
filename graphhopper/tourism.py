import math
import os
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from html import escape

import folium
import requests
import streamlit as st
import streamlit.components.v1 as components

# ========================================================
# 🔑 API CONFIGURATION
# ========================================================
API_KEY = "ff9ba191-28ed-4d04-b171-0f607e4020ad"
GEO_URL = "https://graphhopper.com/api/1/geocode?"
ROUTE_URL = "https://graphhopper.com/api/1/route?"
MAX_CORRIDOR_KM = 1.0

BASE_SPEEDS = {
    "foot": 1.34,   # ~4.8 km/h (walking pace)
    "bike": 4.17,   # ~15.0 km/h (cycling pace)
    "car": 8.33,    # ~30.0 km/h (urban city traffic)
}

st.set_page_config(
    page_title="Detour — Curated Waypoint Concierge",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="collapsed"
)

THEMES = {
    "Coffee": {"emoji": "☕", "terms": ["cafe", "coffee", "bakery"]},
    "Food": {"emoji": "🥟", "terms": ["restaurant", "bistro", "eatery"]},
    "Architecture": {"emoji": "🏛️", "terms": ["museum", "cathedral", "church", "monument"]},
    "Parks": {"emoji": "🌳", "terms": ["park", "garden", "plaza"]},
    "Galleries": {"emoji": "🎨", "terms": ["art gallery", "theatre", "museum"]},
    "Nightlife": {"emoji": "🍸", "terms": ["bar", "pub", "lounge", "nightclub"]},
}
THEME_LABELS = {f"{v['emoji']} {k}": k for k, v in THEMES.items()}
MODES = {"🚶 Walk": "foot", "🚲 Bike": "bike", "🚗 Drive": "car"}
MODES_REVERSE = {v: k for k, v in MODES.items()}

# Read mode from query parameters if modified directly on the map
url_params = st.query_params
initial_mode = url_params.get("mode", "foot")
if initial_mode not in BASE_SPEEDS:
    initial_mode = "foot"

# --- STYLING ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

:root {
    --bg-page: #FFFFFF;
    --brand-green: #00D639;
    --brand-green-hover: #00BA31;
    --ink-title: #111827;
    --ink-body: #374151;
    --ink-muted: #6B7280;
    --border-line: #E5E7EB;
}

*, *::before, *::after {
    box-sizing: border-box !important;
}

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
    letter-spacing: -0.01em;
    margin: 0 !important;
    padding: 0 !important;
}

.stApp {
    background-color: var(--bg-page);
    color: var(--ink-title);
    overflow-x: hidden !important;
}

#MainMenu, footer, header[data-testid="stHeader"], [data-testid="stToolbar"] {
    display: none !important;
}

.block-container {
    max-width: 100% !important;
    width: 100% !important;
    padding: 0.5rem 1rem 1rem 1rem !important;
    margin: 0 !important;
}

[data-testid="stHorizontalBlock"] {
    gap: 12px !important;
    align-items: stretch !important;
    width: 100% !important;
}

.top-nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: #FFFFFF;
    border: 1px solid var(--border-line);
    border-radius: 8px;
    padding: 10px 18px;
    margin-bottom: 12px;
}
.brand-group {
    display: flex;
    align-items: center;
    gap: 10px;
}
.brand-logo {
    font-size: 18px;
    font-weight: 800;
    color: var(--brand-green);
    letter-spacing: -0.04em;
}
.nav-tagline {
    font-size: 13px;
    color: var(--ink-muted);
    border-left: 1px solid var(--border-line);
    padding-left: 10px;
}

.st-key-left_panel, .st-key-right_panel {
    background: #FFFFFF;
    border: 1px solid var(--border-line);
    border-radius: 8px;
    padding: 16px 14px;
    box-sizing: border-box;
}

.st-key-right_panel {
    max-height: 820px;
    overflow-y: auto !important;
    overflow-x: hidden !important;
}

.stTextInput label, .stSelectbox label {
    font-size: 11px !important;
    font-weight: 600 !important;
    color: var(--ink-muted) !important;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    margin-bottom: 2px;
}
.stTextInput [data-baseweb="input"] {
    background: #FAFAFA !important;
    border: 1px solid var(--border-line) !important;
    border-radius: 6px !important;
}
.stTextInput [data-baseweb="input"]:focus-within {
    background: #FFFFFF !important;
    border-color: var(--brand-green) !important;
}
.stTextInput input {
    font-size: 13.5px !important;
    color: var(--ink-title) !important;
    font-weight: 500 !important;
    padding: 7px 10px !important;
}
.stSelectbox [data-baseweb="select"] {
    border-radius: 6px !important;
    border: 1px solid var(--border-line) !important;
    background: #FAFAFA !important;
}

.st-key-submit_btn button {
    background: var(--brand-green) !important;
    color: #FFFFFF !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
    font-size: 13.5px !important;
    padding: 9px 18px !important;
    border: none !important;
    width: 100%;
    margin-top: 10px;
}
.st-key-submit_btn button:hover {
    background: var(--brand-green-hover) !important;
}

.section-title {
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--ink-muted);
    margin: 14px 0 8px 0;
    border-bottom: 1px solid var(--border-line);
    padding-bottom: 4px;
}

.st-key-right_panel div[data-testid="stVerticalBlockBorderWrapper"] {
    background: #FFFFFF !important;
    border: 1px solid var(--border-line) !important;
    border-radius: 6px !important;
    padding: 10px 12px !important;
    margin-bottom: 8px !important;
    width: 100% !important;
    box-sizing: border-box !important;
}

button[kind="secondary"] {
    background: #FFFFFF !important;
    border: 1px solid var(--border-line) !important;
    border-radius: 6px !important;
    color: var(--ink-body) !important;
    font-size: 12px !important;
    font-weight: 500 !important;
    padding: 4px 10px !important;
    min-height: 0 !important;
}
button[kind="secondary"]:hover {
    border-color: #D1D5DB !important;
    background: #F9FAFB !important;
}

.st-key-map_view {
    border: 1px solid var(--border-line);
    border-radius: 8px;
    overflow: hidden;
    position: relative;
    height: 820px;
}
.st-key-map_view iframe {
    border: none !important;
    display: block !important;
    width: 100% !important;
    height: 820px !important;
}

/* Bouncing Letters Animation */
@keyframes letter-bounce {
    0%, 100% { transform: translateY(0); }
    30% { transform: translateY(-16px) scale(1.08); }
    60% { transform: translateY(2px) scale(0.96); }
}

.loading-backdrop {
    height: 820px;
    width: 100%;
    border-radius: 8px;
    border: 1px solid #E5E7EB;
    background: rgba(248, 250, 252, 0.92);
    backdrop-filter: blur(8px);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
}

.bouncing-brand {
    display: flex;
    gap: 0.35rem;
}

.bouncing-brand span {
    font-family: 'Inter', sans-serif;
    font-size: 2.3rem;
    font-weight: 900;
    letter-spacing: 0.05em;
    color: #00D639;
    display: inline-block;
    animation: letter-bounce 1.05s infinite ease-in-out;
}
</style>
""", unsafe_allow_html=True)

# In your MAP_CSS:
MAP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@500;600;700;800;900&display=swap');
html, body { margin:0; padding:0; height:100%; width:100%; font-family: 'Inter', sans-serif; }
.leaflet-container { background: #F8F9FA; width:100%; height:100%; position: relative; }
.leaflet-tile-pane { filter: grayscale(15%) contrast(98%) brightness(102%); }
.pin-wrap { background: none !important; border: none !important; }

/* Relocate zoom control below the floating overlay */
.leaflet-top.leaflet-left .leaflet-control-zoom {
    margin-top: 64px !important;
    margin-left: 14px !important;
    border: 1px solid #D1D5DB !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08) !important;
}

.map-badge {
    background: #FFFFFF;
    border: 1px solid #D1D5DB;
    border-radius: 4px;
    padding: 3px 8px;
    font-size: 12px;
    font-weight: 600;
    color: #111827;
    white-space: nowrap;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    transform: translate(-50%, -100%);
}
.badge-dot { width: 7px; height: 7px; border-radius: 50%; background: #00D639; flex-shrink: 0; }
.map-badge.dest .badge-dot { background: #111827; }
.map-badge.waypoint { border-color: #00D639; }

/* TRUE FLOATING OVERLAY BAR (CLEAR OF ZOOM CONTROLS) */
.leaflet-floating-card {
    position: absolute;
    top: 14px;
    left: 14px;
    right: 14px;
    z-index: 1000;
    background: rgba(255, 255, 255, 0.96);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    padding: 8px 16px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
}
.leaflet-floating-card .metrics {
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 13.5px;
    font-weight: 600;
    color: #111827;
}
.leaflet-floating-card .metrics .highlight {
    color: #00D639;
    font-weight: 700;
}
.leaflet-floating-card select {
    background: #FFFFFF;
    border: 1px solid #D1D5DB;
    border-radius: 6px;
    padding: 5px 12px;
    font-size: 13px;
    font-weight: 600;
    color: #111827;
    outline: none;
    cursor: pointer;
}
</style>
"""

# --- SPATIAL HELPERS ---
def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0)**2
    return 2.0 * r * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

def min_distance_to_route(poi_lat, poi_lng, route_coords):
    if not route_coords:
        return 0.0
    step = max(1, len(route_coords) // 40)
    sampled = route_coords[::step]
    if route_coords[-1] not in sampled:
        sampled.append(route_coords[-1])
    return min(haversine_km(poi_lat, poi_lng, pt[1], pt[0]) for pt in sampled)

def get_ordinal(n):
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"

@st.cache_data(show_spinner=False, ttl=3600)
def geocode_location(query):
    q_clean = query.strip()
    candidates = [q_clean]
    if "philippines" not in q_clean.lower():
        candidates.append(f"{q_clean}, Philippines")

    for q in candidates:
        url = GEO_URL + urllib.parse.urlencode({"q": q, "limit": "1", "key": API_KEY})
        try:
            r = requests.get(url, timeout=5).json()
            if len(r.get("hits", [])) > 0:
                h = r["hits"][0]
                city = h.get("city", h.get("country", ""))
                name = h.get("name", q_clean)
                return True, h["point"]["lat"], h["point"]["lng"], f"{name} ({city})" if city else name
        except Exception:
            continue
    return False, None, None, f"Could not locate '{query}'"

def query_single_route(waypoints, mode):
    pts = "".join(f"&point={a}%2C{b}" for a, b in waypoints)
    q = urllib.parse.urlencode({"key": API_KEY, "profile": mode}) + pts + "&points_encoded=false"
    try:
        r = requests.get(ROUTE_URL + q, timeout=8).json()
        if "paths" in r:
            return True, r["paths"][0]
        return False, r.get("message", "Segment failed")
    except Exception as e:
        return False, str(e)

def robust_multistop_route(waypoints, mode):
    ok, data = query_single_route(waypoints, mode)
    if ok:
        return True, data

    combined_coords = []
    total_dist = 0

    for i in range(len(waypoints) - 1):
        leg = [waypoints[i], waypoints[i + 1]]
        leg_ok, leg_data = query_single_route(leg, mode)
        if not leg_ok and mode == "foot":
            leg_ok, leg_data = query_single_route(leg, "bike")
        if not leg_ok:
            leg_ok, leg_data = query_single_route(leg, "car")

        if leg_ok:
            pts = leg_data["points"]["coordinates"]
            combined_coords.extend(pts if not combined_coords else pts[1:])
            total_dist += leg_data["distance"]
        else:
            combined_coords.extend([[leg[0][1], leg[0][0]], [leg[1][1], leg[1][0]]])

    if combined_coords:
        expected_speed = BASE_SPEEDS.get(mode, 1.34)
        calculated_time_ms = int((total_dist / expected_speed) * 1000)

        return True, {
            "distance": total_dist,
            "time": calculated_time_ms,
            "points": {"coordinates": combined_coords}
        }
    return False, "Could not map segments."

def _fetch_single_term(args):
    label, lat, lng, term = args
    url = GEO_URL + urllib.parse.urlencode({
        "q": term,
        "limit": 8,
        "point": f"{lat},{lng}",
        "key": API_KEY
    })
    try:
        r = requests.get(url, timeout=4).json()
        return [(label, hit) for hit in r.get("hits", [])]
    except Exception:
        return []

@st.cache_data(show_spinner=False, ttl=3600)
def discover_candidate_places(sampling_points, terms):
    tasks = [(label, lat, lng, term) for label, lat, lng in sampling_points for term in terms]
    found, seen = [], set()

    with ThreadPoolExecutor(max_workers=6) as executor:
        results = executor.map(_fetch_single_term, tasks)

    for hits in results:
        for label, h in hits:
            ck = (round(h["point"]["lat"], 4), round(h["point"]["lng"], 4))
            name = h.get("name", "")
            if name and ck not in seen:
                seen.add(ck)
                found.append({
                    "id": f"{ck[0]}_{ck[1]}",
                    "name": name,
                    "lat": h["point"]["lat"],
                    "lng": h["point"]["lng"],
                    "proximity": label,
                    "address": h.get("street", h.get("city", label))
                })
    return found

def fmt_dist(m, unit):
    return f"{m / 1609.344:.1f} mi" if unit == "mi" else f"{m / 1000:.1f} km"

def fmt_time(ms):
    h, mnt = divmod(int(ms / 1000) // 60, 60)
    return f"{h}h {mnt}m" if h else f"{mnt} min"

def render_leaflet_map(endpoints, stops, pois, theme, profile, unit):
    ep = endpoints
    waypoints = [(ep["s_lat"], ep["s_lng"])] + [(s["lat"], s["lng"]) for s in stops] + [(ep["d_lat"], ep["d_lng"])]
    ok, route_data = robust_multistop_route(waypoints, profile)

    if not ok:
        m = folium.Map(location=[ep["s_lat"], ep["s_lng"]], zoom_start=13, tiles="OpenStreetMap")
        m.get_root().header.add_child(folium.Element(MAP_CSS))
        return m.get_root().render()

    coords = [(p[1], p[0]) for p in route_data["points"]["coordinates"]]
    m = folium.Map(location=[ep["s_lat"], ep["s_lng"]], zoom_start=14, tiles="OpenStreetMap", prefer_canvas=True)
    m.get_root().header.add_child(folium.Element(MAP_CSS))

    folium.PolyLine(coords, color="#00D639", weight=4, opacity=0.95).add_to(m)

    # 1. Start Marker
    start_html = f"""
    <div class="map-badge">
        <span class="badge-dot"></span>
        <span>Start: {escape(ep['s_name'].split(',')[0])}</span>
    </div>
    """
    folium.Marker([ep["s_lat"], ep["s_lng"]], icon=folium.DivIcon(html=start_html, class_name="pin-wrap")).add_to(m)

    # 2. Waypoints
    for idx, s in enumerate(stops, 1):
        stop_html = f"""
        <div class="map-badge waypoint">
            <span class="badge-dot"></span>
            <span>{idx}. {escape(s['name'])}</span>
        </div>
        """
        folium.Marker([s["lat"], s["lng"]], icon=folium.DivIcon(html=stop_html, class_name="pin-wrap")).add_to(m)

    # 3. Destination
    dest_html = f"""
    <div class="map-badge dest">
        <span class="badge-dot"></span>
        <span>End: {escape(ep['d_name'].split(',')[0])}</span>
    </div>
    """
    folium.Marker([ep["d_lat"], ep["d_lng"]], icon=folium.DivIcon(html=dest_html, class_name="pin-wrap")).add_to(m)

    # 4. Filtered Nearby Suggested Points
    chosen_ids = {s["id"] for s in stops}
    for p in pois:
        if p["id"] not in chosen_ids:
            poi_html = f"""
            <div class="map-badge">
                <span>{theme['emoji']} {escape(p['name'])}</span>
            </div>
            """
            folium.Marker([p["lat"], p["lng"]], icon=folium.DivIcon(html=poi_html, class_name="pin-wrap"), tooltip=f"{p['name']} ({p.get('dist_from_route_km', 0)} km off trail)").add_to(m)

    lats = [c[0] for c in coords]
    lngs = [c[1] for c in coords]
    m.fit_bounds([[min(lats), min(lngs)], [max(lats), max(lngs)]], padding=(60, 60))

    # Real Floating Overlay inside Leaflet (HTML Control)
    total_dist_str = fmt_dist(route_data["distance"], unit)
    total_dur_str = fmt_time(route_data["time"])
    stops_count = len(stops)

    mode_options_html = ""
    for label, val in MODES.items():
        selected_attr = 'selected="selected"' if val == profile else ""
        mode_options_html += f'<option value="{val}" {selected_attr}>{label}</option>'

    overlay_card_html = f"""
    <div class="leaflet-floating-card">
        <div class="metrics">
            <span>Span: <span class="highlight">{total_dist_str}</span></span>
            <span>•</span>
            <span>Est: <span class="highlight">{total_dur_str}</span></span>
            <span>•</span>
            <span>{stops_count} Stops</span>
        </div>
        <div>
            <select onchange="updateMode(this.value)">
                {mode_options_html}
            </select>
        </div>
    </div>
    <script>
    function updateMode(newMode) {{
        // Update URL parameter on parent window and trigger rerun
        const currentUrl = new URL(window.parent.location.href);
        currentUrl.searchParams.set('mode', newMode);
        window.parent.location.href = currentUrl.toString();
    }}
    </script>
    """
    m.get_root().html.add_child(folium.Element(overlay_card_html))

    return m.get_root().render()

# State Initialization
for k, v in {
    "stops": [],
    "endpoints": None,
    "pois": [],
    "active_theme": "Coffee",
    "selected_mode": initial_mode,
}.items():
    st.session_state.setdefault(k, v)

# Update state if query parameter changed
st.session_state.selected_mode = initial_mode
profile = st.session_state.selected_mode

# --- TOP NAVIGATION ---
st.markdown("""
<div class="top-nav">
    <div class="brand-group">
        <span class="brand-logo">DETOUR</span>
        <span class="nav-tagline">Curated just for your needs</span>
    </div>
</div>
""", unsafe_allow_html=True)

col_config, col_map, col_itinerary = st.columns([1.1, 2.1, 1.4])

# ==========================================
# 1. LEFT COLUMN: CLEAN INPUT CONTROLS
# ==========================================
with col_config:
    with st.container(key="left_panel"):
        st.markdown('<div style="font-weight:700; font-size:14px; margin-bottom:12px;">Route Settings</div>', unsafe_allow_html=True)

        start_input = st.text_input("Origin", value="High Street BGC, Taguig")
        dest_input = st.text_input("Destination", value="Greenbelt Makati")

        c_theme, c_unit = st.columns([2.5, 1.5])
        with c_theme:
            theme_label = st.selectbox("Target Highlights", list(THEME_LABELS.keys()), index=0)
        with c_unit:
            unit = st.selectbox("Units", ["km", "mi"], index=0)

        theme_key = THEME_LABELS[theme_label]
        theme = THEMES[theme_key]

        calculate = st.button("Search Circuit", key="submit_btn")

# ==========================================
# 2. MIDDLE COLUMN: INTERACTIVE MAP CANVAS
# ==========================================
with col_map:
    map_container = st.container(key="map_view")
    map_placeholder = map_container.empty()

    if calculate:
        map_placeholder.markdown("""
        <div class="loading-backdrop">
            <div class="bouncing-brand">
                <span style="animation-delay: 0.06s;">D</span>
                <span style="animation-delay: 0.14s;">E</span>
                <span style="animation-delay: 0.22s;">T</span>
                <span style="animation-delay: 0.30s;">O</span>
                <span style="animation-delay: 0.38s;">U</span>
                <span style="animation-delay: 0.46s;">R</span>
            </div>
            <div style="font-size:12px; font-weight:600; color:#6B7280; letter-spacing:0.04em; margin-top:14px;">
                Searching your Perfect Detour...
            </div>
        </div>
        """, unsafe_allow_html=True)

        ok_s, s_lat, s_lng, s_name = geocode_location(start_input)
        ok_d, d_lat, d_lng, d_name = geocode_location(dest_input)

        if ok_s and ok_d:
            st.session_state.endpoints = {
                "s_lat": s_lat, "s_lng": s_lng, "s_name": s_name,
                "d_lat": d_lat, "d_lng": d_lng, "d_name": d_name
            }
            st.session_state.stops = []

            base_ok, base_route = robust_multistop_route([(s_lat, s_lng), (d_lat, d_lng)], profile)
            route_pts = base_route["points"]["coordinates"] if base_ok else [[s_lng, s_lat], [d_lng, d_lat]]

            sampling_points = [
                ("Near Start", s_lat, s_lng),
                ("Near Destination", d_lat, d_lng),
            ]

            candidates = discover_candidate_places(sampling_points, theme["terms"])
            corridor_filtered = []
            for c in candidates:
                d_km = min_distance_to_route(c["lat"], c["lng"], route_pts)
                if d_km <= MAX_CORRIDOR_KM:
                    c["dist_from_route_km"] = round(d_km, 1)
                    corridor_filtered.append(c)

            corridor_filtered.sort(key=lambda x: x["dist_from_route_km"])
            st.session_state.pois = corridor_filtered
            st.session_state.active_theme = theme_key
            st.rerun()
        else:
            map_placeholder.empty()
            missing = []
            if not ok_s: missing.append(f"Origin ('{start_input}')")
            if not ok_d: missing.append(f"Destination ('{dest_input}')")
            st.error(f"Could not locate: {', '.join(missing)}. Please verify spelling.")

    # Render Normal Leaflet Map View
    if st.session_state.endpoints:
        rendered_html = render_leaflet_map(
            st.session_state.endpoints,
            st.session_state.stops,
            st.session_state.pois,
            theme,
            profile,
            unit
        )
        with map_placeholder.container():
            components.html(rendered_html, height=820)
    else:
        m = folium.Map(location=[14.5547, 121.0244], zoom_start=13, tiles="OpenStreetMap")
        m.get_root().header.add_child(folium.Element(MAP_CSS))
        with map_placeholder.container():
            components.html(m.get_root().render(), height=820)

# ==========================================
# 3. RIGHT COLUMN: ITINERARY & FILTERED POIS
# ==========================================
with col_itinerary:
    with st.container(key="right_panel"):
        st.markdown('<div style="font-weight:700; font-size:14px; margin-bottom:4px;">Itinerary & Stops</div>', unsafe_allow_html=True)

        if st.session_state.endpoints:
            stops = st.session_state.stops

            st.markdown('<div class="section-title">Active Waypoints</div>', unsafe_allow_html=True)
            if len(stops) == 0:
                st.caption("No intermediate stops added. Click + Add on any spot within 1 km of the trail.")
            else:
                for idx, stop in enumerate(stops, 1):
                    col_name, col_action = st.columns([3, 1])
                    with col_name:
                        st.markdown(f"**{get_ordinal(idx)}:** {stop['name']}")
                    with col_action:
                        if st.button("Remove", key=f"del_{idx}", type="secondary"):
                            st.session_state.stops.pop(idx - 1)
                            st.rerun()

            st.markdown(f'<div class="section-title">{theme["emoji"]} Within 1 km of Route ({len(st.session_state.pois)})</div>', unsafe_allow_html=True)
            if not st.session_state.pois:
                st.caption("No recommendations found within 1 km of this path. Try another theme.")
            for idx, poi in enumerate(st.session_state.pois):
                is_added = any(s["id"] == poi["id"] for s in stops)
                with st.container(border=True):
                    c_lbl, c_btn = st.columns([3, 1.1])
                    with c_lbl:
                        dist_badge = f"{poi.get('dist_from_route_km', 0)} km off trail"
                        st.markdown(f"<div style='font-weight:600; font-size:13.5px; line-height:1.3;'>{poi['name']}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='font-size:11.5px; color:#6B7280; margin-top:2px;'>{dist_badge} • {poi['address']}</div>", unsafe_allow_html=True)
                    with c_btn:
                        if is_added:
                            st.caption("✓ Added")
                        else:
                            if st.button("+ Add", key=f"add_{idx}", type="secondary"):
                                st.session_state.stops.append(poi)
                                st.rerun()
        else:
            st.caption("Plan a trip on the left to discover curated spots along your corridor.")
