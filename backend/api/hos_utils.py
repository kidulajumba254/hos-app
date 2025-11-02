from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import math
import requests
import polyline as pl
import random

Activity = Dict[str, Any]

OVERPASS_ENDPOINT = "https://overpass-api.de/api/interpreter"

def decode_route_polyline(polyline_str: str) -> List[Dict[str, float]]:
    """Decode an OSRM polyline into a list of {lat, lng} points."""
    try:
        points = pl.decode(polyline_str)
        return [{"lat": lat, "lng": lng} for lat, lng in points]
    except Exception:
        return []

def sample_route_points(points: List[Dict[str, float]], sample_distance_km: float = 100.0) -> List[Dict[str, float]]:
    """
    Sample approximately every N kilometers along the route.
    Uses crude lat/lng distance approximation (111 km per degree lat).
    """
    if not points:
        return []
    sampled = [points[0]]
    last = points[0]
    km_accum = 0.0
    for p in points[1:]:
        dx = (p["lng"] - last["lng"]) * 111 * math.cos(math.radians(p["lat"]))
        dy = (p["lat"] - last["lat"]) * 111
        dist = math.sqrt(dx*dx + dy*dy)
        km_accum += dist
        if km_accum >= sample_distance_km:
            sampled.append(p)
            km_accum = 0.0
        last = p
    if sampled[-1] != points[-1]:
        sampled.append(points[-1])
    return sampled

def find_fuel_stations_near_points(points: List[Dict[str, float]], radius_km: float = 10.0, limit_each: int = 10) -> List[Dict[str, Any]]:
    """
    Query Overpass for fuel stations near sampled points.
    Combines results and removes duplicates by rounding coords.
    """
    stations = []
    seen = set()
    for p in points:
        lat, lng = p["lat"], p["lng"]
        # Approximating degrees in km
        delta = radius_km / 111.0
        south, north = lat - delta, lat + delta
        west, east = lng - delta, lng + delta
        sub = find_fuel_stations_bbox(north, south, east, west, limit=limit_each)
        for s in sub:
            key = (round(s["lat"], 3), round(s["lng"], 3))
            if key not in seen:
                seen.add(key)
                stations.append(s)
        # Random small delay or limit number of queries if needed (to respect rate limits)
        if len(stations) > 100:
            break
    random.shuffle(stations)
    return stations


