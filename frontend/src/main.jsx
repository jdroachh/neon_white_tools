import React, { useState, useEffect } from "react";
import { createRoot } from "react-dom/client";

/**
 * M1 smoke-test page.
 *
 * Calls window.pywebview.api.ping() on mount and renders the result.
 * Replace with real page routing in M1 wiring pass.
 */
function PingPage() {
  const [status, setStatus] = useState("Connecting to Python bridge…");

  useEffect(() => {
    function tryPing() {
      if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.ping().then((result) => {
          if (result.ok) {
            setStatus(`Bridge OK — version ${result.version}`);
          } else {
            setStatus("Bridge responded but ok=false");
          }
        }).catch((err) => {
          setStatus(`Bridge error: ${String(err)}`);
        });
      } else {
        // pywebview injects the api asynchronously — retry until ready
        setTimeout(tryPing, 100);
      }
    }
    tryPing();
  }, []);

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      height: "100vh",
      gap: 16,
      fontFamily: "monospace",
    }}>
      <h1 style={{ color: "#ff4fa3", margin: 0 }}>NEON<span style={{ color: "#e0e0e0" }}> WHITE</span> Tools</h1>
      <p style={{ color: "#aaa", margin: 0 }}>M1 Groundwork — pywebview bridge smoke test</p>
      <div style={{
        background: "#222",
        border: "1px solid #444",
        borderRadius: 4,
        padding: "12px 24px",
        color: status.startsWith("Bridge OK") ? "#7fff7f" : "#ffd700",
        fontSize: 14,
      }}>
        {status}
      </div>
    </div>
  );
}

const root = createRoot(document.getElementById("root"));
root.render(<PingPage />);
