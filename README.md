# BabyTrack Backend — Инструкция по деплою

## Стек
- **FastAPI** + Python 3.11
- **PostgreSQL** (через Railway)
- **WebSocket** для чата в реальном времени
- **SMS**: SMSC.kz (Казахстан) или SMS.ru

---

## 🚀 Деплой на Railway (бесплатно)

### 1. Создайте аккаунт
Зайдите на https://railway.app и войдите через GitHub.

### 2. Новый проект
- New Project → Deploy from GitHub repo
- Выберите ваш репозиторий с бэкендом

### 3. Добавьте PostgreSQL
- В проекте нажмите "+ New" → Database → PostgreSQL
- Railway автоматически добавит `DATABASE_URL` в переменные

### 4. Настройте переменные окружения
В разделе Variables добавьте:
```
SECRET_KEY=ваш-длинный-секретный-ключ-минимум-32-символа
DEBUG=false
SMSC_LOGIN=ваш_логин_smsc
SMSC_PASSWORD=ваш_пароль_smsc
SMS_PROVIDER=smsc
```

### 5. Готово!
Railway автоматически прочитает `railway.toml` и запустит сервер.
Ваш URL будет вида: `https://babytrack-production.up.railway.app`

---

## 💻 Локальная разработка

```bash
# 1. Клонируйте репозиторий
cd babytrack-backend

# 2. Создайте виртуальное окружение
python -m venv venv
source venv/bin/activate  # Mac/Linux
# или: venv\Scripts\activate  # Windows

# 3. Установите зависимости
pip install -r requirements.txt

# 4. Настройте .env
cp .env.example .env
# Отредактируйте .env — добавьте DATABASE_URL

# 5. Запустите PostgreSQL (через Docker)
docker run -d \
  --name babytrack-db \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=babytrack \
  -p 5432:5432 \
  postgres:15

# 6. Запустите сервер
uvicorn main:app --reload --port 8000
```

Откройте http://localhost:8000/docs — интерактивная документация API.

---

## 📱 Подключение iOS приложения

1. Скопируйте `NetworkManager.swift` в Xcode проект
2. Замените `API.baseURL` на ваш Railway URL:
   ```swift
   static let baseURL = "https://your-app.railway.app"
   ```
3. В `HomeView.swift` замените `SampleData.nannies` на:
   ```swift
   @StateObject var vm = NannyListViewModel()
   // ...
   .task { await vm.load() }
   ```

---

## 📋 API Эндпоинты

| Метод | URL | Описание |
|-------|-----|----------|
| POST | /auth/send-otp | Отправить SMS код |
| POST | /auth/verify-otp | Подтвердить код → JWT токен |
| GET | /nannies | Список нянь с фильтрами |
| GET | /nannies/{id} | Профиль няни |
| POST | /nannies/{id}/favorite | Избранное |
| POST | /bookings | Создать запись |
| GET | /bookings | Мои записи |
| PATCH | /bookings/{id}/status | Изменить статус |
| POST | /bookings/{id}/review | Оставить отзыв |
| GET | /chats | Мои чаты |
| GET | /chats/{id}/messages | История чата |
| WS | /chats/{id}/ws?token=JWT | WebSocket чат |
| GET | /users/me | Мой профиль |
| PATCH | /users/me | Обновить профиль |
| GET | /users/me/children | Мои дети |
| POST | /users/me/children | Добавить ребёнка |

---

## 🔐 Авторизация (SMS flow)

```
1. POST /auth/send-otp  {"phone": "+77011234567"}
   → Отправляет SMS с кодом

2. POST /auth/verify-otp  {"phone": "+77011234567", "code": "123456"}
   → Возвращает {"access_token": "eyJ..."}

3. Все защищённые запросы:
   Header: Authorization: Bearer eyJ...
```

В режиме DEBUG (`.env` → `DEBUG=true`) код всегда `123456`.

---

## 💰 Стоимость

| Сервис | Цена |
|--------|------|
| Railway (сервер) | Бесплатно до $5/месяц |
| Railway PostgreSQL | Бесплатно до 500 МБ |
| SMSC.kz | ~3-5 тенге за SMS |
| Домен (опционально) | ~3000 тенге/год |
