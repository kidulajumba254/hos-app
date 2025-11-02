import React, { useState } from "react";
import MapComponent from "./components/MapComponent";
import LogCanvas from "./components/LogCanvas";
import ComplianceSummary from "./components/ComplianceSummary";
import DaySummarySidebar from "./components/DaySummarySidebar";


export default function App() {
  const [routeData] = useState({
    current: { lat: 41.8781, lng: -87.6298 },
    pickup: { lat: 39.0997, lng: -94.5786 },
    dropoff: { lat: 34.0522, lng: -118.2437 },
  });

  const [routeInfo] = useState({
    duration_minutes: 3000,
    distance_miles: 1750,
  });

  const [planResult, setPlanResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const [selectedDayIndex, setSelectedDayIndex] = useState(null);
  const [selectedStopId, setSelectedStopId] = useState(null);

  const driverInfo = {
    name: "Jesse Kidula",
    company: "Futuristic Ltd",
    tripId: "HOS-TRIP-2025-001",
  };

  const callPlanRoute = async () => {
    setLoading(true);
    try {
      const payload = {
        start_iso: new Date().toISOString(),
        current_location: routeData.current,
        pickup_location: routeData.pickup,
        dropoff_location: routeData.dropoff,
        estimated_drive_minutes: routeInfo.duration_minutes,
        distance_miles: routeInfo.distance_miles,
        allow_restart: true,
        fuel_interval_miles: 1000,
      };
      const res = await fetch("http://127.0.0.1:8000/api/plan-route/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(await res.text());
      const json = await res.json();
      setPlanResult(json);
    } catch (err) {
      alert("Plan request failed: " + err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: 18 }}>
      <h1>🚛 ELD HOS Planner</h1>

      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 16 }}>
  <div>
    <MapComponent
      pickup={routeData.pickup}
      dropoff={routeData.dropoff}
      planData={planResult || {}}
      selectedDayIndex={selectedDayIndex}
      selectedStopId={selectedStopId}
      onSelectDay={setSelectedDayIndex}
      onSelectStop={setSelectedStopId}
    />
    {/* Mini-summary sidebar below the map */}
    {planResult?.days && (
      <div style={{ marginTop: 12 }}>
        <DaySummarySidebar
          days={planResult.days}
          selectedDayIndex={selectedDayIndex}
          onSelectDay={setSelectedDayIndex}
        />
      </div>
    )}
  </div>

  <div>
    <button onClick={callPlanRoute} disabled={loading}>
      {loading ? "Planning..." : "Generate HOS Plan"}
    </button>
    <div style={{ marginTop: 12 }}>
      <strong>Route summary:</strong>
      <div>Distance (mi): {routeInfo.distance_miles}</div>
      <div>Duration (min): {routeInfo.duration_minutes}</div>
    </div>
    <ComplianceSummary
      tripSummary={planResult?.trip_summary}
      days={planResult?.days}
      warnings={planResult?.trip_summary?.warnings}
    />
  </div>
</div>


      {planResult?.days && (
        <div style={{ marginTop: 18 }}>
          <LogCanvas
            days={planResult.days}
            driverInfo={driverInfo}
            tripSummary={planResult.trip_summary}
            selectedDayIndex={selectedDayIndex}
            onSelectDay={setSelectedDayIndex}
          />
        </div>
      )}
    </div>
  );
}
