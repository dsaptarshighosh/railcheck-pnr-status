# RailCheck

RailCheck is an independent PNR status interface. It is not affiliated with Indian Railways or IRCTC.

## Live PNR provider

The backend calls API Mitra's documented `GET https://api.apimitra.in/train/pnr?number=<10-digit PNR>` endpoint. A live request using the PNR supplied in this task reached the endpoint and returned `api_key_required`, so no reservation data was returned. The integration requires `API_MITRA_API_KEY` on the backend and sends it only in the `x-api-key` header. PNR responses are not cached or logged.

The adapter and normalizer are in `api/provider.py`; incomplete or unexpected payloads fail rather than producing invented values. The documented response includes train name/number, route, journey date, chart-prepared status and passenger-wise booking/current statuses. Coach and berth are parsed from provider-returned confirmed status text when present. Departure, arrival and update time appear only when returned. The backend has an 8-second timeout and caps each process at 25 lookups/minute under the provider's documented 30 requests/minute `/train*` limit.

API Mitra's PNR docs publish an endpoint and sample response, but that example omits authentication. The live endpoint required an API key. Its site says keys can be obtained by creating an account. Public pages are inconsistent about no-key/free access versus account keys and free allowances; the PNR-specific price/quota and upstream railway data rights are not clearly stated. Check the current plan, privacy notice and data-use terms before production deployment. IRCTC's policy grants direct PNR Enquiry Service integration to approved B2C PSPs and restricts onward API sharing.

## Run locally

Requirements: Node.js 20+ and Python 3.10+.

```powershell
npm install
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn api.main:app --reload --port 8000
```

Put your API Mitra key in `.env` before starting Uvicorn. Open `http://localhost:8000/` for the dependency-free local page served by FastAPI. For React/Vite development, run `npm run dev` in a second terminal and open `http://localhost:5173/`; Vite proxies `/api` to FastAPI.

## Environment

Copy `.env.example` to `.env`. Set `API_MITRA_API_KEY` to the key obtained by creating an account at [API Mitra](https://www.apimitra.in/). The backend loads `.env`; the key is never placed in Vite variables or frontend code. Set `CORS_ORIGINS` to comma-separated exact frontend origins and optionally change `API_MITRA_TIMEOUT_SECONDS`.

## Verification

`npm run build` checks TypeScript and creates the production frontend build. Start the API with Uvicorn to use the backend. `/api/health` reports the selected provider, not upstream availability.

## Authorization and source notes

- IRCTC B2C PSP Policy, sections 22.1–22.10: <https://contents.irctc.co.in/en/B2C_PSP_Policy_other_than_Startup_MSME.pdf>
- Official Indian Railways PNR enquiry: <https://www.indianrail.gov.in/enquiry/PNR/PnrEnquiry.jsp?locale=en>
- API Mitra PNR endpoint and response schema: <https://docs.apimitra.in/trains/pnr/>
- API Mitra rate limits: <https://docs.apimitra.in/reference/rate-limits/>
- API Mitra overview: <https://www.apimitra.in/>
