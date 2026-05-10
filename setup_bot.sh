
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[+]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[x]${NC} $*"; exit 1; }
section() {
    echo ""
    echo -e "${CYAN}════════════════════════════════════════${NC}"
    echo -e "${CYAN}  $*${NC}"
    echo -e "${CYAN}════════════════════════════════════════${NC}"
    echo ""
}


[[ $EUID -ne 0 ]] && err "Запусти от root: sudo bash setup_bot.sh"
[[ ! -f "run_bot.py" ]] && err "Запусти скрипт из папки с проектом (где лежит run_bot.py)"
[[ ! -f "bot-ecosystem.config.js" ]] && err "bot-ecosystem.config.js не найден"

DISTRO=$(lsb_release -cs 2>/dev/null || echo "unknown")
if [[ "$DISTRO" != "jammy" && "$DISTRO" != "noble" ]]; then
    warn "Скрипт тестирован на Ubuntu 22.04/24.04. Текущий: $DISTRO. Продолжаю."
fi

TOTAL_RAM_MB=$(free -m | awk '/Mem:/ {print $2}')
(( TOTAL_RAM_MB < 1800 )) && warn "RAM ${TOTAL_RAM_MB} МБ — рекомендуется минимум 2 ГБ."

PROJECT_DIR="$(pwd)"
VENV_DIR="${PROJECT_DIR}/venv"
LOG_DIR="${PROJECT_DIR}/logs"
BACKUP_DIR="${PROJECT_DIR}/backups"

DB_PASSWORD=$(openssl rand -base64 20 | tr -d '/+=')
DB_USER="vpnbox"
DB_NAME="vpnbox"


section "Шаг 1/9 · Системные пакеты"

apt update -qq
apt upgrade -y -qq
apt install -y -qq \
    build-essential libpq-dev curl git \
    software-properties-common lsb-release gnupg2 ca-certificates


section "Шаг 2/9 · Python 3.12"

if ! command -v python3.12 &>/dev/null; then
    if [[ "$DISTRO" == "noble" ]]; then
        apt install -y -qq python3.12 python3.12-venv python3.12-dev
    else
        if [[ ! -f /etc/apt/sources.list.d/deadsnakes-ppa.list ]]; then
            apt-key adv --keyserver keyserver.ubuntu.com --recv-keys F23C5A6CF475977595C89F51BA6932366A755776 2>/dev/null || true
            echo "deb https://ppa.launchpadcontent.net/deadsnakes/ppa/ubuntu ${DISTRO} main" \
                > /etc/apt/sources.list.d/deadsnakes-ppa.list
            apt update -qq
        fi
        apt install -y -qq python3.12 python3.12-venv python3.12-dev
    fi
    log "Python 3.12 установлен."
else
    log "Python 3.12 уже есть."
    apt install -y -qq python3.12-venv python3.12-dev 2>/dev/null || true
fi


section "Шаг 3/9 · PostgreSQL 16"

if ! command -v psql &>/dev/null || ! psql --version | grep -q "16"; then
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | \
        gpg --dearmor -o /usr/share/keyrings/postgresql.gpg
    echo "deb [signed-by=/usr/share/keyrings/postgresql.gpg] http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list
    apt update -qq
    apt install -y -qq postgresql-16
    log "PostgreSQL 16 установлен."
else
    log "PostgreSQL 16 уже есть."
fi

systemctl enable --now postgresql

log "Настройка БД..."
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1 \
    || sudo -u postgres psql -c "CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';"

sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1 \
    || sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"

sudo -u postgres psql -c "ALTER USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';" >/dev/null


section "Шаг 4/9 · Redis 7"

if ! command -v redis-server &>/dev/null; then
    curl -fsSL https://packages.redis.io/gpg | gpg --dearmor -o /usr/share/keyrings/redis.gpg
    echo "deb [signed-by=/usr/share/keyrings/redis.gpg] https://packages.redis.io/deb $(lsb_release -cs) main" \
        > /etc/apt/sources.list.d/redis.list
    apt update -qq
    apt install -y -qq redis-server
    log "Redis установлен."
else
    log "Redis уже есть."
fi

if ! grep -q "^maxmemory 256mb" /etc/redis/redis.conf 2>/dev/null; then
    sed -i 's/^# maxmemory .*/maxmemory 256mb/' /etc/redis/redis.conf
    sed -i 's/^# maxmemory-policy .*/maxmemory-policy allkeys-lru/' /etc/redis/redis.conf
    grep -q "^maxmemory " /etc/redis/redis.conf || echo "maxmemory 256mb" >> /etc/redis/redis.conf
    grep -q "^maxmemory-policy " /etc/redis/redis.conf || echo "maxmemory-policy allkeys-lru" >> /etc/redis/redis.conf
fi

systemctl enable --now redis-server
systemctl restart redis-server


