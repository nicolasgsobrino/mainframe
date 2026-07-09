import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// allowedHosts:true permite servir tras el proxy del webapp (pestaña Browser)
const server: Record<string, unknown> = {
  host: true,
  port: 5173,
  allowedHosts: true,
  proxy: { "/api": "http://localhost:8080" },
};

export default defineConfig({
  plugins: [react()],
  server,
});
