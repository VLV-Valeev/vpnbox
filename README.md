# VPNBox

Telegram-бот для продажи VPN-подписок с поддержкой нескольких платёжных систем, мультиклиентностью и админ-панелью.

## Возможности

- Автоматическая продажа VPN-подписок через Telegram-бота
- 5 платёжных систем: YooKassa, FreeKassa, Platega, CryptoCloud, Telegram Stars
- Админ-панель с аналитикой и ручной выдачей тарифов
- Мультиклиентность — название сервиса, тарифы, платёжные провайдеры и тексты настраиваются через БД
- Балансировка нагрузки между несколькими VPN-серверами
- Автоматическое продление и истечение подписок
- Пробный период (триал)
- Уведомления об истечении подписки за 24 часа

## Архитектура

```
Пользователь → Telegram Bot (aiogram) → PostgreSQL
                     ↓                       ↑
               Celery Worker ←── Redis ──── Beat
                     ↓
               VPN-панель (3X-UI)
```

| Компонент | Что делает |
|-----------|-----------|
| **Bot** | Telegram-бот на aiogram 3, long polling |
| **PostgreSQL** | Пользователи, подписки, платежи, конфигурация клиента |
| **Redis** | Брокер сообщений для Celery |
| **Celery Worker** | Фоновые задачи: проверка платежей, истечение подписок |
| **Celery Beat** | Планировщик: запускает задачи по расписанию |
| **3X-UI** | VPN-панель — управление аккаунтами пользователей |

## Быстрый старт

```bash
# Клонировать проект на сервер (Ubuntu 22.04 / 24.04)
git clone https://github.com/YOUR_USERNAME/VPNBox.git
cd VPNBox

# Настроить .env
cp .env.example .env
nano .env  # заполни BOT_TOKEN, ADMIN_ID, платёжки, VPN_SERVERS

# Запустить установку (PostgreSQL, Redis, Python, PM2, 3X-UI)
sudo bash setup.sh
```

Скрипт `setup.sh` автоматически установит все зависимости, создаст БД, виртуальное окружение и запустит бота через PM2.

Таблицы в БД создаются автоматически при первом запуске бота (`create_all`). Миграции не используются.

## Переменные окружения

| Переменная | Описание |
|---|---|
| `BOT_TOKEN` | Токен Telegram-бота |
| `BOT_USERNAME` | Username бота (без @) |
| `ADMIN_ID` | Telegram ID администраторов (через запятую) |
| `DATABASE_URL` | URL PostgreSQL (`postgresql+asyncpg://...`) |
| `REDIS_URL` | URL Redis |
| `YOOKASSA_SHOP_ID` | ID магазина ЮKassa |
| `YOOKASSA_SECRET_KEY` | Секретный ключ ЮKassa |
| `FREEKASSA_SHOP_ID` | ID магазина FreeKassa |
| `FREEKASSA_SECRET1` | Секретное слово 1 FreeKassa |
| `FREEKASSA_SECRET2` | Секретное слово 2 FreeKassa |
| `FREEKASSA_API_KEY` | API-ключ FreeKassa |
| `PLATEGA_MERCHANT_ID` | UUID мерчанта Platega |
| `PLATEGA_SECRET_KEY` | Секретный ключ Platega |
| `CRYPTOCLOUD_SHOP_ID` | ID магазина CryptoCloud |
| `CRYPTOCLOUD_API_KEY` | API-ключ CryptoCloud |
| `VPN_SERVERS` | JSON-массив серверов (см. `.env.example`) |
| `LOG_LEVEL` | Уровень логирования (`DEBUG`, `INFO`, …) |

## Мультиклиентность

При первом запуске бот создаёт запись `Client` в БД с дефолтными настройками из `.env` и `config.py`. После этого конфигурация живёт в базе данных:

- **service_name** — название сервиса (отображается в приветствии, админке и т.д.)
- **Роли пользователей** — `user` / `admin` (в таблице `users`)
- **Тарифные планы** (таблица `client_plans`) — slug, название, длительность, трафик, цена
- **Платёжные провайдеры** (таблица `client_payment_providers`) — какие включены, credentials в JSON
- **VPN-приложение** — ссылки на Android/iOS/Desktop, какие платформы показывать
- **Документы** — URL пользовательского соглашения и политики конфиденциальности
- **Поддержка** — ссылка на контакт поддержки

Изменения в БД применяются при следующем запуске бота.

## Команды бота

| Команда | Описание |
|---|---|
| `/start` | Главное меню |
| `/info` | Пользовательское соглашение и политика конфиденциальности |
| `/admin` | Панель администратора (только для администраторов) |

## Админ-панель (`/admin`)

Доступна пользователям с ролью `admin`. Первый админ назначается из `ADMIN_ID` в `.env`, далее админы добавляются через саму панель.