def find_fuel_stations_bbox(north: float, south: float, east: float, west: float, limit: int = 200) -> List[Dict[str, Any]]:
    """
    Query Overpass for fuel stations (amenity=fuel) inside bbox.
    Returns a list of {lat, lon, name}
    """
    # Overpass QL: node["amenity"="fuel"](south,west,north,east);
    query = f"""
    [out:json][timeout:25];
    (
      node["amenity"="fuel"]({south},{west},{north},{east});
      way["amenity"="fuel"]({south},{west},{north},{east});
      relation["amenity"="fuel"]({south},{west},{north},{east});
    );
    out center {limit};
    """
    try:
        resp = requests.post(OVERPASS_ENDPOINT, data={"data": query}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        stations = []
        for el in data.get("elements", []):
            if el.get("type") == "node":
                lat = el.get("lat")
                lon = el.get("lon")
            else:
                center = el.get("center", {})
                lat = center.get("lat")
                lon = center.get("lon")
            name = el.get("tags", {}).get("name", "Fuel Station")
            if lat is None or lon is None:
                continue
            stations.append({"lat": lat, "lng": lon, "name": name})
        return stations
    except Exception:
        
        return []

def bbox_from_points(p1: Dict[str, float], p2: Dict[str, float], pad: float = 0.2) -> Dict[str, float]:
    """Create a bbox (north, south, east, west) padding percentage around points."""
    lat_min = min(p1["lat"], p2["lat"])
    lat_max = max(p1["lat"], p2["lat"])
    lng_min = min(p1["lng"], p2["lng"])
    lng_max = max(p1["lng"], p2["lng"])
    # add small padding degrees to capture nearby stations
    lat_pad = max(0.01, (lat_max - lat_min) * pad)
    lng_pad = max(0.01, (lng_max - lng_min) * pad)
    return {
        "north": lat_max + lat_pad,
        "south": lat_min - lat_pad,
        "east": lng_max + lng_pad,
        "west": lng_min - lng_pad,
    }

def plan_multi_day_trip(
    start_dt: datetime,
    total_drive_minutes: int,
    cycle_hours_used: float = 0.0,
    distance_miles: Optional[float] = None,
    current_location: Optional[Dict[str, float]] = None,
    pickup_location: Optional[Dict[str, float]] = None,
    dropoff_location: Optional[Dict[str, float]] = None,
    route_polyline: Optional[str] = None,          
    fuel_interval_miles: int = 1000,
    allow_restart: bool = False,
    assume_pickup_minutes: int = 60,
    assume_dropoff_minutes: int = 60,
    fuel_stop_minutes: int = 60,
) -> Dict[str, Any]:

    """
    Top-level multi-day planner:
      - splits route across multiple day windows until remaining driving == 0
      - attempts to place geolocated fuel stops using Overpass if bbox available
      - optionally inserts a 34-hour restart (allow_restart=True) if cycle would be exceeded

    Returns:
      {
        "days": [
           {
             "date": "YYYY-MM-DD",
             "activities": [...],
             "warnings": [...],
             "remaining_cycle_hours": float
           }, ...
        ],
        "trip_summary": {...}
      }
    """
    
    total_drive_td = timedelta(minutes=total_drive_minutes)
    remaining_drive = total_drive_td
    current = start_dt
    days: List[Dict[str, Any]] = []
    overall_warnings: List[str] = []

        
    pois = []
    if route_polyline:
        decoded_points = decode_route_polyline(route_polyline)
        sampled_points = sample_route_points(decoded_points, sample_distance_km=100.0)
        pois = find_fuel_stations_near_points(sampled_points, radius_km=10.0)
    elif pickup_location and dropoff_location and distance_miles and distance_miles > 50:
        bbox = bbox_from_points(pickup_location, dropoff_location)
        pois = find_fuel_stations_bbox(bbox["north"], bbox["south"], bbox["east"], bbox["west"])



    # Computing how many fuel stops expected
    fuel_stops_expected = 0
    if distance_miles and fuel_interval_miles > 0:
        fuel_stops_expected = max(0, math.floor(distance_miles / fuel_interval_miles))

    # iterating day-by-day
    day_index = 0
    fuel_stops_inserted_total = 0
    # Keeping track of cumulative on-duty hours used in current rolling computation
    cycle_hours_remaining = max(0.0, 70.0 - cycle_hours_used)

    
    guard = 0
    max_days = 30

    while remaining_drive > timedelta(0) and guard < 2000 and day_index < max_days:
        guard += 1
        # Outlining a day planner that respects 14hr window, 11hr drive, breaks etc.
        # then calling a helper that plans up to a single duty-window (no automatic 34h restart in this function).
        day_plan = plan_day_schedule_single_window(
            current,
            int(remaining_drive.total_seconds() / 60.0),
            cycle_hours_used=cycle_hours_used,
            distance_miles=distance_miles,
            fuel_interval_miles=fuel_interval_miles,
            fuel_stop_minutes=fuel_stop_minutes,
            assume_pickup_minutes=assume_pickup_minutes if day_index == 0 else 0,
            assume_dropoff_minutes=assume_dropoff_minutes if remaining_drive <= timedelta(minutes=0) else 0,
            pois=pois,
        )

        # day_plan returns activities (ISO strings), warnings, remaining_cycle_hours, drive_consumed_minutes, fuel_inserted
        activities = day_plan["activities"]
        warnings = day_plan.get("warnings", [])
        drive_consumed_minutes = day_plan.get("drive_consumed_minutes", 0)
        fuel_inserted = day_plan.get("fuel_inserted", 0)
        fuel_stops_inserted_total += fuel_inserted

        # Append day record
        day_date = current.date().isoformat()
        days.append({
            "date": day_date,
            "activities": activities,
            "warnings": warnings,
            "remaining_cycle_hours": day_plan.get("remaining_cycle_hours", 0.0),
            "drive_consumed_minutes": drive_consumed_minutes,
            "fuel_inserted": fuel_inserted,
        })

        # Update trackers
        remaining_drive -= timedelta(minutes=drive_consumed_minutes)
        # advance current to end of last activity
        if activities:
            last_end_iso = activities[-1]["end"]
            # parse iso
            last_end = datetime.fromisoformat(last_end_iso)
            current = last_end
        else:
            # safety: advance one day
            current = current + timedelta(days=1)

        # update cycle_hours_used with used hours this day (approx)
        used_hours_today = sum(
            (datetime.fromisoformat(a["end"]) - datetime.fromisoformat(a["start"])).total_seconds()/3600.0
            for a in activities
        )
        cycle_hours_used += used_hours_today
        cycle_hours_remaining = max(0.0, 70.0 - cycle_hours_used)

        # If driver exceeded cycle and restart allowed, insert a 34-hour restart block and reset cycle_hours_used to 0
        if cycle_hours_used >= 70.0:
            msg = "Cycle would be exceeded. "
            if allow_restart:
                # insert 34h OffDuty block
                restart_start = current
                restart_end = current + timedelta(hours=34)
                days.append({
                    "date": restart_start.date().isoformat(),
                    "activities": [
                        {"start": restart_start.isoformat(), "end": restart_end.isoformat(), "status": "OffDuty", "type": "restart_34", "note": "34-hour restart inserted"}
                    ],
                    "warnings": ["34-hour restart inserted to reset cycle."],
                    "remaining_cycle_hours": 70.0
                })
                # Move current forward and reset cycle counters
                current = restart_end
                cycle_hours_used = 0.0
                cycle_hours_remaining = 70.0
                fuel_stops_inserted_total = fuel_stops_inserted_total  # unchanged
                overall_warnings.append("34-hour restart inserted in plan (allow_restart=True).")
            else:
                overall_warnings.append("Planned activities exceed 70-hour cycle limit. Set allow_restart=true to simulate a 34-hour restart.")
                # we stop further driving
                break

        day_index += 1

    trip_summary = {
        "total_drive_minutes_requested": total_drive_minutes,
        "total_drive_minutes_remaining": int(max(0, remaining_drive.total_seconds() / 60.0)),
        "days_planned": len(days),
        "fuel_stops_expected": fuel_stops_expected,
        "fuel_stops_inserted": fuel_stops_inserted_total,
        "warnings": overall_warnings
    }

    return {"days": days, "trip_summary": trip_summary}

def plan_day_schedule_single_window(
    start_dt: datetime,
    total_drive_minutes: int,
    cycle_hours_used: float = 0.0,
    distance_miles: Optional[float] = None,
    fuel_interval_miles: int = 1000,
    fuel_stop_minutes: int = 60,
    assume_pickup_minutes: int = 60,
    assume_dropoff_minutes: int = 60,
    pois: Optional[List[Dict[str, float]]] = None,
) -> Dict[str, Any]:
    """
    Plan activities inside a single 14-hour duty window (until 14-hr window forces off-duty).
    Returns activities, warnings, remaining_cycle_hours, drive_consumed_minutes, fuel_inserted
    This function is purposely conservative and returns ISO datetimes for easy JSON serialization.
    """
    activities: List[Activity] = []
    warnings: List[str] = []

    drive_td = timedelta(minutes=total_drive_minutes)
    pickup_td = timedelta(minutes=assume_pickup_minutes)
    drop_td = timedelta(minutes=assume_dropoff_minutes)
    fuel_td = timedelta(minutes=fuel_stop_minutes)

    MAX_DRIVING_MINUTES = 11 * 60
    MAX_WINDOW_MINUTES = 14 * 60
    BREAK_AFTER_MINUTES = 8 * 60
    BREAK_DURATION = timedelta(minutes=30)
    CYCLE_LIMIT_HOURS = 70.0

    current = start_dt
    window_start = start_dt
    driving_elapsed = timedelta(0)
    on_duty_elapsed = timedelta(0)

    remaining_drive = drive_td

    # Pickup provided
    if pickup_td.total_seconds() > 0:
        activities.append({"start": current, "end": (current + pickup_td), "status": "OnDuty", "type": "pickup", "note": "Pickup / loading (assumed 1h)"})
        current += pickup_td
        on_duty_elapsed += pickup_td

    # Fuel scheduling without perfect route polyline:
    fuel_stops_inserted = 0
    fuel_stop_schedule_minutes = None
    if distance_miles and fuel_interval_miles > 0:
      
        fuel_stop_schedule_minutes = (fuel_interval_miles / max(1.0, distance_miles)) * total_drive_minutes if distance_miles and distance_miles > 0 else None

    # If POIs provided, we'll use them in round-robin fashion to attach coords to fuel stops
    poi_index = 0

    loop_guard = 0
    consumed_drive_minutes = 0
    while remaining_drive > timedelta(0) and loop_guard < 2000:
        loop_guard += 1

        window_elapsed = current - window_start
        window_minutes_left = MAX_WINDOW_MINUTES - (window_elapsed.total_seconds() / 60.0)
        if window_minutes_left <= 0:
            # must rest 10 hours
            off_end = current + timedelta(hours=10)
            activities.append({"start": current, "end": off_end, "status": "OffDuty", "type": "window_end", "note": "10-hr off to restart 14-hr window"})
            current = off_end
            # done for this duty-window
            break

        driving_allowed_by_11 = timedelta(minutes=MAX_DRIVING_MINUTES) - driving_elapsed
        if driving_allowed_by_11 <= timedelta(0):
            # must rest 10 hours
            off_end = current + timedelta(hours=10)
            activities.append({"start": current, "end": off_end, "status": "OffDuty", "type": "limit_reached", "note": "Reached 11-hr driving limit; 10-hr off required"})
            current = off_end
            break

        # maximum chunk we can drive now
        max_chunk_minutes = min(
            remaining_drive.total_seconds() / 60.0,
            driving_allowed_by_11.total_seconds() / 60.0,
            max(0.0, window_minutes_left)
        )
        if max_chunk_minutes <= 0:
            break

        until_break = timedelta(minutes=BREAK_AFTER_MINUTES) - driving_elapsed
        if until_break < timedelta(minutes=max_chunk_minutes):
            chunk = until_break
        else:
            chunk = timedelta(minutes=max_chunk_minutes)

        # Drive chunk
        activities.append({"start": current, "end": current + chunk, "status": "Driving", "type": "drive", "note": ""})
        current += chunk
        driving_elapsed += chunk
        on_duty_elapsed += chunk
        remaining_drive -= chunk
        consumed_drive_minutes += int(chunk.total_seconds() / 60.0)

        # After chunk, maybe insert fuel stop (heuristic: if chunk length > fuel_stop_schedule_minutes)
        if fuel_stop_schedule_minutes and chunk.total_seconds()/60.0 >= fuel_stop_schedule_minutes:
            # create a fuel stop
            fuel_activity = {"start": current, "end": current + fuel_td, "status": "OnDuty", "type": "fuel_stop", "note": "Fuel stop (assumed 1h)"}
            # attach POI coords if available
            if pois and poi_index < len(pois):
                fuel_activity["location"] = {"lat": pois[poi_index]["lat"], "lng": pois[poi_index]["lng"], "name": pois[poi_index].get("name")}
                poi_index += 1
            activities.append(fuel_activity)
            current += fuel_td
            on_duty_elapsed += fuel_td
            fuel_stops_inserted += 1

        # If driving_elapsed reached 8 hours -> 30 min break (OffDuty)
        if driving_elapsed >= timedelta(minutes=BREAK_AFTER_MINUTES):
            activities.append({"start": current, "end": current + BREAK_DURATION, "status": "OffDuty", "type": "break", "note": "30-min required break"})
            current += BREAK_DURATION
            on_duty_elapsed += BREAK_DURATION
            # We do NOT zero driving_elapsed for the 11-hr check

    # After driving for this window, append dropoff if assumed and if remaining_drive is zero (or if drop_td>0 and we want to always include)
    if assume_dropoff_minutes and remaining_drive <= timedelta(0):
        activities.append({"start": current, "end": current + drop_td, "status": "OnDuty", "type": "dropoff", "note": "Dropoff / unloading (assumed 1h)"})
        current += drop_td
        on_duty_elapsed += drop_td

    # Cycle remaining estimate
    used_this_period = on_duty_elapsed.total_seconds() / 3600.0
    remaining_cycle_hours = max(0.0, CYCLE_LIMIT_HOURS - (cycle_hours_used + used_this_period))

    # serialize datetimes to ISO for JSON output
    serialized = []
    for a in activities:
        s = a.copy()
        if isinstance(s["start"], datetime):
            s["start"] = s["start"].isoformat()
        if isinstance(s["end"], datetime):
            s["end"] = s["end"].isoformat()
        serialized.append(s)

    return {
        "activities": serialized,
        "warnings": warnings,
        "remaining_cycle_hours": remaining_cycle_hours,
        "drive_consumed_minutes": consumed_drive_minutes,
        "fuel_inserted": fuel_stops_inserted,
    }
