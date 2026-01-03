from fastapi import FastAPI

from certus_transform.routers import health, ingest, privacy, promotion, uploads, verification

app = FastAPI(
    title="Certus Data Prep Service",
    version="0.1.0",
    description="Customer-operated service for managing raw/quarantine/golden workflows.",
)

app.include_router(health.router)
app.include_router(uploads.router)
app.include_router(privacy.router)
app.include_router(promotion.router)
app.include_router(ingest.router)
app.include_router(verification.router)