- **Аналитика** — пользователи, подписки, платежи, выручка
- **Выдача тарифа** — ввод Telegram ID → выбор тарифа → мгновенная активация
- **Настройки сервиса** — название, контакт поддержки, ссылки на документы
- **Управление тарифами** — название, цена, трафик, длительность, вкл/выкл каждого тарифа
- **VPN-приложение** — название (Hiddify, V2rayTun и т.д.), ссылки скачивания, вкл/выкл платформ (Android/iOS/Desktop)
- **Администраторы** — список, добавление, снятие прав

## Платёжные системы

Бот поддерживает несколько платёжных систем одновременно. При оплате пользователь сам выбирает способ.

Каждый провайдер реализует интерфейс `BasePaymentProvider` (`app/services/payments/base.py`):

```
BasePaymentProvider
├── create_payment(amount, order_id, description) → PaymentResult
└── check_payment(provider_payment_id) → PaymentStatusResult
```

### Поддерживаемые провайдеры

| Провайдер | Аутентификация | Особенности |
|-----------|---------------|-------------|
| **YooKassa** | Shop ID + Secret Key | Redirect-flow, ThreadPoolExecutor для sync SDK |
| **FreeKassa** | Shop ID + Secret1/2 + API Key | HMAC-SHA256 подпись |
| **Platega** | Merchant ID + Secret Key | Заголовки X-MerchantId + X-Secret |
| **CryptoCloud** | Shop ID + API Key | Инвойс в RUB, пользователь выбирает крипту |
| **Telegram Stars** | Не нужны, всегда включён | Нативный send_invoice, курс настраивается |

### Проверка оплаты (polling)

- **Быстрый** (asyncio, каждые 3 сек, до 15 мин) — запускается сразу после создания платежа, обновляет сообщение пользователю
- **Фоновый** (Celery, каждые 30 сек) — fallback на случай перезапуска бота

### Добавление нового провайдера

1. Создай `app/services/payments/your_provider.py`, реализуй `BasePaymentProvider`
2. Зарегистрируй в `factory.py` (`get_provider`) и добавь в `PROVIDER_LABELS`

## Фоновые задачи (Celery)

| Задача | Интервал | Что делает |
|--------|----------|-----------|
| `check_pending_payments` | каждые 30 сек | Проверяет платежи и активирует подписки |
| `expire_subscriptions` | каждые 60 сек | Деактивирует истёкшие подписки, уведомляет пользователей |
| `send_expiry_reminders` | каждые 30 мин | Напоминает об истечении за 24 часа |
| `healthcheck_vpn_servers` | каждые 5 мин | Проверяет доступность VPN-панелей |
| `cleanup_stale_payments` | раз в сутки (3:00 UTC) | Отменяет неоплаченные платежи старше 24 часов |

## Структура проекта

```
app/
├── bot/
│   ├── main.py              # Инициализация бота и диспетчера
│   ├── middlewares.py        # DbSession, Error, Admin middleware
│   ├── texts.py              # Тексты бота (брендинг из БД)
│   └── handlers/
│       ├── start.py          # /start, /info
│       ├── admin.py          # /admin — аналитика, выдача тарифов
│       ├── trial.py          # Активация триала
│       ├── subscription.py   # Выбор тарифа и способа оплаты
│       ├── payment.py        # Оплата через внешние провайдеры
│       ├── stars_payment.py  # Оплата через Telegram Stars
│       └── profile.py        # Профиль, подключение, трафик
├── db/
│   ├── engine.py             # AsyncEngine, async_session
│   ├── models.py             # SQLAlchemy-модели
│   └── repo.py               # Репозитории (User, Sub, Payment)
├── services/
│   ├── client_service.py     # Загрузка и кэш конфигурации клиента
│   ├── subscription_service.py # Подписки, платежи, продления
│   ├── vpn_service.py        # Управление VPN-аккаунтами
│   └── payments/
│       ├── base.py           # BasePaymentProvider (ABC)
│       ├── factory.py        # Фабрика провайдеров
│       ├── yookassa_provider.py
│       ├── freekassa_provider.py
│       ├── platega_provider.py
│       └── cryptocloud_provider.py
├── vpn/
│   ├── panel_factory.py      # Создание клиента панели по типу
│   ├── panel_manager.py      # Балансировка, CRUD пользователей
│   └── threexui.py           # Клиент API 3X-UI (VLESS)
├── worker/
│   ├── celery_app.py         # Конфигурация Celery + Beat schedule
│   └── tasks.py              # Реализация фоновых задач
└── config.py                 # Settings (pydantic), дефолтные PLANS
```

## Документация

- [Руководство по деплою](DEPLOY.md) — пошаговая инструкция от покупки сервера до запуска
