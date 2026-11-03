from fastapi import APIRouter, Depends, Response

from routers import auth, health, jobs, orgs, scans, usage

API_VERSION = "v1"


def _add_routes(router: APIRouter) -> APIRouter:
    router.include_router(health.router)
    router.include_router(scans.router)
    router.include_router(jobs.router)
    router.include_router(usage.router)
    router.include_router(auth.router)
    router.include_router(orgs.router)
    return router


def _mark_legacy(response: Response) -> None:
    """Tell clients still on the unversioned paths where to move"""
    response.headers["Deprecation"] = "true"
    response.headers["Link"] = f'</api/{API_VERSION}>; rel="successor-version"'


# The supported API. Breaking changes go into a new prefix (/api/v2) instead of changing this one.
api_v1_router = _add_routes(APIRouter(prefix=f"/api/{API_VERSION}"))

# The original unversioned paths keep working for existing clients, flagged as deprecated and
# hidden from the API docs.
legacy_router = _add_routes(
    APIRouter(prefix="/api", dependencies=[Depends(_mark_legacy)], include_in_schema=False)
)
