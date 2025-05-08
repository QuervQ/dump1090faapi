import datetime
import httpx
import psycopg2
from typing import Optional
from fastapi import FastAPI, HTTPException, Query
from apscheduler.schedulers.background import BackgroundScheduler
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
import os
load_dotenv()
app = FastAPI()
dbuser = os.getenv("DBUSER")
dbpassword = os.getenv("DBPASSWORD")
print(f"DBUSER: {dbuser}")
print(f"DBPASSWORD: {dbpassword}")

pg_conn_info = f"dbname=aircraft user={dbuser} password={dbpassword} host=localhost port=5432"

def get_pg_conn():
    return psycopg2.connect(pg_conn_info)

def initialize_pg_db():
    conn = get_pg_conn()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS aircraft(
            hex TEXT,
            lat REAL,
            lon REAL,
            flight TEXT,
            squawk TEXT,
            altitude REAL,
            timestamp TEXT,
            category TEXT,
            heading REAL,
            PRIMARY KEY (hex, timestamp)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON aircraft(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_hex ON aircraft(hex)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_flight ON aircraft(flight)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_category ON aircraft(category)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_altitude ON aircraft(altitude)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_latlon ON aircraft(lat, lon)")
    conn.commit()
    conn.close()

def insert_to_postgresql(data):
    conn = get_pg_conn()
    cursor = conn.cursor()
    insert_sql = """
    INSERT INTO aircraft (hex, lat, lon, flight, squawk, altitude, timestamp, category, heading)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (hex, timestamp) DO UPDATE SET
        lat = EXCLUDED.lat,
        lon = EXCLUDED.lon,
        flight = EXCLUDED.flight,
        squawk = EXCLUDED.squawk,
        altitude = EXCLUDED.altitude,
        category = EXCLUDED.category,
        heading = EXCLUDED.heading
    """
    for row in data:
        cursor.execute(insert_sql, row)
    conn.commit()
    conn.close()

def put_positions_live():
    url = os.getenv("ip")
    try:
        response = httpx.get(url, timeout=5.0)
        response.raise_for_status()
    except Exception as e:
        print(f"Fetch error: {e}")
        return

    data = response.json()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = []

    for aircraft in data.get("aircraft", []):
        if "lat" not in aircraft or "lon" not in aircraft:
            continue

        rows.append((
            aircraft.get("hex", "N/A"),
            aircraft["lat"],
            aircraft["lon"],
            aircraft.get("flight", "N/A"),
            aircraft.get("squawk", "N/A"),
            aircraft.get("alt_baro", 0),
            now,
            aircraft.get("category", "N/A"),
            aircraft.get("track", 0)
        ))

    if rows:
        insert_to_postgresql(rows)

@app.on_event("startup")
def on_startup():
    initialize_pg_db()
    scheduler = BackgroundScheduler()
    scheduler.add_job(put_positions_live, "interval", seconds=1)
    scheduler.start()

@app.get("/")
def root():
    return {"message": "Hello World"}

@app.get("/positions/live")
def get_positions_live():
    url = os.getenv("ip")
    try:
        response = httpx.get(url, timeout=5.0)
        response.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch data: {e}")

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data = response.json()
    aircraft_list = []

    for a in data.get("aircraft", []):
        if a.get("lat") is None or a.get("lon") is None:
            continue

        aircraft_list.append({
            "hex": a.get("hex", "N/A"),
            "lat": a["lat"],
            "lon": a["lon"],
            "flight": a.get("flight", "N/A"),
            "squawk": a.get("squawk", "N/A"),
            "altitude": a.get("alt_baro", 0),
            "timestamp": now,
            "category": a.get("category", "N/A"),
            "heading": a.get("track", 0)
        })

    return {"aircraft": aircraft_list}

@app.get("/positions/history")
def get_positions_history(
    start: Optional[datetime.datetime] = Query(datetime.datetime.now() - datetime.timedelta(days=1)),
    end: Optional[datetime.datetime] = Query(datetime.datetime.now()),
    hex_code: Optional[str] = None,
    flight: Optional[str] = None,
    squawk: Optional[str] = None,
    altitude_min: Optional[float] = None,
    altitude_max: Optional[float] = None,
    lat_min: Optional[float] = None,
    lat_max: Optional[float] = None,
    lon_min: Optional[float] = None,
    lon_max: Optional[float] = None,
    category: Optional[str] = None,
    heading: Optional[float] = None,
):
    if any([lat_min, lat_max, lon_min, lon_max]) and not all([lat_min, lat_max, lon_min, lon_max]):
        raise HTTPException(status_code=400, detail="All coordinate bounds must be provided if one is used.")

    filters = ["timestamp BETWEEN %s AND %s"]
    params = [start.strftime("%Y-%m-%d %H:%M:%S"), end.strftime("%Y-%m-%d %H:%M:%S")]

    if hex_code:
        filters.append("hex = %s")
        params.append(hex_code)

    if flight:
        filters.append("flight ILIKE %s")
        params.append(f"%{flight}%")

    if squawk:
        filters.append("squawk = %s")
        params.append(squawk)

    if category:
        filters.append("category = %s")
        params.append(category)

    if heading is not None:
        filters.append("heading = %s")
        params.append(heading)

    if altitude_min is not None:
        filters.append("altitude >= %s")
        params.append(altitude_min)

    if altitude_max is not None:
        filters.append("altitude <= %s")
        params.append(altitude_max)

    if lat_min is not None:
        filters.append("lat BETWEEN %s AND %s")
        params.extend([lat_min, lat_max])

    if lon_min is not None:
        filters.append("lon BETWEEN %s AND %s")
        params.extend([lon_min, lon_max])

    query = f"SELECT * FROM aircraft WHERE {' AND '.join(filters)}"

    conn = get_pg_conn()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(query, params)
    results = cursor.fetchall()
    conn.close()

    return {"results": results}
