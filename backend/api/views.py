from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.http import FileResponse
from datetime import datetime, timedelta
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
import random
import os
import math
from django.core.cache import cache


CALIBRATED_Y = {
    "OffDuty": 190,     # Bottom grid line
    "Sleeper": 144,     # Sleeper Berth line
    "Driving": 98,      # Driving line
    "OnDuty": 53        # On Duty (Not Driving)
}

LOG_TEMPLATE_FILENAME = "blank-paper-log.png"


#Trip Simulation Function
def _simulate_trip(origin, destination, driver_name=None):
    """
    Generates a simulated HOS trip between two U.S. cities.
    Returns dict: {trip, stops, daily_log, activities, trip_summary}
    """

    #Supported cities
    us_cities = {
        "Los Angeles, CA": (34.0522, -118.2437),
        "Dallas, TX": (32.7767, -96.7970),
        "New York, NY": (40.7128, -74.0060),
        "Chicago, IL": (41.8781, -87.6298),
        "Miami, FL": (25.7617, -80.1918),
        "Atlanta, GA": (33.749, -84.388),
        "Seattle, WA": (47.6062, -122.3321),
        "Denver, CO": (39.7392, -104.9903),
        "Houston, TX": (29.7604, -95.3698),
        "Las Vegas, NV": (36.1699, -115.1398),
    }

    start_coords = us_cities.get(origin)
    end_coords = us_cities.get(destination)
    if not start_coords or not end_coords:
        raise ValueError("Origin or destination not supported. Use a known U.S. city string.")

    #Simulate trip distance and duration (capped for realism)
    total_distance = random.randint(800, 1200)
    avg_speed_mph = 55
    total_duration_hours = total_distance / avg_speed_mph
    total_duration_min = int(total_duration_hours * 60)

    # Avoid overlong trips
    max_days = 14
    total_duration_hours = min(total_duration_hours, max_days * 11)

    # Generate fuel stops every 400–600 miles
    num_stops = max(1, int(total_distance // random.randint(400, 600)))
    base_time = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    stops = []

    for i in range(num_stops):
        frac = (i + 1) / (num_stops + 1)
        lat = start_coords[0] + frac * (end_coords[0] - start_coords[0]) + random.uniform(-0.4, 0.4)
        lon = start_coords[1] + frac * (end_coords[1] - start_coords[1]) + random.uniform(-0.4, 0.4)
        stops.append({
            "id": f"fuel-{i+1}",
            "type": "FUEL",
            "latitude": round(lat, 6),
            "longitude": round(lon, 6),
            "timestamp": (base_time + timedelta(hours=(i+1) * (total_duration_hours / (num_stops + 1)))).isoformat() + "Z"
        })

    #Generate day-by-day driving activities
    hours_remaining = total_duration_hours
    current_time = base_time
    daily_log = []
    activities = []
    day = 0

    while hours_remaining > 0:
        day += 1
        driving_today = min(11, math.ceil(hours_remaining * 2) / 2)
        on_duty = driving_today + 1.5
        off_duty = 24 - on_duty

        t0 = current_time
        t1 = t0 + timedelta(hours=0.5)
        t2 = t1 + timedelta(hours=driving_today)
        t3 = t2 + timedelta(hours=1.0)
        t4 = t3 + timedelta(hours=off_duty)

        day_activities = [
            {"status": "OnDuty", "start": t0.isoformat() + "Z", "end": t1.isoformat() + "Z", "day": day},
            {"status": "Driving", "start": t1.isoformat() + "Z", "end": t2.isoformat() + "Z", "day": day},
            {"status": "OnDuty", "start": t2.isoformat() + "Z", "end": t3.isoformat() + "Z", "day": day},
            {"status": "OffDuty", "start": t3.isoformat() + "Z", "end": t4.isoformat() + "Z", "day": day},
        ]

        activities.extend(day_activities)
        daily_log.append({
            "day": day,
            "date": t0.date().isoformat(),
            "driving_hours": round(driving_today, 2),
            "on_duty_hours": round(on_duty, 2),
            "off_duty_hours": round(off_duty, 2),
            "activities_count": len(day_activities)
        })

        hours_remaining -= driving_today
        current_time = t4

    #Add pickup and dropoff
    activities.insert(0, {
        "status": "OnDuty", "type": "Pickup",
        "start": base_time.isoformat() + "Z",
        "end": (base_time + timedelta(hours=1)).isoformat() + "Z",
        "day": 1
    })
    activities.append({
        "status": "OnDuty", "type": "Dropoff",
        "start": (base_time + timedelta(hours=total_duration_hours + 1)).isoformat() + "Z",
        "end": (base_time + timedelta(hours=total_duration_hours + 2)).isoformat() + "Z",
        "day": day
    })

    # Add fuel stop activities
    for s in stops:
        ts = datetime.fromisoformat(s["timestamp"].replace("Z", ""))
        target_day = 1
        for d in daily_log:
            day_start = datetime.fromisoformat(d["date"]) 
            if ts.date() == day_start.date():
                target_day = d["day"]
                break
        activities.append({
            "status": "OnDuty",
            "type": "FuelStop",
            "start": (ts - timedelta(minutes=10)).isoformat() + "Z",
            "end": (ts + timedelta(minutes=20)).isoformat() + "Z",
            "day": target_day,
            "lat": s["latitude"],
            "lng": s["longitude"],
            "stop_id": s["id"]
        })

    activities.sort(key=lambda x: x["start"])

    #Trip metadata
    trip_meta = {
        "origin": origin,
        "destination": destination,
        "total_distance_mi": total_distance,
        "total_duration_min": total_duration_min,
        "driver_name": driver_name or "Driver Unknown",
    }

    # Trip summary
    trip_summary = {
        "total_days": len(daily_log),
        "total_drive_hours": round(sum(d["driving_hours"] for d in daily_log), 2),
        "total_on_duty": round(sum(d["on_duty_hours"] for d in daily_log), 2),
        "total_off_duty": round(sum(d["off_duty_hours"] for d in daily_log), 2),
        "warnings": []
    }

    return {
        "trip": trip_meta,
        "stops": stops,
        "daily_log": daily_log,
        "activities": activities,
        "trip_summary": trip_summary
    }

# API Endpoints
@method_decorator(csrf_exempt, name="dispatch")
class PlanRouteView(APIView):
    def post(self, request):
        try:
            origin = request.data.get("origin", "Los Angeles, CA")
            destination = request.data.get("destination", "Dallas, TX")
            driver_name = request.data.get("driver_name", "Jesse Kidula")

            
            # Check cache first
            cache_key = f"trip_{origin}_{destination}_{driver_name}"
            cached = cache.get(cache_key)
            if cached:
                return Response(cached, status=status.HTTP_200_OK)

            data = _simulate_trip(origin, destination, driver_name)

            # Cache for 1 hour to reduce load
            cache.set(cache_key, data, timeout=3600)

            request.session["latest_trip"] = data
            request.session.modified = True
            return Response(data, status=status.HTTP_200_OK)

        except ValueError as ve:
            return Response({"error": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# PDF Generation View
@method_decorator(csrf_exempt, name="dispatch")
class GenerateLogPDFView(APIView):
    def get(self, request):
        trip_data = request.session.get("latest_trip")
        if not trip_data:
            return Response({"error": "No trip data in session. Generate plan first."},
                            status=status.HTTP_400_BAD_REQUEST)

        template_path = os.path.join(os.getcwd(), LOG_TEMPLATE_FILENAME)
        template_exists = os.path.exists(template_path)

        buffer = BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        page_w, page_h = letter
        natural_w, natural_h = 1000.0, 200.0

        def time_to_x(ts_iso, draw_width):
            dt = datetime.fromisoformat(ts_iso.replace("Z", ""))
            hour = dt.hour + dt.minute / 60.0
            left_margin = 40
            right_margin = 40
            usable = draw_width - left_margin - right_margin
            return left_margin + (hour / 24.0) * usable

        def status_to_y(status, draw_height):
            y_px = CALIBRATED_Y.get(status, CALIBRATED_Y["OffDuty"])
            scale = draw_height / natural_h
            y_from_top = y_px * scale
            return page_h - 120 - y_from_top

        img = ImageReader(template_path) if template_exists else None

        for day_info in trip_data["daily_log"]:
            draw_width = page_w - 80
            draw_height = (natural_h / natural_w) * draw_width
            img_x = 40
            img_y = page_h - 120 - draw_height

            if template_exists:
                p.drawImage(img, img_x, img_y, width=draw_width, height=draw_height)
            else:
                p.setFont("Helvetica-Bold", 12)
                p.drawString(40, page_h - 50, "Template missing")

            p.setFont("Helvetica-Bold", 14)
            p.drawString(40, page_h - 40, f"Driver: {trip_data['trip'].get('driver_name', '')}")
            p.setFont("Helvetica", 10)
            p.drawString(300, page_h - 40,
                         f"Trip: {trip_data['trip']['origin']} → {trip_data['trip']['destination']}")
            p.drawString(40, page_h - 56,
                         f"Date: {day_info['date']} | Day: {day_info['day']} | Distance: {trip_data['trip']['total_distance_mi']} mi")

            day_num = day_info["day"]
            day_acts = [a for a in trip_data["activities"] if a.get("day") == day_num]

            for act in day_acts:
                try:
                    x1 = time_to_x(act["start"], draw_width) + img_x
                    x2 = time_to_x(act.get("end", act["start"]), draw_width) + img_x
                    status = act.get("status", "OnDuty")
                    y = status_to_y(status, draw_height)
                    color = (0, 0.5, 1) if status == "Driving" else (0.9, 0.6, 0.0) if status == "OnDuty" else (0.4, 0.8, 0.4)
                    p.setFillColorRGB(*color)
                    p.rect(x1, y - 4, max(2, x2 - x1), 8, fill=1, stroke=0)

                    if act.get("type") == "FuelStop":
                        fx = (x1 + x2) / 2
                        fy = y
                        p.setFillColorRGB(1, 0, 0)
                        p.circle(fx, fy, 4, fill=1)
                        label = act.get("stop_id", "")
                        p.setFont("Helvetica", 7)
                        p.setFillColorRGB(0, 0, 0)
                        p.drawString(fx + 6, fy - 3, label)
                except Exception:
                    continue

            summary_y = img_y - 30
            p.setFont("Helvetica", 10)
            p.setFillColorRGB(0, 0, 0)
            p.drawString(40, summary_y,
                         f"Day {day_info['day']} Summary: Driving {day_info['driving_hours']}h | On Duty {day_info['on_duty_hours']}h | Off Duty {day_info['off_duty_hours']}h")
            p.showPage()

        p.save()
        buffer.seek(0)
        return FileResponse(buffer, as_attachment=True, filename="daily_log_full.pdf")
