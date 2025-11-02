import React, { useEffect, useState } from "react";
import html2canvas from "html2canvas";
import jsPDF from "jspdf";

// Define status colors
const colors = {
  OffDuty: "#66cc66",
  Sleeper: "#9966ff",
  Driving: "#1E90FF",
  OnDuty: "#FFA500",
};

// Define Y positions (adjusted to your sheet layout)
const statusY = {
  OffDuty: 162,
  Sleeper: 122,
  Driving: 84,
  OnDuty: 46,
};

// Draws the background image and activity lines
function drawCanvas(ctx, dayActivities, bgImage) {
  const width = 1000;
  const height = (bgImage.naturalHeight / bgImage.naturalWidth) * width;

  ctx.clearRect(0, 0, width, height);
  ctx.drawImage(bgImage, 0, 0, width, height);

  const scaleY = height / bgImage.naturalHeight;

  dayActivities.forEach((a) => {
    const start = new Date(a.start);
    const end = new Date(a.end);
    const startHours = start.getUTCHours() + start.getUTCMinutes() / 60;
    const endHours = end.getUTCHours() + end.getUTCMinutes() / 60;

    const xStart = (startHours / 24) * width;
    const xEnd = (endHours / 24) * width;
    const y = (statusY[a.status] || statusY.OffDuty) * scaleY;

    ctx.strokeStyle = colors[a.status] || "#000";
    ctx.lineWidth = 5;
    ctx.beginPath();
    ctx.moveTo(xStart, y);
    ctx.lineTo(xEnd, y);
    ctx.stroke();
  });
}

const LogCanvas = ({ days = [], driverInfo = {} }) => {
  const [logDays, setLogDays] = useState(days);

  useEffect(() => {
    const bgImage = new Image();
    bgImage.src = "/logsheets/blank-paper-log.png"; 

    bgImage.onload = () => {
      logDays.forEach((day, idx) => {
        const canvas = document.getElementById(`log-${idx}`);
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        drawCanvas(ctx, day.activities, bgImage);
      });
    };
  }, [logDays]);

  // Calculate total hours for each status
  const calcTotalHours = (activities, status) =>
    activities
      .filter((a) => a.status === status)
      .reduce(
        (sum, a) => sum + (new Date(a.end) - new Date(a.start)) / 3600000,
        0
      );

  // Compute total hours for the cycle
  const currentCycleHours = logDays.reduce(
    (sum, d) =>
      sum +
      calcTotalHours(d.activities, "Driving") +
      calcTotalHours(d.activities, "OnDuty"),
    0
  );

 
  const handleCanvasClick = (e, dayIndex) => {
    const canvas = e.target;
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const hours = (x / canvas.width) * 24;

    // Determine clicked status area
    let status = "Driving";
    if (y < canvas.height * 0.25) status = "OnDuty";
    else if (y < canvas.height * 0.5) status = "Driving";
    else if (y < canvas.height * 0.75) status = "Sleeper";
    else status = "OffDuty";

    const newActivity = {
      start: new Date(`2025-11-01T${Math.floor(hours)}:00:00Z`),
      end: new Date(`2025-11-01T${Math.floor(hours + 1)}:00:00Z`),
      status,
    };

    setLogDays((prev) => {
      const updated = [...prev];
      updated[dayIndex].activities.push(newActivity);
      return updated;
    });
  };

  // Export all sheets to a single PDF
  const handleDownloadPDF = async () => {
    const pdf = new jsPDF("landscape", "pt", "a4");
    const currentDate = new Date().toLocaleString();

    for (let i = 0; i < logDays.length; i++) {
      const canvas = document.getElementById(`log-${i}`);
      if (!canvas) continue;

      const canvasImage = await html2canvas(canvas, { scale: 2 });
      const imgData = canvasImage.toDataURL("image/png");
      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = (canvas.height / canvas.width) * pageWidth;

      if (i > 0) pdf.addPage();

      // Header Info
      pdf.setFontSize(14);
      pdf.text("FMCSA DRIVER DAILY LOG SHEET", pageWidth / 2, 30, {
        align: "center",
      });
      pdf.setFontSize(10);
      pdf.text(`Driver: ${driverInfo.name || ""}`, 20, 50);
      pdf.text(`Company: ${driverInfo.company || ""}`, 20, 65);
      pdf.text(`Date: ${logDays[i].date}`, 20, 80);

      
      pdf.addImage(imgData, "PNG", 0, 100, pageWidth, pageHeight);

      // Summary
      const driveHrs = calcTotalHours(logDays[i].activities, "Driving").toFixed(1);
      const onDutyHrs = calcTotalHours(logDays[i].activities, "OnDuty").toFixed(1);
      const offDutyHrs = calcTotalHours(logDays[i].activities, "OffDuty").toFixed(1);

      pdf.text(`Driving Hours: ${driveHrs} hrs`, 20, 110 + pageHeight + 10);
      pdf.text(`On Duty: ${onDutyHrs} hrs`, 220, 110 + pageHeight + 10);
      pdf.text(`Off Duty: ${offDutyHrs} hrs`, 420, 110 + pageHeight + 10);

      pdf.line(20, 130 + pageHeight, 220, 130 + pageHeight);
      pdf.text("Driver Signature", 20, 145 + pageHeight);

      pdf.setFontSize(8);
      pdf.text(`Generated: ${currentDate}`, pageWidth - 160, 145 + pageHeight);
    }

    pdf.save("FMCSA_Driver_Log.pdf");
  };

  return (
    <div style={{ marginTop: 20, textAlign: "center" }}>
      <h2>Driver Daily Log Sheets</h2>
      <p>
        <strong>Cycle Hours Used:</strong> {currentCycleHours.toFixed(1)} hrs
      </p>

      {logDays.map((day, idx) => (
        <div key={idx} style={{ marginTop: 20 }}>
          <div style={{ marginBottom: 8 }}>
            <strong>{day.date}</strong> — {day.activities.length} activities — Fuel:{" "}
            {day.fuel_inserted ?? 0} L
          </div>
          <canvas
            id={`log-${idx}`}
            width={1000}
            height={200}
            style={{
              display: "block",
              margin: "0 auto",
              maxWidth: "100%",
              height: "auto",
              border: "1px solid #ccc",
              borderRadius: 8,
              cursor: "crosshair",
            }}
            onClick={(e) => handleCanvasClick(e, idx)}
          />
        </div>
      ))}

      <button
        onClick={handleDownloadPDF}
        style={{
          marginTop: 20,
          backgroundColor: "#1E90FF",
          color: "white",
          border: "none",
          padding: "10px 20px",
          borderRadius: 6,
          cursor: "pointer",
        }}
      >
        Download FMCSA PDF
      </button>
    </div>
  );
};

export default LogCanvas;
