"""RailCheck API backed by API Mitra's documented PNR endpoint."""
import os
from collections import deque
from pathlib import Path
from time import monotonic
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .provider import ApiMitraProvider, ProviderError, normalize_api_mitra
from .validation import is_valid_pnr

load_dotenv()


class Passenger(BaseModel):
    number: int
    bookingStatus: str
    currentStatus: str
    coach: str | None = None
    berth: str | None = None


class PnrQuery(BaseModel):
    pnr: str


class PnrResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    train: dict[str, str]
    journeyDate: str | None = None
    from_: str = Field(alias="from")
    to: str
    departure: str | None = None
    arrival: str | None = None
    chart: str | None = None
    updatedAt: str | None = None
    passengers: list[Passenger]
    mode: str


app = FastAPI(title="RailCheck API", version="1.0.0")
ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"
DIST_DIR = ROOT / "dist"
ASSETS_DIR = DIST_DIR / "assets"
origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
provider = ApiMitraProvider(timeout_seconds=float(os.getenv("API_MITRA_TIMEOUT_SECONDS", "8")), api_key=os.getenv("API_MITRA_API_KEY"))
request_times: deque[float] = deque()


def enforce_local_rate_limit() -> None:
    """Keep this process below the provider's documented 30 train requests/minute."""
    now = monotonic()
    while request_times and now - request_times[0] >= 60:
        request_times.popleft()
    if len(request_times) >= 25:
        raise HTTPException(status_code=429, detail="Too many lookups in a short time. Wait a minute and try again.")
    request_times.append(now)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "provider": "api-mitra"}


@app.get("/", include_in_schema=False)
async def home() -> FileResponse:
    if (DIST_DIR / "index.html").is_file():
        return FileResponse(DIST_DIR / "index.html")
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/pnr", response_model=PnrResult)
async def get_pnr(query: PnrQuery) -> dict[str, Any]:
    if not is_valid_pnr(query.pnr):
        raise HTTPException(status_code=422, detail="PNR must contain exactly 10 digits.")
    enforce_local_rate_limit()
    try:
        raw = await provider.lookup(query.pnr)
        normalized = normalize_api_mitra(raw)
        return PnrResult.model_validate({**normalized, "mode": "live"}).model_dump(by_alias=True)
    except ProviderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.public_message) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="The status provider returned an unexpected response. Please try again later.") from exc


app.mount("/src", StaticFiles(directory=ROOT / "src"), name="styles")
if ASSETS_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")
