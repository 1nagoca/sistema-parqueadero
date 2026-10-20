import React from "react";
import ReactDOM from "react-dom/client";

import App from "./App";
import "./index.css";

// Monta la app de React en el <div id="root"> de index.html.
ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

// Solo en el build: en desarrollo el service worker estorbaría la recarga de Vite.
if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js");
  });
}
