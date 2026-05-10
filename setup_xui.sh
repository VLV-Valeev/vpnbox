
set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[+]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[x]${NC} $*"; exit 1; }

[[ $EUID -ne 0 ]] && err "Запусти от root: sudo bash setup_xui.sh"

if command -v x-ui &>/dev/null; then
    warn "3X-UI уже установлен."
    echo ""
    echo -e "  ${CYAN}Управление:${NC}"
    echo    "    x-ui                  — интерактивное меню"
    echo    "    systemctl status x-ui — статус"
    echo    "    systemctl restart x-ui"
    echo ""
    exit 0
fi

log "Устанавливаю 3X-UI (официальный скрипт)..."
bash <(curl -Ls https://raw.githubusercontent.com/mhsanaei/3x-ui/master/install.sh)

echo ""
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo -e "${GREEN}  3X-UI установлен.${NC}"
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo ""
echo -e "  ${CYAN}Дальше:${NC}"
echo    "    1. Открой веб-панель (порт показан выше)"
echo    "    2. Создай inbound (VLESS + REALITY рекомендуется)"
echo    "    3. Запомни URL панели, логин, пароль, inbound_id —"
echo    "       они нужны для VPN_SERVERS в .env бота."
echo ""
