
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

[[ $EUID -ne 0 ]] && err "Запусти от root: sudo bash setup_web.sh"
[[ ! -f "run_bot.py" ]] && err "Запусти из корня проекта"
[[ ! -d "venv" ]] && err "venv не найден — сначала запусти setup_bot.sh"
[[ ! -f ".env" ]] && err ".env не найден — сначала запусти setup_bot.sh"
[[ ! -d "web" ]] && err "Папка web/ не найдена"
[[ ! -f "web-ecosystem.config.js" ]] && err "web-ecosystem.config.js не найден"

PROJECT_DIR="$(pwd)"
VENV_DIR="${PROJECT_DIR}/venv"
WEB_DIR="${PROJECT_DIR}/web"
LOG_DIR="${PROJECT_DIR}/logs"


section "Шаг 1/5 · Node.js 20 + PM2"

if ! command -v node &>/dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt install -y -qq nodejs
    log "Node.js установлен."
else
    log "Node.js: $(node --version)"
fi

if ! command -v pm2 &>/dev/null; then
    npm install -g pm2
    log "PM2 установлен."
else
    log "PM2: $(pm2 --version)"
fi


section "Шаг 2/5 · Python web-зависимости"

"${VENV_DIR}/bin/pip" install -q \
    "fastapi==0.115.6" \
    "uvicorn[standard]==0.32.1" \
    "python-jose[cryptography]==3.3.0" \
    "passlib[bcrypt]==1.7.4" \
    "python-multipart==0.0.20" \
    "pydantic[email]==2.9.2" \
    "email-validator==2.2.0" \
    "slowapi==0.1.9" \
    "bcrypt==4.2.1"
log "Web-зависимости установлены."


section "Шаг 3/5 · Переменные окружения"

if ! grep -q "^JWT_SECRET=" "${PROJECT_DIR}/.env"; then
    JWT_SECRET=$(openssl rand -base64 48 | tr -d '/+=')
    cat >> "${PROJECT_DIR}/.env" <<EOF

# ── Web Add-on ────────────────────────────────────────
JWT_SECRET=${JWT_SECRET}
JWT_ALGORITHM=HS256
JWT_EXPIRE_DAYS=30

# reCAPTCHA v3 (необязательно)
RECAPTCHA_SECRET_KEY=
RECAPTCHA_SITE_KEY=

# Домен сайта — поменяй на свой после настройки Nginx
API_CORS_ORIGINS=http://localhost:3000
WEB_URL=http://localhost:3000
EOF
    log "JWT_SECRET и веб-переменные добавлены в .env"
else
    warn "JWT_SECRET уже есть — не перезаписываю"
fi

WEB_ENV="${WEB_DIR}/.env.local"
if [[ ! -f "${WEB_ENV}" ]]; then
    cat > "${WEB_ENV}" <<'EOF'
# URL бэкенда (FastAPI). Поменяй на https://yourdomain.com после настройки Nginx.
NEXT_PUBLIC_API_URL=http://localhost:8000

# Google reCAPTCHA v3 site key (публичный, необязательно)
NEXT_PUBLIC_RECAPTCHA_SITE_KEY=
EOF
    log "Создан web/.env.local"
else
    warn "web/.env.local уже существует — не перезаписываю"
fi


section "Шаг 4/5 · Сборка Next.js (standalone)"

cd "${WEB_DIR}"

log "npm install..."
npm install --prefer-offline 2>&1 | tail -3

log "npm run build..."
npm run build 2>&1 | tail -8


STANDALONE_DIR="${WEB_DIR}/.next/standalone"
if [[ ! -d "${STANDALONE_DIR}" ]]; then
    err "Сборка standalone не удалась — ${STANDALONE_DIR} отсутствует"
fi

log "Копирую статику в standalone..."
mkdir -p "${STANDALONE_DIR}/.next"
rm -rf "${STANDALONE_DIR}/.next/static"
cp -r "${WEB_DIR}/.next/static" "${STANDALONE_DIR}/.next/static"

if [[ -d "${WEB_DIR}/public" ]]; then
    rm -rf "${STANDALONE_DIR}/public"
    cp -r "${WEB_DIR}/public" "${STANDALONE_DIR}/public"
fi

log "Фронтенд собран и собран со статикой."
cd "${PROJECT_DIR}"


section "Шаг 5/5 · Запуск PM2"

mkdir -p "${LOG_DIR}"

pm2 delete vpnbox-api vpnbox-web 2>/dev/null || true
pm2 start web-ecosystem.config.js
pm2 save

echo ""
pm2 status

echo ""
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo -e "${GREEN}  Web-аддон установлен!${NC}"
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo ""
echo -e "  ${CYAN}Запущено:${NC}"
echo    "    vpnbox-api  → http://localhost:8000  (FastAPI)"
echo    "    vpnbox-web  → http://localhost:3000  (Next.js)"
echo ""
echo -e "  ${CYAN}Следующие шаги:${NC}"
echo    "    1. Настрой Nginx + SSL (см. DEPLOY.md, раздел 5)"
echo    "    2. Укажи домен:"
echo    "         nano .env            # API_CORS_ORIGINS, WEB_URL"
echo    "         nano web/.env.local  # NEXT_PUBLIC_API_URL"
echo    "    3. Пересобери фронт с новым доменом:"
echo    "         sudo bash setup_web.sh   (идемпотентно — соберёт заново)"
echo    "       или вручную:"
echo    "         cd web && npm run build && cd .."
echo    "         cp -r web/.next/static web/.next/standalone/.next/"
echo    "         cp -r web/public       web/.next/standalone/ 2>/dev/null || true"
echo    "         pm2 reload web-ecosystem.config.js --update-env"
echo ""
warn "Без настройки домена CORS и reCAPTCHA могут ломаться на проде."
