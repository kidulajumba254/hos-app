import React, { useState, useEffect, useRef } from "react";
import { MapContainer, TileLayer, Marker, Polyline, Popup } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";
import axios from "axios";
import jsPDF from "jspdf";

const colors = {
  OffDuty: "#66cc66",
  Sleeper: "#9966ff",
  Driving: "#1E90FF",
  OnDuty: "#FFA500",
};

const statusY = {
  OffDuty: 162,
  Sleeper: 122,
  Driving: 84,
  OnDuty: 46,
};

const MapWithLogs = () => {
  const [pickup, setPickup] = useState("Los Angeles, CA");
  const [dropoff, setDropoff] = useState("Dallas, TX");
  const [driverName, setDriverName] = useState("Jesse Kidula");
  const [cycleHoursUsed, setCycleHoursUsed] = useState(0);

  const [trip, setTrip] = useState(null);
  const [stops, setStops] = useState([]);
  const [routeLine, setRouteLine] = useState([]);
  const [loading, setLoading] = useState(false);

  const [logDays, setLogDays] = useState([]);
  const [selectedStatus, setSelectedStatus] = useState("Driving");
  const canvasRefs = useRef([]);
  const [isDrawing, setIsDrawing] = useState(false);

  const [realTime, setRealTime] = useState({ elapsed: 0, remaining: 70 });

  const fuelIcon = new L.Icon({
    iconUrl: "https://cdn-icons-png.flaticon.com/512/2857/2857391.png",
    iconSize: [30, 30],
  });
  const pickupIcon = new L.Icon({
    iconUrl: "https://cdn-icons-png.flaticon.com/512/684/684908.png",
    iconSize: [35, 35],
  });
  const dropoffIcon = new L.Icon({
    iconUrl: "https://cdn-icons-png.flaticon.com/512/1051/1051277.png",
    iconSize: [35, 35],
  });

  const getCityCoords = (cityName) => {
    const coordsMap = {
      "Los Angeles, CA": [34.0522, -118.2437],
      "Dallas, TX": [32.7767, -96.7970],
      "New York, NY": [40.7128, -74.0060],
      "Chicago, IL": [41.8781, -87.6298],
      "Miami, FL": [25.7617, -80.1918],
      "Atlanta, GA": [33.749, -84.388],
      "Seattle, WA": [47.6062, -122.3321],
      "Denver, CO": [39.7392, -104.9903],
      "Houston, TX": [29.7604, -95.3698],
      "Las Vegas, NV": [36.1699, -115.1398],
    };
    return coordsMap[cityName] || [39.8283, -98.5795];
  };

  const generateRoute = async () => {
    if (!pickup || !dropoff) return alert("Enter pickup & dropoff");

    try {
      setLoading(true);
      const res = await axios.post("http://127.0.0.1:8000/api/plan-route/", {
        origin: pickup,
        destination: dropoff,
        driver_name: driverName,
      });
      const data = res.data;
      setTrip(data.trip);
      setStops(data.stops);

      const points = [
        getCityCoords(data.trip.origin),
        ...data.stops.map((s) => [s.latitude, s.longitude]),
        getCityCoords(data.trip.destination),
      ];
      setRouteLine(points);

      const days = data.trip.days || 1;
      setLogDays(
        Array.from({ length: days }).map((_, i) => ({
          date: new Date(Date.now() + i * 86400000).toLocaleDateString(),
          activities: [],
        }))
      );

      setRealTime({
        elapsed: cycleHoursUsed,
        remaining: 70 - cycleHoursUsed,
      });
    } catch (err) {
      console.error(err);
      alert("Failed to generate trip.");
    } finally {
      setLoading(false);
    }
  };

  // Drawing handlers
  const handleMouseDown = (e, dayIdx) => {
    setIsDrawing(true);
    const canvas = canvasRefs.current[dayIdx];
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const startHour = (x / canvas.width) * 24;

    setLogDays((prev) => {
      const newDays = [...prev];
      newDays[dayIdx].activities.push({
        status: selectedStatus,
        startHour,
        endHour: startHour,
      });
      return newDays;
    });
  };

  const handleMouseMove = (e, dayIdx) => {
    if (!isDrawing) return;
    const canvas = canvasRefs.current[dayIdx];
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const hour = (x / canvas.width) * 24;

    setLogDays((prev) => {
      const newDays = [...prev];
      const currentAct =
        newDays[dayIdx].activities[newDays[dayIdx].activities.length - 1];
      currentAct.endHour = hour;
      return newDays;
    });
  };

  const handleMouseUp = () => setIsDrawing(false);

  const drawCanvas = (ctx, activities) => {
    const canvas = ctx.canvas;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    Object.entries(statusY).forEach(([status, y]) => {
      ctx.fillStyle = "#ddd";
      ctx.fillRect(0, y, canvas.width, 2);
    });
    activities.forEach((a) => {
      const xStart = (a.startHour / 24) * canvas.width;
      const xEnd = (a.endHour / 24) * canvas.width;
      const y = statusY[a.status];
      ctx.strokeStyle = colors[a.status];
      ctx.lineWidth = 6;
      ctx.beginPath();
      ctx.moveTo(xStart, y);
      ctx.lineTo(xEnd, y);
      ctx.stroke();
    });
  };

  useEffect(() => {
    logDays.forEach((day, idx) => {
      const canvas = canvasRefs.current[idx];
      if (canvas) drawCanvas(canvas.getContext("2d"), day.activities);
    });
  }, [logDays]);

  
  useEffect(() => {
    const timer = setInterval(() => {
      setRealTime((prev) => ({
        elapsed: Math.min(prev.elapsed + 0.1, 70),
        remaining: Math.max(prev.remaining - 0.1, 0),
      }));
    }, 2000);
    return () => clearInterval(timer);
  }, []);

  const calcHours = (activities, status) =>
    activities
      .filter((a) => a.status === status)
      .reduce((sum, a) => sum + Math.max(a.endHour - a.startHour, 0), 0)
      .toFixed(1);

  const downloadPDF = async () => {
    const pdf = new jsPDF("l", "pt", "a4");
    const currentDate = new Date().toLocaleString();

    for (let i = 0; i < logDays.length; i++) {
      const canvas = canvasRefs.current[i];
      if (!canvas) continue;
      const imgData = canvas.toDataURL("image/png");
      if (i > 0) pdf.addPage();
      pdf.setFontSize(14);
      pdf.text("FMCSA DRIVER DAILY LOG SHEET", pdf.internal.pageSize.getWidth() / 2, 30, { align: "center" });
      pdf.setFontSize(10);
      pdf.text(`Driver: ${driverName}`, 20, 50);
      pdf.text(`Date: ${logDays[i].date}`, 20, 65);
      pdf.addImage(imgData, "PNG", 0, 90, pdf.internal.pageSize.getWidth(), 150);
      pdf.text(`Driving: ${calcHours(logDays[i].activities, "Driving")} hrs`, 20, 260);
      pdf.text(`On Duty: ${calcHours(logDays[i].activities, "OnDuty")} hrs`, 160, 260);
      pdf.text(`Off Duty: ${calcHours(logDays[i].activities, "OffDuty")} hrs`, 300, 260);
      pdf.text(`Generated: ${currentDate}`, 400, 260);
    }

    pdf.save("FMCSA_Driver_Log.pdf");
  };

  return (
    <div style={{ padding: 16 }}>
      <h1>🚛 ELD Route & Interactive Log Planner</h1>

      {/* Inputs */}
      <div style={{ display: "flex", gap: 10, marginBottom: 10 }}>
        <input value={pickup} onChange={(e) => setPickup(e.target.value)} placeholder="Pickup" />
        <input value={dropoff} onChange={(e) => setDropoff(e.target.value)} placeholder="Dropoff" />
        <input value={driverName} onChange={(e) => setDriverName(e.target.value)} placeholder="Driver Name" />
        <input
          type="number"
          min="0"
          max="70"
          value={cycleHoursUsed}
          onChange={(e) => setCycleHoursUsed(parseFloat(e.target.value))}
          placeholder="Current Cycle Hours Used"
        />
        <button onClick={generateRoute} disabled={loading}>
          {loading ? "Generating..." : "Generate Route"}
        </button>
      </div>

      {/* Real-time status */}
      <div style={{ background: "#f0f0f0", padding: "8px", borderRadius: "8px", marginBottom: "10px" }}>
        <strong>⏱ Real-Time Tracker</strong>
        <div>Elapsed Cycle Hours: {realTime.elapsed.toFixed(1)}h</div>
        <div>Remaining Hours: {realTime.remaining.toFixed(1)}h</div>
      </div>

      {/* Map */}
      <MapContainer center={[39.8283, -98.5795]} zoom={5} style={{ height: 400, width: "100%" }}>
        <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        {trip && <Marker position={getCityCoords(trip.origin)} icon={pickupIcon}><Popup>{trip.origin}</Popup></Marker>}
        {trip && <Marker position={getCityCoords(trip.destination)} icon={dropoffIcon}><Popup>{trip.destination}</Popup></Marker>}
        {stops.map((s, i) => (
          <Marker key={i} position={[s.latitude, s.longitude]} icon={fuelIcon}>
            <Popup>Fuel Stop {i + 1}</Popup>
          </Marker>
        ))}
        {routeLine.length > 1 && <Polyline positions={routeLine} color="blue" />}
      </MapContainer>

      {/* Status Buttons */}
      <div style={{ marginTop: 10 }}>
        {Object.keys(colors).map((status) => (
          <button
            key={status}
            onClick={() => setSelectedStatus(status)}
            style={{
              backgroundColor: colors[status],
              color: "white",
              marginRight: 5,
              padding: "5px 10px",
              border: selectedStatus === status ? "2px solid black" : "none",
            }}
          >
            {status}
          </button>
        ))}
      </div>

      {/* Daily Logs */}
      <div style={{ marginTop: 20 }}>
        {logDays.map((day, idx) => (
          <div key={idx} style={{ marginBottom: 20 }}>
            <h3>{day.date}</h3>
            <canvas
              ref={(el) => (canvasRefs.current[idx] = el)}
              width={1000}
              height={200}
              style={{ border: "1px solid #ccc", maxWidth: "100%", height: "auto" }}
              onMouseDown={(e) => handleMouseDown(e, idx)}
              onMouseMove={(e) => handleMouseMove(e, idx)}
              onMouseUp={handleMouseUp}
              onMouseLeave={handleMouseUp}
            />
            <div style={{ marginTop: 5 }}>
              Driving: {calcHours(day.activities, "Driving")} hrs, On Duty: {calcHours(day.activities, "OnDuty")} hrs, Off Duty: {calcHours(day.activities, "OffDuty")} hrs
            </div>
          </div>
        ))}
      </div>

      <button onClick={downloadPDF} style={{ marginTop: 20 }}>
        Download FMCSA PDF
      </button>
    </div>
  );
};

export default MapWithLogs;
