import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { initObservability } from "./lib/observability";
// Fonts are bundled with the app (no Google Fonts), so they load in mainland China too.
import "@fontsource-variable/inter";
import "@fontsource-variable/inter-tight";
import "@fontsource-variable/manrope";
import "./styles.css";

initObservability();

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);

