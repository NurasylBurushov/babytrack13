import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from database import create_tables
from router_auth import router as auth_router
from router_users import router as users_router
from router_nannies import router as nannies_router
from router_chat import router as chat_router
from router_market import router as market_router
from router_tracking import router as tracking_router
import time

@asynccontextmanager
async def lifespan(app: FastAPI):
    for attempt in range(5):
        try:
            await create_tables()
            print("✅ База данных готова")
            break
        except Exception as e:
            print(f"⏳ БД не готова (попытка {attempt+1}/5): {e}")
            if attempt < 4:
                import asyncio
                await asyncio.sleep(3)
            else:
                print("⚠️ Сервер запущен без БД")
    yield

app = FastAPI(
    title="SabiTrack API",
    description="Бэкенд для приложения SabiTrack",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting (простая защита)
request_counts = {}

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host
    current_time = time.time()
    
    if client_ip not in request_counts:
        request_counts[client_ip] = []
    
    # Оставляем только запросы за последние 60 секунд
    request_counts[client_ip] = [
        t for t in request_counts[client_ip] 
        if current_time - t < 60
    ]
    
    # Максимум 100 запросов в минуту
    if len(request_counts[client_ip]) >= 100:
        return JSONResponse(
            status_code=429,
            content={"detail": "Слишком много запросов. Подождите минуту."}
        )
    
    request_counts[client_ip].append(current_time)
    response = await call_next(request)
    return response

# Роуты
app.include_router(auth_router,     prefix="/api")
app.include_router(users_router,    prefix="/api")
app.include_router(nannies_router,  prefix="/api")
app.include_router(chat_router,     prefix="/api")
app.include_router(market_router,   prefix="/api")
app.include_router(tracking_router, prefix="/api")

@app.get("/", tags=["Health"])
async def root():
    return {"app": "SabiTrack API", "version": "2.0.0", "status": "ok"}

@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
