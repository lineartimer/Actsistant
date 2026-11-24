from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from fastapi import FastAPI
import uvicorn

from api.ask import ask_router
from api.health import health_router
from database.database import close_database, initialize_database


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await initialize_database()
    yield
    close_database()

app = FastAPI(lifespan=lifespan)
app.include_router(ask_router)
app.include_router(health_router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=5005, reload=True)
