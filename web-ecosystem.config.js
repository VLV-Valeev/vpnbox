
const path = require("path");

const ROOT = __dirname;
const VENV = path.join(ROOT, "venv", "bin");
const LOGS = path.join(ROOT, "logs");
const WEB = path.join(ROOT, "web");

module.exports = {
  apps: [
    {
      name: "vpnbox-api",
      script: path.join(VENV, "python"),
      args: "run_api.py",
      cwd: ROOT,
      interpreter: "none",
      autorestart: true,
      max_restarts: 10,
      restart_delay: 3000,
      max_memory_restart: "500M",
      watch: false,
      log_date_format: "YYYY-MM-DD HH:mm:ss Z",
      error_file: path.join(LOGS, "api-error.log"),
      out_file: path.join(LOGS, "api-out.log"),
      merge_logs: true,
    },
    {
      name: "vpnbox-web",
      script: "node",
      args: ".next/standalone/server.js",
      cwd: WEB,
      interpreter: "none",
      autorestart: true,
      max_restarts: 10,
      restart_delay: 3000,
      max_memory_restart: "500M",
      watch: false,
      env: {
        PORT: "3000",
        NODE_ENV: "production",
      },
      log_date_format: "YYYY-MM-DD HH:mm:ss Z",
      error_file: path.join(LOGS, "web-error.log"),
      out_file: path.join(LOGS, "web-out.log"),
      merge_logs: true,
    },
  ],
};
