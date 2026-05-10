const path = require("path");
const ROOT = __dirname;
const VENV = path.join(ROOT, "venv", "bin");
const LOGS = path.join(ROOT, "logs");

module.exports = {
  apps: [
    {
      name: "vpnbox-bot",
      script: path.join(VENV, "python"),
      args: "run_bot.py",
      cwd: ROOT,
      interpreter: "none",
      autorestart: true,
      max_restarts: 10,
      restart_delay: 5000,
      max_memory_restart: "500M",
      watch: false,
      log_date_format: "YYYY-MM-DD HH:mm:ss Z",
      error_file: path.join(LOGS, "bot-error.log"),
      out_file: path.join(LOGS, "bot-out.log"),
      merge_logs: true,
    },
    {
      name: "vpnbox-worker",
      script: path.join(VENV, "celery"),
      args: "-A app.worker.celery_app worker --loglevel=info --concurrency=2",
      cwd: ROOT,
      interpreter: "none",
      autorestart: true,
      max_restarts: 10,
      restart_delay: 5000,
      max_memory_restart: "500M",
      kill_timeout: 30000,
      watch: false,
      log_date_format: "YYYY-MM-DD HH:mm:ss Z",
      error_file: path.join(LOGS, "worker-error.log"),
      out_file: path.join(LOGS, "worker-out.log"),
      merge_logs: true,
    },
    {
      name: "vpnbox-beat",
      script: path.join(VENV, "celery"),
      args: "-A app.worker.celery_app beat --loglevel=info",
      cwd: ROOT,
      interpreter: "none",
      autorestart: true,
      max_restarts: 10,
      restart_delay: 5000,
      instances: 1,
      watch: false,
      log_date_format: "YYYY-MM-DD HH:mm:ss Z",
      error_file: path.join(LOGS, "beat-error.log"),
      out_file: path.join(LOGS, "beat-out.log"),
      merge_logs: true,
    },
  ],
};
