import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Capacitor } from "@capacitor/core";
import { StatusBar, Style } from "@capacitor/status-bar";
import "./index.css";
import App from "./App.jsx";

// Barra de estado del teléfono con el rojo de marca ESACOM -- solo
// tiene efecto dentro del APK (Capacitor); en el navegador normal
// Capacitor.isNativePlatform() es false y esto no hace nada.
if (Capacitor.isNativePlatform()) {
  StatusBar.setBackgroundColor({ color: "#DA291C" }).catch(() => {});
  StatusBar.setStyle({ style: Style.Dark }).catch(() => {}); // texto/íconos blancos
}

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>
);
