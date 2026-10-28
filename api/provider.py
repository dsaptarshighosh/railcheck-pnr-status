"""Adapter for API Mitra's documented Indian Railways PNR endpoint."""
import asyncio
import json
import os
import re
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_URL = "https://api.apimitra.in/train/pnr"


class ProviderError(Exception):
    def __init__(self, status_code: int, public_message: str):
        super().__init__(public_message)
        self.status_code = status_code
        self.public_message = public_message


class ApiMitraProvider:
    """Calls GET /train/pnr?number=<10-digit PNR> as documented by API Mitra."""

    def __init__(self, timeout_seconds: float = 8, api_key: str | None = None):
        self.timeout_seconds = timeout_seconds
        self.api_key = api_key or os.getenv("API_MITRA_API_KEY", "").strip()

    async def lookup(self, pnr: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._lookup_sync, pnr)

    def _lookup_sync(self, pnr: str) -> dict[str, Any]:
        if not self.api_key:
            raise ProviderError(503, "Live status lookup is not configured. Add API_MITRA_API_KEY to the backend environment.")
        url = f"{BASE_URL}?{urlencode({'number': pnr})}"
        request = Request(url, headers={"Accept": "application/json", "User-Agent": "RailCheck/1.0", "x-api-key": self.api_key})
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read(1_000_001)
                if len(body) > 1_000_000:
                    raise ProviderError(502, "The status provider returned an oversized response. Please try again later.")
                payload = json.loads(body.decode("utf-8"))
        except HTTPError as exc:
            if exc.code in (400, 404):
                raise ProviderError(404, "No reservation status was returned. Check the PNR and try again.") from exc
            if exc.code == 403:
                try:
                    error_payload = json.loads(exc.read().decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    error_payload = {}
                if isinstance(error_payload, dict) and error_payload.get("code") == "service_not_activated":
                    raise ProviderError(403, "PNR lookup is not activated for your API Mitra account. Open API Access in API Mitra and enable the Train service, then try again.") from exc
                raise ProviderError(403, "API Mitra denied Train/PNR access for this account. Check API Access in your API Mitra portal.") from exc
            if exc.code == 401:
                raise ProviderError(502, "API Mitra did not accept the configured API key. Check that it is active and saved correctly in the backend .env file.") from exc
                raise ProviderError(502, "API Mitra denied this PNR request. Check that API_MITRA_API_KEY is active and that your account can access PNR status.") from exc
            if exc.code == 429:
                raise ProviderError(429, "The status provider is receiving too many requests. Please wait a minute and try again.") from exc
            raise ProviderError(502, "The status provider is temporarily unavailable. Please try again shortly.") from exc
        except TimeoutError as exc:
            raise ProviderError(504, "The status enquiry timed out. Please try again.") from exc
        except URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise ProviderError(504, "The status enquiry timed out. Please try again.") from exc
            raise ProviderError(502, "We could not reach the status provider. Check your connection and try again.") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderError(502, "The status provider returned an unreadable response. Please try again later.") from exc

        if isinstance(payload, dict) and payload.get("code") == "api_key_required":
            raise ProviderError(502, "The provider requires an API key. Check API_MITRA_API_KEY in the backend environment.")
        if isinstance(payload, dict) and payload.get("code") in ("invalid_api_key", "api_key_invalid"):
            raise ProviderError(502, "The provider rejected its API key. Check API_MITRA_API_KEY in the backend environment.")
        if not isinstance(payload, dict) or payload.get("status") not in ("ok", "success"):
            message = str(payload.get("message", "")) if isinstance(payload, dict) else ""
            if any(word in message.lower() for word in ("invalid", "not found", "no record")):
                raise ProviderError(404, "No reservation status was returned. Check the PNR and try again.")
            raise ProviderError(502, "The status provider returned an unexpected response. Please try again later.")
        return payload


def _station_name(value: Any) -> str | None:
    if isinstance(value, str):
        return value or None
    if isinstance(value, dict):
        name, code = value.get("name"), value.get("code")
        if name and code:
            return f"{name} ({code})"
        return name or code
    return None


def _display_date(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    for pattern in ("%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, pattern).strftime("%d %b %Y")
        except ValueError:
            pass
    return value


def normalize_api_mitra(raw: dict[str, Any]) -> dict[str, Any]:
    """Map documented fields into RailCheck's UI contract; don't invent fields."""
    if raw.get("status") not in ("ok", "success"):
        raise ValueError("Provider response was not successful")
    train_number, train_name = raw.get("train_number"), raw.get("train_name")
    origin, destination = _station_name(raw.get("from")), _station_name(raw.get("to"))
    source_passengers = raw.get("passengers")
    if not train_number or not train_name or not origin or not destination or not isinstance(source_passengers, list):
        raise ValueError("Provider response is missing required journey or passenger fields")
    passengers = []
    for index, item in enumerate(source_passengers, start=1):
        if not isinstance(item, dict):
            raise ValueError("Provider passenger row is malformed")
        booking, current = item.get("booking_status"), item.get("current_status")
        if not isinstance(booking, str) or not isinstance(current, str):
            raise ValueError("Provider passenger status is missing")
        row: dict[str, Any] = {"number": item.get("number", index), "bookingStatus": booking, "currentStatus": current}
        coach = item.get("coach")
        berth = item.get("berth", item.get("berth_number"))
        if current.startswith("CNF"):
            seat_source = current if re.search(r"\b[A-Z]{1,2}\d{1,2}\s+\d{1,3}\b", current) else booking
            seat_match = re.search(r"\b([A-Z]{1,2}\d{1,2})\s+(\d{1,3})\b", seat_source)
            if seat_match:
                coach = coach or seat_match.group(1)
                berth = berth or seat_match.group(2)
        if coach is not None:
            row["coach"] = str(coach)
        if berth is not None:
            row["berth"] = str(berth)
        passengers.append(row)
    if not passengers:
        raise ValueError("Provider returned no passengers")
    chart = raw.get("chart_prepared")
    return {
        "train": {"number": str(train_number), "name": str(train_name)},
        "journeyDate": _display_date(raw.get("travel_date")),
        "from": origin,
        "to": destination,
        "departure": raw.get("departure") if isinstance(raw.get("departure"), str) else None,
        "arrival": raw.get("arrival") if isinstance(raw.get("arrival"), str) else None,
        "chart": ("Prepared" if chart else "Not prepared") if isinstance(chart, bool) else (str(chart) if chart else None),
        "updatedAt": raw.get("updated_at") if isinstance(raw.get("updated_at"), str) else None,
        "passengers": passengers,
    }
