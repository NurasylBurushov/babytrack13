import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from config import settings
from database import create_tables
from router_auth import router as auth_router
from router_nannies import router as nannies_router
from router_bookings import router as bookings_router
from router_chat import router as chat_router
from router_users import router as users_router


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
                print("⚠️ Сервер запущен без БД — проверьте DATABASE_URL")
    yield


app = FastAPI(
    title="BabyTrack API",
    description="Бэкенд для приложения подбора нянь",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router,     prefix="/api")
app.include_router(nannies_router,  prefix="/api")
app.include_router(bookings_router, prefix="/api")
app.include_router(chat_router,     prefix="/api")
app.include_router(users_router,    prefix="/api")


@app.get("/", tags=["Health"])
async def root():
    return {"app": settings.APP_NAME, "version": "1.0.0", "status": "ok", "docs": "/docs"}


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
