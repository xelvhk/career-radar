"""Local-only HTTP API and static browser surface for Opportunity Inbox."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import urlsplit

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .opportunity_reporting import opportunity_to_dict
from .opportunity_service import OpportunityImporter
from .opportunity_store import OpportunityStore
from .hh_source import HeadHunterAdapter, JsonTransport, SourceBlockedError, load_hh_config
from .scan_service import ScanService


PANEL_VERSION = 1
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
SECURITY_HEADERS = {
    "Cache-Control": "no-store",
    "Content-Security-Policy": (
        "default-src 'self'; base-uri 'none'; connect-src 'self'; "
        "font-src 'self'; form-action 'self'; frame-ancestors 'none'; "
        "img-src 'self' data:; object-src 'none'; script-src 'self'; "
        "style-src 'self'"
    ),
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}


class ImportRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    text: str
    source: str = Field(default="manual", min_length=1, max_length=50)
    source_vacancy_id: str | None = Field(
        default=None, alias="sourceVacancyId", max_length=300
    )
    source_url: str | None = Field(default=None, alias="sourceUrl", max_length=2048)
    retrieved_at: str | None = Field(default=None, alias="retrievedAt", max_length=64)


class StatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["new", "shortlisted", "dismissed"]


class ScanRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    profile_id: str = Field(alias="profileId", min_length=1, max_length=100)


def create_app(
    *,
    db_path: Path | str,
    root: Path,
    profile_path: Path | None = None,
    hh_config_path: Path | None = None,
    hh_transport: JsonTransport | None = None,
) -> FastAPI:
    """Create a loopback-only panel application around one local store."""
    web_root = Path(__file__).resolve().parent / "web"
    store = OpportunityStore(db_path)
    importer = OpportunityImporter(root, db_path, profile=profile_path)
    try:
        hh_config = load_hh_config(hh_config_path or root / "hh_source.local.yaml")
        hh_adapter = HeadHunterAdapter(hh_config, transport=hh_transport)
        hh_blocked_message = None
    except SourceBlockedError as error:
        hh_adapter = None
        hh_blocked_message = str(error)
    scanner = ScanService(
        root, importer, hh_adapter, blocked_message=hh_blocked_message
    )
    app = FastAPI(
        title="Career Radar Local Panel",
        version=str(PANEL_VERSION),
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.middleware("http")
    async def protect_local_boundary(request: Request, call_next):  # type: ignore[no-untyped-def]
        host = _hostname(request.headers.get("host", ""))
        if host not in LOOPBACK_HOSTS:
            response = _error(400, "INVALID_HOST", "Local host is required")
        elif request.method not in {"GET", "HEAD", "OPTIONS"} and not _same_origin(
            request
        ):
            response = _error(403, "FORBIDDEN", "Local request verification failed")
        else:
            response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers[name] = value
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(  # type: ignore[no-untyped-def]
        _request: Request, _error_value: RequestValidationError
    ) -> JSONResponse:
        return _error(422, "VALIDATION_ERROR", "Invalid request")

    @app.exception_handler(ValueError)
    async def value_error(  # type: ignore[no-untyped-def]
        _request: Request, error: ValueError
    ) -> JSONResponse:
        message = str(error)
        if message == "opportunity was not found":
            return _error(404, "NOT_FOUND", "Opportunity was not found")
        if "database" in message or "schema version" in message:
            return _error(500, "STORAGE_ERROR", "Local opportunity storage is unavailable")
        return _error(400, "INVALID_INPUT", message)

    @app.exception_handler(Exception)
    async def unexpected_error(  # type: ignore[no-untyped-def]
        _request: Request, _error_value: Exception
    ) -> JSONResponse:
        return _error(500, "INTERNAL_ERROR", "The local panel could not complete the request")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(web_root / "index.html", media_type="text/html")

    @app.get("/app.css", include_in_schema=False)
    def stylesheet() -> FileResponse:
        return FileResponse(web_root / "app.css", media_type="text/css")

    @app.get("/app.js", include_in_schema=False)
    def javascript() -> FileResponse:
        return FileResponse(web_root / "app.js", media_type="text/javascript")

    @app.get("/api/opportunities")
    def list_opportunities(
        recommendation: Literal["APPLY", "REVIEW", "SKIP"] | None = None,
        status: Literal["new", "shortlisted", "dismissed"] | None = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 100,
    ) -> dict[str, object]:
        opportunities = store.list(
            recommendation=recommendation, status=status, limit=limit
        )
        return {
            "panelVersion": PANEL_VERSION,
            "opportunityCount": len(opportunities),
            "opportunities": [
                opportunity_to_dict(item, include_match_report=False)
                for item in opportunities
            ],
        }

    @app.get("/api/sources")
    def list_sources() -> dict[str, object]:
        configured = scanner.adapter is not None
        return {
            "panelVersion": PANEL_VERSION,
            "profiles": list(scanner.profiles),
            "sources": [
                {
                    "source": "hh",
                    "status": "ready" if configured else "blocked",
                    "message": (
                        "HeadHunter is ready for a manual scan"
                        if configured
                        else scanner.blocked_message
                    ),
                }
            ],
        }

    @app.post("/api/scans")
    def scan_sources(payload: ScanRequest) -> dict[str, object]:
        return {"panelVersion": PANEL_VERSION, "scan": scanner.scan(payload.profile_id).to_dict()}

    @app.get("/api/opportunities/{vacancy_id}")
    def get_opportunity(vacancy_id: str) -> dict[str, object]:
        return {
            "panelVersion": PANEL_VERSION,
            "opportunity": opportunity_to_dict(
                store.get(vacancy_id), include_match_report=True
            ),
        }

    @app.post("/api/opportunities", status_code=201)
    def import_opportunity(payload: ImportRequest) -> dict[str, object]:
        result = importer.import_text(
            payload.text,
            source=payload.source,
            source_vacancy_id=payload.source_vacancy_id,
            source_url=payload.source_url,
            retrieved_at=payload.retrieved_at,
        )
        return {
            "panelVersion": PANEL_VERSION,
            "created": result.created,
            "stale": result.stale,
            "opportunity": opportunity_to_dict(
                result.opportunity, include_match_report=True
            ),
        }

    @app.patch("/api/opportunities/{vacancy_id}")
    def set_opportunity_status(
        vacancy_id: str, payload: StatusRequest
    ) -> dict[str, object]:
        return {
            "panelVersion": PANEL_VERSION,
            "opportunity": opportunity_to_dict(
                store.set_status(vacancy_id, payload.status),
                include_match_report=True,
            ),
        }

    return app


def _hostname(host_header: str) -> str | None:
    try:
        return urlsplit(f"//{host_header}").hostname
    except ValueError:
        return None


def _same_origin(request: Request) -> bool:
    if request.headers.get("x-career-radar-request") != "1":
        return False
    origin = request.headers.get("origin")
    if origin is None:
        return False
    expected = f"{request.url.scheme}://{request.headers.get('host', '')}"
    return origin == expected


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )
