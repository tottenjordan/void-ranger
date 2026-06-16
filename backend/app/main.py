from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import physics, stars

app = FastAPI(title="ChronoCloud API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(physics.router)
app.include_router(stars.router)


@app.get("/")
async def root():
    return {"status": "ok"}
