const API_BASE = "http://localhost:8000/api";

export async function planRoute(payload) {
  const resp = await fetch(`${API_BASE}/plan-route/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    const t = await resp.text();
    throw new Error(t);
  }
  return resp.json();
}
