// ─── main.jsx ─────────────────────────────────────────────────────────────────
// React entry point.
// Poin 4: App itself handles all auto-refresh (useAutoFetch + window focus),
// so main.jsx stays minimal — zero business logic here.

import { StrictMode } from "react";
import { createRoot }  from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "./styles/dark-style.css";
import "./styles/light-style.css";
import App from "./App.jsx";
import { AuthProvider } from "./AuthContext.jsx";
import { ErrorBoundary, OfflineBanner } from "./components.jsx";

// Emergency Mobile Logger — DEV only, never runs in production
if (import.meta.env.DEV) {
  window.onerror = function(msg, url, line, col, error) {
    const div = document.createElement('div');
    div.style.cssText = "position:fixed;top:0;left:0;width:100%;z-index:99999;background:#800;color:#fff;font:10px monospace;padding:10px;overflow:auto;max-height:50vh;border-bottom:2px solid #f00";
    div.innerHTML = `<strong>JS ERROR:</strong> ${msg}<br><small>At: ${url}:${line}:${col}</small><br><pre>${error?.stack || ''}</pre>`;
    document.body.appendChild(div);
  };

  window.onunhandledrejection = function(event) {
    const div = document.createElement('div');
    div.style.cssText = "position:fixed;bottom:0;left:0;width:100%;z-index:99999;background:#500;color:#fff;font:10px monospace;padding:10px";
    div.innerHTML = `<strong>PROMISE REJECTION:</strong> ${event.reason}`;
    document.body.appendChild(div);
  };
}

// Service Worker Registration for Offline Media & Fast Loading
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.getRegistrations().then(registrations => {
    for (let registration of registrations) {
      registration.unregister();
    }
  });
  if ('caches' in window) {
    caches.keys().then(names => {
      for (let name of names) caches.delete(name);
    });
  }
}

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <ErrorBoundary>
      <OfflineBanner />
      <AuthProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </AuthProvider>
    </ErrorBoundary>
  </StrictMode>
);
