# VPNBox — Полное руководство по деплою

Документ описывает полную установку VPNBox с нуля на пустой Ubuntu-сервер: 3X-UI панель, Telegram-бот с воркерами и веб-кабинет под HTTPS.

---

## Оглавление

1. [Архитектура](#1-архитектура)
2. [Требования к серверу](#2-требования-к-серверу)
3. [Быстрый старт (TL;DR)](#3-быстрый-старт-tldr)
4. [Подготовка: клонирование репозитория](#4-подготовка-клонирование-репозитория)
5. [Этап 1 — 3X-UI панель](#5-этап-1--3x-ui-панель)
6. [Этап 2 — Telegram-бот + воркеры](#6-этап-2--telegram-бот--воркеры)
7. [Этап 3 — Веб-кабинет (FastAPI + Next.js)](#7-этап-3--веб-кабинет-fastapi--nextjs)
8. [Nginx + SSL](#8-nginx--ssl)
9. [Управление сервисами (PM2, systemd)](#9-управление-сервисами-pm2-systemd)
10. [Обновление проекта](#10-обновление-проекта)
11. [Бэкапы БД](#11-бэкапы-бд)
12. [Безопасность сервера](#12-безопасность-сервера)
13. [Типовые проблемы](#13-типовые-проблемы)
14. [Нюансы и подводные камни](#14-нюансы-и-подводные-камни)

---

## 1. Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                         Пользователь                         │
└───────────────┬────────────────────┬────────────────────────┘
                │                    │
         Telegram Bot API     Браузер (HTTPS)
                │                    │
                │              ┌─────▼──────┐
                │              │   Nginx    │ :443, :80
                │              │  (SSL, CDN)│
                │              └─┬──────┬───┘
                │                │      │
                │        /_next/*│      │/api/*
                │                │      │
                ▼                ▼      ▼
         ┌──────────┐    ┌──────────┐ ┌──────────┐
         │ vpnbox-  │    │ vpnbox-  │ │ vpnbox-  │
         │   bot    │    │   web    │ │   api    │
         │(aiogram) │    │ (Next15) │ │(FastAPI) │
         └────┬─────┘    └──────────┘ └────┬─────┘
              │                             │
              └────────────┬────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
    ┌────▼────┐     ┌──────▼──────┐    ┌────▼────┐
    │PostgreSQL│    │    Redis    │    │  3X-UI  │
    │  :5432  │     │   :6379     │    │  :2053  │
    └─────────┘     └──────▲──────┘    └─────────┘
                           │
                  ┌────────┴────────┐
                  │                 │
           ┌──────▼──────┐   ┌──────▼──────┐
           │vpnbox-worker│   │ vpnbox-beat │
           │  (Celery)   │   │ (scheduler) │
           └─────────────┘   └─────────────┘
```

**Процессы под PM2:**
- `vpnbox-bot` — aiogram long-polling
- `vpnbox-worker` — Celery worker (проверка платежей, истечение подписок, хелсчеки)
- `vpnbox-beat` — Celery beat (планировщик)
- `vpnbox-api` — FastAPI на `:8000` (только если установлен web-аддон)
- `vpnbox-web` — Next.js на `:3000` (только если установлен web-аддон)

**Процессы под systemd (не PM2):**
- `postgresql` — БД
- `redis-server` — очередь/кеш
- `nginx` — reverse proxy для веба
- `x-ui` — VPN-панель (если ставилась на этом же сервере)
- `pm2-vpnbox` — сам PM2, автоматически поднимает все app-процессы при ребуте

---

## 2. Требования к серверу

| Ресурс | Минимум | Рекомендуется |
|--------|---------|---------------|
| ОС | Ubuntu 22.04 (jammy) / 24.04 (noble) | Ubuntu 24.04 |
| CPU | 1 vCPU | 2 vCPU |
| RAM | 2 ГБ | 4 ГБ |
| Диск | 15 ГБ | 30 ГБ SSD |
| Сеть | Публичный IPv4 | IPv4 + IPv6 |
| Доступ | `root` по SSH | + SSH-ключ |

**Сколько серверов нужно:**
- **1 сервер** — бот + веб + 3X-UI на одной машине (подходит для MVP и до ~5000 активных пользователей).
- **2+ серверов** — бот/веб на управляющем, 3X-UI на отдельных VPN-нодах (лучше для скорости и отказоустойчивости).

**Что надо заранее:**
- Домен (например `vpn.example.com`), A-запись которого смотрит на IP веб-сервера.
- Telegram-токен бота от `@BotFather`.
- Свой Telegram ID (узнать: `@userinfobot`) для поля `ADMIN_ID`.
- Хотя бы одна платёжная система (YooKassa / FreeKassa / Platega / CryptoCloud / Telegram Stars).

---

## 3. Быстрый старт (TL;DR)

Для опытных: один сервер, всё на нём, домен уже указывает на IP.

```bash
# 1. Клонирование
mkdir -p /opt/vpnbox && cd /opt/vpnbox
sudo apt update && sudo apt install -y git
git clone https://github.com/rlxrd/VPNBox.git .

# 2. 3X-UI (пропусти если хостинг ставит её сам)
sudo bash setup_xui.sh

# 3. Настрой .env
cp .env.example .env
nano .env   # BOT_TOKEN, BOT_USERNAME, ADMIN_ID, VPN_SERVERS, платёжки

# 4. Бот
sudo bash setup_bot.sh

# 5. Перезапусти бот с заполненным .env
pm2 reload bot-ecosystem.config.js --update-env

# 6. Веб (опционально)
sudo bash setup_web.sh

# 7. Nginx + SSL
DOMAIN=yourdomain.com
sudo apt install -y nginx certbot python3-certbot-nginx
sudo systemctl stop nginx
sudo certbot certonly --standalone -d ${DOMAIN} --non-interactive \
    --agree-tos -m you@example.com
sudo cp nginx.conf /etc/nginx/sites-available/vpnbox
sudo sed -i "s/yourdomain\.com/${DOMAIN}/g" /etc/nginx/sites-available/vpnbox
sudo ln -sf /etc/nginx/sites-available/vpnbox /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl start nginx && sudo systemctl enable nginx

# 8. Перепрошей домен в .env и пересобери фронт
sed -i "s|API_CORS_ORIGINS=.*|API_CORS_ORIGINS=https://${DOMAIN}|" .env
sed -i "s|WEB_URL=.*|WEB_URL=https://${DOMAIN}|" .env
sed -i "s|NEXT_PUBLIC_API_URL=.*|NEXT_PUBLIC_API_URL=https://${DOMAIN}|" web/.env.local
sudo bash setup_web.sh   # пересоберёт фронт и перезапустит PM2

pm2 status
```

---

## 4. Подготовка: клонирование репозитория

```bash
sudo mkdir -p /opt/vpnbox
sudo chown $USER /opt/vpnbox
cd /opt/vpnbox
sudo apt update && sudo apt install -y git nano
git clone https://github.com/rlxrd/VPNBox.git .
```

**Если репозиторий приватный:**
```bash
ssh-keygen -t ed25519 -C "vpnbox-server"
cat ~/.ssh/id_ed25519.pub   # добавь в GitHub → Settings → SSH Keys
git clone git@github.com:rlxrd/VPNBox.git .
```

---

## 5. Этап 1 — 3X-UI панель

**Пропусти этот этап, если:**
- Хостинг ставит 3X-UI сам при покупке сервера.
- У тебя уже есть отдельный VPN-сервер с 3X-UI и ты просто укажешь его в `VPN_SERVERS` бота.

### Установка

```bash
sudo bash setup_xui.sh
```

Скрипт запустит официальный инсталлер `mhsanaei/3x-ui`. Он задаст несколько вопросов — для дефолтных настроек жми Enter.

### Что сделать в панели

1. Открой `http://<IP-сервера>:<порт-панели>` (порт показан в конце установки).
2. Войди с учёткой, которую задал инсталлер.
3. Создай **inbound** (раздел "Подключения" → "Добавить подключение"):
   - Протокол: `VLESS` + `REALITY` (рекомендуется — не детектится DPI).
   - Порт: любой, например `443`.
   - SNI: любой реальный домен, например `www.microsoft.com`.
4. **Запомни:**
   - URL панели (`http://IP:PORT`)
   - Логин / пароль
   - `inbound_id` (обычно `1`)

Эти данные пойдут в `VPN_SERVERS` на следующем этапе.

---

## 6. Этап 2 — Telegram-бот + воркеры

### 6.1. Настрой `.env`

```bash
cd /opt/vpnbox
cp .env.example .env
nano .env
```

**Обязательные поля:**

```env
# Telegram
BOT_TOKEN=123456:ABC-DEF          # от @BotFather
BOT_USERNAME=your_bot             # юзернейм без @
ADMIN_ID=123456789                # твой Telegram ID (через запятую можно несколько)

# Платёжки — заполняй только те, что будешь использовать.
# Пустые провайдеры автоматически отключаются в боте.
YOOKASSA_SHOP_ID=
YOOKASSA_SECRET_KEY=

FREEKASSA_SHOP_ID=
FREEKASSA_SECRET1=
FREEKASSA_SECRET2=
FREEKASSA_API_KEY=

PLATEGA_MERCHANT_ID=
PLATEGA_SECRET_KEY=

CRYPTOCLOUD_SHOP_ID=
CRYPTOCLOUD_API_KEY=

# Telegram Stars — ключи не нужны, работает автоматически.

# VPN-серверы (JSON-массив). Минимум один объект.
VPN_SERVERS=[{"id":1,"name":"Netherlands","panel_type":"3xui","url":"http://127.0.0.1:2053","username":"admin","password":"admin","country":"NL","inbound_id":1,"max_users":500}]

LOG_LEVEL=INFO
```

**`DATABASE_URL` и `REDIS_URL` не трогай** — `setup_bot.sh` впишет их сам с рандомным паролем БД.

### 6.2. Запусти установку

```bash
sudo bash setup_bot.sh
```

Скрипт (≈3–5 минут):
- `apt update && upgrade`
- Ставит PostgreSQL 16, Redis 7, Python 3.12, Node.js 20, PM2
- Создаёт БД `vpnbox` и юзера с рандомным паролем (пишет в `.env`)
- Настраивает Redis (`maxmemory 256mb`, `allkeys-lru`)
- Создаёт `venv` и ставит Python-зависимости
- Запускает через PM2: `vpnbox-bot`, `vpnbox-worker`, `vpnbox-beat`
- Регистрирует PM2 в systemd (`pm2-vpnbox.service`) — поднимается при ребуте
- Ставит cron-бэкап БД (каждый день в 03:00, хранение 30 дней)

### 6.3. Проверь

```bash
pm2 status
```

Должны быть три процесса в состоянии `online`:
```
│ vpnbox-bot    │ online │
│ vpnbox-worker │ online │
│ vpnbox-beat   │ online │
```

Посмотри логи бота:
```bash
pm2 logs vpnbox-bot --lines 30
```
Должно быть что-то вроде `Start polling` без стектрейсов.

### 6.4. Если правил `.env` — обязательно перезагрузи

```bash
pm2 reload bot-ecosystem.config.js --update-env
```
Флаг `--update-env` критичен — без него новые значения `.env` не подтянутся.

### 6.5. Проверь в Telegram

Напиши боту `/start`. Должен ответить. Если админский ID прописан в `.env`, команда `/admin` откроет админ-меню.

---

## 7. Этап 3 — Веб-кабинет (FastAPI + Next.js)

Этот этап нужен, только если хочешь сайт с личным кабинетом. Для чисто-телеграм-бота пропускай.

### 7.1. Запусти установку

```bash
cd /opt/vpnbox
sudo bash setup_web.sh
```

Скрипт:
- Ставит Python web-зависимости (FastAPI, uvicorn, passlib, jose) в тот же `venv`
- Генерирует `JWT_SECRET` и дописывает его в `.env`
- Создаёт `web/.env.local` с дефолтными значениями
- Запускает `npm install` и `npm run build` (режим `standalone`)
- **Копирует `.next/static` и `public/` внутрь `.next/standalone/`** — критически важно, иначе 404 на CSS/JS
- Запускает через PM2: `vpnbox-api` (порт 8000), `vpnbox-web` (порт 3000)

### 7.2. Проверь

```bash
pm2 status
curl http://localhost:8000/api/plans    # должен вернуть JSON тарифов
curl -I http://localhost:3000           # 200 OK
```

Теперь веб доступен по `http://IP-сервера:3000` — но это временно, нужно закрыть за HTTPS.

---

## 8. Nginx + SSL

В репозитории уже есть готовый `nginx.conf` с upstream-блоками, immutable-кешем для `/_next/static/`, HSTS, редиректом HTTP→HTTPS.

### 8.1. Убедись, что DNS указывает на сервер

```bash
dig +short yourdomain.com
```
Должен вернуть IP твоего сервера. Если нет — добавь A-запись в DNS-панели домена и подожди 5–10 минут.

### 8.2. Установи nginx и certbot

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

### 8.3. Получи SSL-сертификат (standalone-режим)

Сертификат получаем **до** копирования конфига, потому что в конфиге уже прописаны пути к `/etc/letsencrypt/live/...`, которых ещё нет. В `--standalone` режиме certbot сам поднимет временный HTTP-сервер на 80 порту.

```bash
DOMAIN=yourdomain.com

sudo systemctl stop nginx 2>/dev/null || true   # освободить 80 порт

sudo certbot certonly --standalone \
    -d ${DOMAIN} \
    --non-interactive \
    --agree-tos \
    -m you@example.com
```

Сертификаты появятся в `/etc/letsencrypt/live/${DOMAIN}/`.

### 8.4. Скопируй и подставь домен

```bash
sudo cp /opt/vpnbox/nginx.conf /etc/nginx/sites-available/vpnbox
sudo sed -i "s/yourdomain\.com/${DOMAIN}/g" /etc/nginx/sites-available/vpnbox

sudo ln -sf /etc/nginx/sites-available/vpnbox /etc/nginx/sites-enabled/vpnbox
sudo rm -f /etc/nginx/sites-enabled/default

sudo nginx -t    # проверка синтаксиса
sudo systemctl start nginx
sudo systemctl enable nginx
```

### 8.5. Добавь автоперезагрузку nginx после renew

Certbot обновляет сертификат раз в 60 дней, но nginx его не подхватит без reload:

```bash
sudo tee /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh >/dev/null <<'EOF'
#!/bin/bash
systemctl reload nginx
EOF
sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
```

### 8.6. Пропиши домен в конфиги веба

```bash
cd /opt/vpnbox

# В .env — CORS и ссылки в API
sed -i "s|API_CORS_ORIGINS=.*|API_CORS_ORIGINS=https://${DOMAIN}|" .env
sed -i "s|WEB_URL=.*|WEB_URL=https://${DOMAIN}|" .env

# В web/.env.local — URL API для фронтенда
sed -i "s|NEXT_PUBLIC_API_URL=.*|NEXT_PUBLIC_API_URL=https://${DOMAIN}|" web/.env.local
```

### 8.7. Пересобери фронт с новым доменом

```bash
sudo bash setup_web.sh
```
Идемпотентный скрипт — заново соберёт фронт с правильным `NEXT_PUBLIC_API_URL` и перезапустит PM2.

### 8.8. Проверь

```bash
curl -I https://yourdomain.com                 # 200 OK
curl -I https://yourdomain.com/_next/static/   # 404 или 200 с Cache-Control: immutable
curl -s https://yourdomain.com/api/plans       # JSON
```

Открой `https://yourdomain.com` в браузере. В DevTools → Network все CSS/JS должны отдаваться с `200` и заголовком `Cache-Control: immutable` для `/_next/static/*`.

### 8.9. Несколько доменов / subdomains

Если хочешь и apex и `www`:

```bash
sudo certbot certonly --standalone \
    -d yourdomain.com \
    -d www.yourdomain.com \
    --non-interactive --agree-tos -m you@example.com
```
И в `nginx.conf` в двух `server_name` перечисли через пробел: `server_name yourdomain.com www.yourdomain.com;`.

---

## 9. Управление сервисами (PM2, systemd)

### PM2 (бот и веб)

```bash
pm2 status                        # все процессы
pm2 logs vpnbox-bot               # логи в live-режиме (Ctrl+C — выход)
pm2 logs vpnbox-bot --lines 200   # последние 200 строк
pm2 logs vpnbox-worker
pm2 logs vpnbox-api
pm2 logs vpnbox-web

pm2 reload bot-ecosystem.config.js --update-env    # graceful restart с новым .env
pm2 reload web-ecosystem.config.js --update-env

pm2 restart vpnbox-bot            # hard restart одного процесса
pm2 stop vpnbox-worker            # остановить
pm2 start vpnbox-worker           # запустить
pm2 delete vpnbox-worker          # удалить из списка PM2

pm2 save                          # сохранить текущий список в dump.pm2
pm2 monit                         # интерактивный монитор (CPU/RAM/логи)
```

### Автозапуск при ребуте

```bash
sudo systemctl status pm2-vpnbox.service   # должен быть enabled + active
```

Если по какой-то причине не автостартится:
```bash
pm2 startup systemd -u root --hp /root --service-name pm2-vpnbox
pm2 save
```

### systemd-сервисы

```bash
systemctl status postgresql
systemctl status redis-server
systemctl status nginx
systemctl status x-ui            # если ставил на этом сервере

# Рестарт:
sudo systemctl restart postgresql
sudo systemctl restart redis-server
sudo systemctl reload nginx      # reload без обрыва соединений
```

---

## 10. Обновление проекта

**Правило на коробке**: после каждого `git pull`, если в моделях были изменения, прогоняем `migrate.sh` — он сам разберётся.

### Только бот (без веба)

```bash
cd /opt/vpnbox
git pull
venv/bin/pip install -r requirements.txt -q
sudo bash migrate.sh                     # автобэкап + diff + применение
pm2 reload bot-ecosystem.config.js --update-env
```

### Бот + веб

```bash
cd /opt/vpnbox
git pull
venv/bin/pip install -r requirements.txt -q
sudo bash migrate.sh                     # миграция БД
sudo bash setup_web.sh                   # пересобрать фронт и перезапустить веб
pm2 reload bot-ecosystem.config.js --update-env
```

### Миграции (Alembic async) — как это устроено

- **`alembic.ini`** не содержит `sqlalchemy.url` — URL берётся из `.env` динамически через `app.config.settings` (важно для коробки: у каждого клиента свой `.env`).
- **`migrations/env.py`** — async, использует `create_async_engine` + `run_sync`. Автоматически импортирует все модели из `app.db.models` → при `--autogenerate` видит все таблицы.
- **`migrations/versions/*.py`** — **в `.gitignore`**. У каждого клиента свой набор ревизий, они отражают историю именно его БД. Коммитится только `env.py` и `script.py.mako`.
- **`migrate.sh`** — один скрипт, который:
    1. Делает автобэкап БД в `backups/pre_migrate_<ts>.sql.gz`.
    2. Определяет состояние БД:
       - **Пустая** → создаёт "initial" ревизию и применяет → схема с нуля.
       - **С таблицами, но без `alembic_version`** → делает `alembic stamp head` (baseline — помечает текущую схему как отправную точку, миграции не применяет).
       - **Нормальное состояние** → пробует `alembic revision --autogenerate`. Если diff есть — создаёт ревизию. Применяет все pending через `alembic upgrade head`.
- **`create_all` убран из startup-хендлеров** бота и API — схема теперь управляется только через Alembic.

### Первый раз на существующей БД

Если у клиента уже есть продовая БД (например, после предыдущей версии без Alembic):

```bash
cd /opt/vpnbox
venv/bin/pip install -r requirements.txt -q
sudo bash migrate.sh
```
Скрипт увидит таблицы + отсутствие `alembic_version` → сделает baseline. С этого момента любые изменения моделей будут нормально мигрировать.

### Ручные команды Alembic

```bash
source venv/bin/activate

alembic current                          # текущая ревизия
alembic history                          # история всех ревизий
alembic revision --autogenerate -m "msg" # создать новую ревизию вручную
alembic upgrade head                     # применить все pending
alembic downgrade -1                     # откатить на 1 ревизию назад
alembic stamp head                       # пометить текущее состояние как head
                                         # (без выполнения, для baseline)
```

### Что autogenerate НЕ ловит

Alembic `--autogenerate` хорош, но не идеален. **Обязательно поправь вручную** в сгенерированном `.py` ревизии:
- Переименование колонок (видит как `drop_column` + `add_column` → потеряешь данные!)
- Переименование таблиц (аналогично)
- Изменение `CHECK constraint` 
- Кастомные типы и enum'ы PostgreSQL

Перед применением в проде всегда посмотри `migrations/versions/*_auto_*.py` — если видишь `drop_column` того, что должно было быть переименовано, поправь на `op.alter_column('old', new_column_name='new')`.

### Вручную (если нужно контролировать веб-сборку)

```bash
cd /opt/vpnbox/web
npm install
npm run build

# КРИТИЧНО — скопировать статику в standalone:
cp -r .next/static .next/standalone/.next/static
[ -d public ] && cp -r public .next/standalone/public

cd ..
pm2 reload bot-ecosystem.config.js --update-env
pm2 reload web-ecosystem.config.js --update-env
```

### Откат к предыдущей версии

```bash
cd /opt/vpnbox
git log --oneline -20            # найди нужный коммит
git checkout <commit-hash>
venv/bin/pip install -r requirements.txt -q
sudo bash setup_web.sh
pm2 reload all --update-env
```

---

## 11. Бэкапы БД

### Автоматический бэкап

`setup_bot.sh` ставит cron на 03:00 каждый день:
```cron
0 3 * * * pg_dump -U vpnbox vpnbox | gzip > /opt/vpnbox/backups/db_YYYYMMDD.sql.gz
0 4 * * * find /opt/vpnbox/backups -name '*.sql.gz' -mtime +30 -delete
```

### Ручной бэкап

```bash
cd /opt/vpnbox
pg_dump -U vpnbox vpnbox | gzip > backups/manual_$(date +%Y%m%d_%H%M).sql.gz
```

### Восстановление

```bash
# 1. Остановить всё, что пишет в БД
pm2 stop vpnbox-bot vpnbox-worker vpnbox-beat vpnbox-api

# 2. Восстановить
gunzip -c backups/db_20260101.sql.gz | psql -U vpnbox vpnbox

# 3. Запустить обратно
pm2 start all
```

### Бэкап на внешнее хранилище

Добавь в cron копирование на S3 / rsync / ssh:
```cron
30 3 * * * rsync -az /opt/vpnbox/backups/ backupuser@backup-server:/backups/vpnbox/
```

---

## 12. Безопасность сервера

### UFW (firewall)

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp       # SSH (не запирайся сам)
sudo ufw allow 80/tcp       # HTTP
sudo ufw allow 443/tcp      # HTTPS
sudo ufw allow 2053/tcp     # 3X-UI панель (если ставил на этом сервере)
sudo ufw allow 443/udp      # если VLESS+REALITY на 443
sudo ufw enable
sudo ufw status numbered
```

**Не открывай публично:**
- `5432` (PostgreSQL)
- `6379` (Redis)
- `8000` (FastAPI — доступ только через Nginx)
- `3000` (Next.js — доступ только через Nginx)

### Fail2ban (опционально)

```bash
sudo apt install -y fail2ban
sudo tee /etc/fail2ban/jail.local >/dev/null <<EOF
[sshd]
enabled = true
maxretry = 5
bantime = 1h
EOF
sudo systemctl enable --now fail2ban
```

### SSH-ключи вместо паролей

```bash
# На своей машине:
ssh-copy-id root@your-server-ip

# На сервере — выключи парольный вход:
sudo sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart ssh
```

### Обновления безопасности

```bash
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure --priority=low unattended-upgrades
```

---

## 13. Типовые проблемы

### Веб отдаёт 404 на CSS и JS

**Причина:** обновил фронт вручную через `npm run build`, но забыл скопировать `.next/static` и `public/` в `.next/standalone/`. Next standalone build **не копирует их сам** — это особенность Next.js.

**Фикс:**
```bash
cd /opt/vpnbox
sudo bash setup_web.sh          # пересоберёт и скопирует правильно
```
Или вручную — см. раздел 10.

### Веб возвращает "Internal Server Error" при сабмите форм

**Причина:** `serverActions.allowedOrigins` в `next.config.ts` не включает твой домен.

**Фикс:**
```bash
nano /opt/vpnbox/web/.env.local
# добавь:
NEXT_PUBLIC_ALLOWED_ORIGIN=yourdomain.com

sudo bash setup_web.sh
```

### Бот ругается "too many connections" или падает с asyncpg-ошибками

**Причина:** слишком маленький `max_connections` в PostgreSQL.

**Фикс:**
```bash
sudo -u postgres psql -c "SHOW max_connections;"
# если <100:
sudo -u postgres psql -c "ALTER SYSTEM SET max_connections = 200;"
sudo systemctl restart postgresql
pm2 restart all
```

### "FreeKassa / Platega: ошибка при генерации ссылки"

1. Проверь, что все ключи провайдера заполнены в `.env`.
2. `.env` читается **только при старте процесса** — после правки обязательно:
   ```bash
   pm2 reload bot-ecosystem.config.js --update-env
   ```
3. Посмотри логи: `pm2 logs vpnbox-bot | grep -i "fk\|platega\|payment"`.

### Certbot не может получить сертификат

**Возможные причины:**
- Домен не указывает на IP сервера (`dig +short yourdomain.com`).
- Порт 80 занят (nginx не остановлен): `sudo systemctl stop nginx`.
- Файрвол блокирует 80: `sudo ufw allow 80/tcp`.
- Rate limit Let's Encrypt (5 попыток/час). Подожди час или используй staging:
  ```bash
  sudo certbot certonly --standalone --staging -d yourdomain.com ...
  ```

### Nginx: "could not build server_names_hash"

```bash
sudo nano /etc/nginx/nginx.conf
# в секции http { добавь:
server_names_hash_bucket_size 128;
sudo nginx -t && sudo systemctl reload nginx
```

### Bot не отвечает, но PM2 показывает `online`

```bash
pm2 logs vpnbox-bot --lines 100
```
Типичные причины:
- Неправильный `BOT_TOKEN` — Telegram возвращает `401`, aiogram в цикле реконнектит.
- Конфликт (`409: Conflict`) — где-то ещё работает инстанс того же бота с тем же токеном. Останови его.
- `DATABASE_URL` / `REDIS_URL` невалидны — бот крашится при старте, PM2 в бесконечном цикле рестартует.

### Дубликаты VPN-юзеров после оплаты

Это было до фикса с advisory-локом. Обнови код:
```bash
cd /opt/vpnbox
git pull
pm2 reload all --update-env
```

### PM2 после ребута не поднялся

```bash
systemctl status pm2-vpnbox.service
# если disabled или нет сервиса:
pm2 startup systemd -u root --hp /root --service-name pm2-vpnbox
pm2 save
```

---

## 14. Нюансы и подводные камни

### 14.1. Порядок изменений `.env`

После правки `.env` **обязательно** делай `pm2 reload ... --update-env`. Без флага `--update-env` PM2 использует кешированные переменные окружения из момента первого запуска.

### 14.2. Next.js standalone — особенности

`output: "standalone"` в `next.config.ts` включает оптимизированный сборочный режим, когда в `.next/standalone/` лежит **минимальный Node-сервер** с только необходимыми `node_modules`. Но `public/` и `.next/static/` туда не попадают автоматически — их надо копировать. Это знаменитая засада Next.js, именно поэтому у тебя 404 были. `setup_web.sh` копирует их автоматически, ручной `npm run build` — нет.

### 14.3. Платёжки — тестовые vs боевые ключи

- **YooKassa**: в дев-кабинете есть `test_XXX` ключи — они пропускают оплату через тестовые карты. Смени на боевые перед продом.
- **FreeKassa**: `nonce` должен быть в **наносекундах** (`time.time_ns()`), иначе подпись не совпадёт. Уже исправлено в коде.
- **Platega**: поле возврата называется `returnUrl`, не `return`. Тоже исправлено.
- **Telegram Stars**: работает без ключей, но нужен включённый "платёжный аккаунт" у бота — в `@BotFather` → `/mybots` → `Payments`.

### 14.4. Таймзона сервера

Celery beat работает в UTC (`timezone="UTC"` в `celery_app.py`). Логи PM2 показывают локальную таймзону сервера. Если надо проследить событие — учитывай разницу.

Проверить:
```bash
timedatectl
```

### 14.5. Мультитенантность (несколько ботов на одном сервере)

Код уже поддерживает это через таблицу `clients`. Каждый бот-токен → отдельная запись с своими тарифами и платёжками. Но **один инстанс** (`run_bot.py`) слушает только **один** токен из `.env`. Чтобы запустить второго бота:

1. Скопируй проект в `/opt/vpnbox2`.
2. Другой `.env` с другим `BOT_TOKEN`.
3. Отдельный PM2-конфиг с `name: vpnbox2-bot` (и поменяй порты API/Web если поднимаешь веб).
4. Отдельная БД (или общая — сам выбирай).

### 14.6. Переход на webhook вместо polling (опционально)

По дефолту aiogram работает через long polling — это просто, но даёт задержку ~0.1–1с. Для webhook нужен домен с SSL. Если хочешь — это делается заменой `dp.start_polling()` на `aiohttp` + `setWebhook`. Не описываю подробно, так как polling работает хорошо до ~100k сообщений/день.

### 14.7. Размер БД и рост

```bash
sudo -u postgres psql -d vpnbox -c "SELECT pg_size_pretty(pg_database_size('vpnbox'));"
sudo -u postgres psql -d vpnbox -c "
  SELECT relname, pg_size_pretty(pg_total_relation_size(relid)) FROM pg_catalog.pg_statio_user_tables
  ORDER BY pg_total_relation_size(relid) DESC LIMIT 10;
"
```

Раз в год стоит делать `VACUUM FULL`:
```bash
sudo -u postgres psql -d vpnbox -c "VACUUM FULL ANALYZE;"
```
(на время операции БД залочится, запускай в минимум нагрузки).

### 14.8. 3X-UI — если панель на другом сервере

В `.env` на боте:
```env
VPN_SERVERS=[{"id":1,"name":"NL","panel_type":"3xui","url":"http://1.2.3.4:2053","username":"admin","password":"secret","country":"NL","inbound_id":1,"max_users":500}]
```
`url` — публичный IP панели. UFW на том сервере должен пропускать `2053` (или какой порт панели) **только** с IP бота:
```bash
# на VPN-сервере:
sudo ufw allow from <IP-бота> to any port 2053
```

### 14.9. Логи — куда смотреть в каком порядке

1. `pm2 logs vpnbox-bot` — ошибки хендлеров бота.
2. `pm2 logs vpnbox-worker` — ошибки фоновых задач (платежи, истечения).
3. `pm2 logs vpnbox-api` — ошибки HTTP-запросов от фронта.
4. `pm2 logs vpnbox-web` — ошибки SSR Next.js.
5. `sudo tail -f /var/log/nginx/error.log` — проблемы проксирования / SSL.
6. `sudo journalctl -u postgresql -n 100` — БД.

### 14.10. Миграция на другой сервер

```bash
# На старом:
cd /opt/vpnbox
pg_dump -U vpnbox vpnbox | gzip > migrate.sql.gz
tar czf migrate.tar.gz .env migrate.sql.gz

# Скопируй migrate.tar.gz на новый сервер, потом:
cd /opt/vpnbox   # уже склонирован
tar xzf /path/to/migrate.tar.gz
sudo bash setup_bot.sh              # поднимет стек
pm2 stop vpnbox-bot vpnbox-worker vpnbox-beat
sudo -u postgres psql -c "DROP DATABASE vpnbox;"
sudo -u postgres psql -c "CREATE DATABASE vpnbox OWNER vpnbox;"
gunzip -c migrate.sql.gz | psql -U vpnbox vpnbox
pm2 start all
```

Не забудь сменить A-запись DNS на новый IP и подождать распространения (TTL).

### 14.11. Обновление SSL-сертификата — проверка

```bash
sudo certbot renew --dry-run
```
Должно написать `Congratulations, all simulated renewals succeeded`. Реально обновится когда сертификату останется <30 дней — systemd-timer `certbot.timer` запускается дважды в день.

### 14.12. Что делать при 500 на `/api/*`

1. `pm2 logs vpnbox-api --lines 100` — смотри последний стектрейс.
2. Если `DatabaseError: connection refused` — PG упал, `sudo systemctl start postgresql`.
3. Если `401 Invalid or expired token` — JWT-токен протух (`JWT_EXPIRE_DAYS=30`), пользователю надо перелогиниться.
4. Если `CORS error` в браузере — проверь, что `API_CORS_ORIGINS` в `.env` равен точно `https://yourdomain.com` (без слэша в конце).

### 14.13. Rate limiting

На `/api/auth/login` и `/api/auth/register` стоит лимит `5 запросов/минута с IP` (через `slowapi`). На `/api/auth/telegram` — `20/минута`. При превышении отдаётся `429 Too Many Requests`. Если сидишь за NAT и 5 юзеров регистрируются одновременно — можно поднять лимит в `app/api/routes/auth.py` в декораторах `@limiter.limit(...)`.

### 14.14. Логи — единый формат

Все процессы (bot/api/worker/beat) пишут в stdout с единым форматом:
```
2026-04-20 15:30:42 INFO    [app.bot.handlers.start] User 12345 started
```
Уровень задаётся `LOG_LEVEL` в `.env` (`DEBUG`/`INFO`/`WARNING`/`ERROR`). PM2 logrotate ротирует логи раз в сутки, держит последние 7 файлов по 50MB, gzip'ит старое — настраивается в `setup_bot.sh`.

### 14.15. Валидация `.env`

Все entrypoint'ы (`run_bot.py`, `run_api.py`, celery worker) при старте проверяют критичные поля (`BOT_TOKEN`, `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`). Если поле пустое — процесс падает с понятной ошибкой в первую секунду, а не через 10 минут в рантайме.

### 14.16. Дебаг платежей

Включи детальные логи:
```bash
sed -i 's/^LOG_LEVEL=.*/LOG_LEVEL=DEBUG/' /opt/vpnbox/.env
pm2 reload bot-ecosystem.config.js --update-env
pm2 logs vpnbox-bot --lines 200 | grep -i "payment\|fk\|platega\|yookassa"
```
После отладки верни `INFO` — на `DEBUG` БД логи раздуваются.
