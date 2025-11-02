import React from "react";

const ComplianceSummary = ({ tripSummary = {}, days = [], warnings = [] }) => {
  if (!tripSummary && !days.length) return null;

  const totalDrive = tripSummary.total_drive_hours || 0;
  const totalOnDuty = tripSummary.total_on_duty_hours || 0;
  const totalOffDuty = tripSummary.total_off_duty_hours || 0;
  const totalMiles = tripSummary.total_miles || 0;
  const totalDays = days.length;

  return (
    <div
      style={{
        background: "#f0f5ff",
        borderRadius: 12,
        padding: 16,
        boxShadow: "0 3px 10px rgba(0,0,0,0.1)",
        marginTop: 10,
      }}
    >
      <h3 style={{ marginBottom: 8 }}>📋 Compliance Summary</h3>

      <div style={{ fontSize: 15 }}>
        <div>
          <strong>Total Days:</strong> {totalDays}
        </div>
        <div>
          <strong>Total Miles:</strong> {totalMiles.toLocaleString()} mi
        </div>
        <div>
          <strong>Total Drive Hours:</strong> {totalDrive.toFixed(1)}h
        </div>
        <div>
          <strong>Total On Duty:</strong> {totalOnDuty.toFixed(1)}h
        </div>
        <div>
          <strong>Total Off Duty:</strong> {totalOffDuty.toFixed(1)}h
        </div>
      </div>

      <div
        style={{
          marginTop: 10,
          height: 10,
          background: "#ddd",
          borderRadius: 5,
          overflow: "hidden",
        }}
      >
        {/* Visual drive bar */}
        <div
          style={{
            width: `${Math.min((totalDrive / 70) * 100, 100)}%`,
            height: "100%",
            background:
              totalDrive > 70
                ? "#ff3333"
                : totalDrive > 60
                ? "#ffc107"
                : "#4caf50",
            transition: "width 0.5s ease",
          }}
        ></div>
      </div>

      {/* FMCSA Notice */}
      <div style={{ fontSize: 13, marginTop: 6 }}>
        Rule: Property-carrying driver, max <b>70 hours / 8 days</b> rule
      </div>

      {warnings?.length > 0 && (
        <div
          style={{
            background: "#ffe6e6",
            color: "#b30000",
            borderRadius: 8,
            padding: 10,
            marginTop: 12,
          }}
        >
          <b>⚠️ Compliance Warnings:</b>
          <ul style={{ marginTop: 6, paddingLeft: 18 }}>
            {warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

export default ComplianceSummary;
