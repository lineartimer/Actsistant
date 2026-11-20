from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from fastapi import FastAPI
import uvicorn

from api.ask import ask_router
from database.database import initialize_database


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await initialize_database()
    yield

app = FastAPI(lifespan=lifespan)
app.include_router(ask_router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=5005, reload=True)
