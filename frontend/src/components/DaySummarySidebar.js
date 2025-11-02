import React from "react";

function calcHours(activities, status) {
  return activities
    .filter((a) => a.status === status)
    .reduce((sum, a) => {
      const s = new Date(a.start);
      const e = new Date(a.end);
      return sum + (e - s) / 3600000;
    }, 0);
}

export default function DaySummarySidebar({ days, selectedDayIndex, onSelectDay }) {
  if (!days || days.length === 0) return null;

  return (
    <div
      style={{
        border: "1px solid #ddd",
        borderRadius: 8,
        padding: 12,
        maxHeight: 400,
        overflowY: "auto",
        background: "#fafafa",
      }}
    >
      <h3>🗓 Trip Overview</h3>
      {days.map((d, idx) => {
        const drive = calcHours(d.activities, "Driving").toFixed(1);
        const off = calcHours(d.activities, "OffDuty").toFixed(1);
        const fuelStops = d.activities.filter((a) => a.type === "fuel_stop").length;

        const active = idx === selectedDayIndex;

        return (
          <div
            key={idx}
            onClick={() => onSelectDay(idx)}
            style={{
              marginBottom: 10,
              padding: 10,
              borderRadius: 6,
              cursor: "pointer",
              background: active ? "#e6f0ff" : "#fff",
              border: active ? "2px solid #1E90FF" : "1px solid #ddd",
              transition: "all 0.2s ease",
            }}
          >
            <div style={{ fontWeight: 600 }}>Day {idx + 1}</div>
            <div style={{ fontSize: 13 }}>
              Drive hrs: {drive} | Rest hrs: {off} | Fuel stops: {fuelStops}
            </div>
          </div>
        );
      })}
    </div>
  );
}