section "Шаг 5/9 · Node.js 20 + PM2"

if ! command -v node &>/dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt install -y -qq nodejs
    log "Node.js установлен."
else
    log "Node.js уже есть: $(node --version)"
fi

if ! command -v pm2 &>/dev/null; then
    npm install -g pm2
    log "PM2 установлен."
else
    log "PM2 уже есть."
fi

if ! pm2 list | grep -q "pm2-logrotate"; then
    pm2 install pm2-logrotate >/dev/null 2>&1 || true
    pm2 set pm2-logrotate:max_size 50M        >/dev/null
    pm2 set pm2-logrotate:retain 7            >/dev/null
    pm2 set pm2-logrotate:compress true       >/dev/null
    pm2 set pm2-logrotate:rotateInterval '0 0 * * *' >/dev/null
    log "pm2-logrotate настроен (50MB × 7, ежедневная ротация)."
fi


section "Шаг 6/9 · Python venv + зависимости"

if [[ ! -d "${VENV_DIR}" ]]; then
    python3.12 -m venv "${VENV_DIR}"
    log "venv создан."
fi

PIP="${VENV_DIR}/bin/pip"
"${PIP}" install --upgrade pip -q
"${PIP}" install -r "${PROJECT_DIR}/requirements.txt" -q
log "Python-зависимости установлены."


section "Шаг 7/9 · .env"

if [[ ! -f "${PROJECT_DIR}/.env" ]]; then
    if [[ -f "${PROJECT_DIR}/.env.example" ]]; then
        cp "${PROJECT_DIR}/.env.example" "${PROJECT_DIR}/.env"
    else
        touch "${PROJECT_DIR}/.env"
    fi
    log "Создан .env — заполни его перед запуском."
fi


sed -i "s|postgresql+asyncpg://vpnbox:[^@]*@[^:]*:|postgresql+asyncpg://${DB_USER}:${DB_PASSWORD}@localhost:|g" "${PROJECT_DIR}/.env"
sed -i "s|redis://redis:|redis://localhost:|g" "${PROJECT_DIR}/.env"


section "Шаг 8/9 · Директории + автозапуск PM2"

mkdir -p "${LOG_DIR}" "${BACKUP_DIR}"

pm2 startup systemd -u root --hp /root --service-name pm2-vpnbox 2>/dev/null || true

PM2_SERVICE="/etc/systemd/system/pm2-vpnbox.service"
if [[ -f "$PM2_SERVICE" ]] && ! grep -q "postgresql" "$PM2_SERVICE"; then
    sed -i 's/^After=.*/After=network-online.target postgresql.service redis-server.service/' "$PM2_SERVICE"
    sed -i '/^After=/a Wants=postgresql.service redis-server.service' "$PM2_SERVICE"
    systemctl daemon-reload
fi


section "Шаг 9/10 · Миграция БД (Alembic)"

pg_isready -q && log "PostgreSQL OK" || warn "PostgreSQL не отвечает"
redis-cli ping &>/dev/null && log "Redis OK" || warn "Redis не отвечает"


bash "${PROJECT_DIR}/migrate.sh"


section "Шаг 10/10 · Запуск PM2"

pm2 delete vpnbox-bot vpnbox-worker vpnbox-beat 2>/dev/null || true
pm2 start bot-ecosystem.config.js
pm2 save

echo ""
pm2 status



CRON_JOB="0 3 * * * pg_dump -U ${DB_USER} ${DB_NAME} | gzip > ${BACKUP_DIR}/db_\$(date +\\%Y\\%m\\%d).sql.gz 2>/dev/null"
CRON_CLEANUP="0 4 * * * find ${BACKUP_DIR} -name '*.sql.gz' -mtime +30 -delete"
(crontab -l 2>/dev/null | grep -v "pg_dump.*${DB_NAME}"; echo "$CRON_JOB"; echo "$CRON_CLEANUP") | sort -u | crontab -

echo ""
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo -e "${GREEN}  Бот установлен и запущен!${NC}"
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo ""
echo -e "  Пароль БД:        ${YELLOW}${DB_PASSWORD}${NC} (уже записан в .env)"
echo -e "  Проект:           ${PROJECT_DIR}"
echo -e "  Логи:             ${LOG_DIR}"
echo -e "  Бэкапы:           ${BACKUP_DIR} (автобэкап 03:00, хранение 30 дней)"
echo ""
echo -e "  ${CYAN}Управление:${NC}"
echo    "    pm2 status"
echo    "    pm2 logs vpnbox-bot"
echo    "    pm2 logs vpnbox-worker"
echo    "    pm2 reload bot-ecosystem.config.js --update-env"
echo ""
warn "Заполни .env: nano ${PROJECT_DIR}/.env"
warn "После этого: pm2 reload bot-ecosystem.config.js --update-env"
