set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[+]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[x]${NC} $*"; exit 1; }
info() { echo -e "${CYAN}[i]${NC} $*"; }

[[ ! -f "run_bot.py" ]] && err "Запусти из корня проекта"
[[ ! -d "venv" ]]       && err "venv не найден — сначала setup_bot.sh"
[[ ! -f "alembic.ini" ]] && err "alembic.ini не найден"
[[ ! -f ".env" ]]       && err ".env не найден"

PROJECT_DIR="$(pwd)"
VENV_DIR="${PROJECT_DIR}/venv"
BACKUP_DIR="${PROJECT_DIR}/backups"
mkdir -p "${BACKUP_DIR}"

PY="${VENV_DIR}/bin/python"
ALEMBIC="${VENV_DIR}/bin/alembic"

if [[ ! -x "${ALEMBIC}" ]]; then
    log "alembic не установлен — ставлю..."
    "${VENV_DIR}/bin/pip" install -q "alembic==1.14.0"
fi

DB_INFO=$("${PY}" - <<'PYEOF'
from urllib.parse import urlparse
from app.config import settings
u = urlparse(settings.database_url.replace("+asyncpg", "").replace("postgresql", "postgresql", 1))
# формат: user|password|host|port|dbname
print(f"{u.username}|{u.password}|{u.hostname}|{u.port or 5432}|{u.path.lstrip('/')}")
PYEOF
)

IFS='|' read -r DB_USER DB_PASS DB_HOST DB_PORT DB_NAME <<<"${DB_INFO}"

if [[ -z "${DB_NAME}" ]]; then
    err "Не удалось распарсить DATABASE_URL из .env"
fi

info "БД: ${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

psql_query() {
    PGPASSWORD="${DB_PASS}" psql -X -A -t \
        -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" \
        -c "$1" 2>/dev/null
}

BACKUP_FILE="${BACKUP_DIR}/pre_migrate_$(date +%Y%m%d_%H%M%S).sql.gz"
log "Бэкап БД → ${BACKUP_FILE}"
PGPASSWORD="${DB_PASS}" pg_dump \
    -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" \
    | gzip > "${BACKUP_FILE}"
log "Бэкап готов ($(du -h "${BACKUP_FILE}" | cut -f1))"

HAS_TABLES=$(psql_query "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' AND table_name <> 'alembic_version'")
HAS_ALEMBIC=$(psql_query "SELECT COUNT(*) FROM information_schema.tables WHERE table_name='alembic_version'")

HAS_TABLES=${HAS_TABLES:-0}
HAS_ALEMBIC=${HAS_ALEMBIC:-0}

info "Таблиц в public: ${HAS_TABLES}, alembic_version: ${HAS_ALEMBIC}"

HAS_REVISIONS=0
if compgen -G "migrations/versions/*.py" >/dev/null 2>&1; then
    HAS_REVISIONS=1
fi

if [[ "${HAS_TABLES}" == "0" && "${HAS_ALEMBIC}" == "0" ]]; then
    log "БД пустая — создаю initial ревизию и применяю"
    if [[ "${HAS_REVISIONS}" == "0" ]]; then
        "${ALEMBIC}" revision --autogenerate -m "initial"
    fi
    "${ALEMBIC}" upgrade head
    log "Готово: БД создана с нуля."
    exit 0
fi

if [[ "${HAS_TABLES}" != "0" && "${HAS_ALEMBIC}" == "0" ]]; then
    warn "БД имеет таблицы, но Alembic о них не знает."
    log "Делаю baseline — создаю initial ревизию и помечаю как применённую (stamp head)"

    if [[ "${HAS_REVISIONS}" == "0" ]]; then
        "${ALEMBIC}" revision --autogenerate -m "baseline"
    fi
    "${ALEMBIC}" stamp head
    log "Baseline установлен. Следующий запуск migrate.sh будет работать штатно."

fi

log "Пробую сгенерировать diff (autogenerate)..."

TS=$(date +%Y%m%d_%H%M%S)
GEN_OUTPUT=$("${ALEMBIC}" revision --autogenerate -m "auto_${TS}" 2>&1 || true)
echo "${GEN_OUTPUT}"

if echo "${GEN_OUTPUT}" | grep -qE "No changes|No new revision"; then
    warn "Изменений в моделях нет — ревизия не создана."
else
    LATEST_REV=$(ls -t migrations/versions/*.py 2>/dev/null | head -1 || true)
    if [[ -n "${LATEST_REV}" ]]; then
        log "Сгенерирована ревизия: ${LATEST_REV}"
    fi
fi

log "Применяю все pending-ревизии (upgrade head)..."
"${ALEMBIC}" upgrade head

log "Текущая ревизия:"
"${ALEMBIC}" current

echo ""
log "Миграция завершена."
echo ""
info "В случае проблем откат: gunzip -c ${BACKUP_FILE} | psql ..."
