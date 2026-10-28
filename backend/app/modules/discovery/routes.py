from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from app.modules.discovery.repository import DiscoveryRepository
from app.modules.discovery.schemas import (
    CandidateRead,
    CandidateReview,
    RouteCandidate,
    RunRead,
    SourceCreate,
    SourceRead,
)
from app.modules.discovery.service import DiscoveryService
from app.modules.identity.routes import Actor, Service, Writer

router = APIRouter(
    prefix="/api/workspaces/{workspace}/brands/{brand}/discovery", tags=["discovery"]
)


def service(workspace: UUID, brand: UUID, identity: Service, user: Actor) -> DiscoveryService:
    svc = DiscoveryService(DiscoveryRepository(identity.repo.db, workspace, brand), identity, user)
    svc.authorize()
    return svc


Discovery = Annotated[DiscoveryService, Depends(service)]
Offset = Annotated[int, Query(ge=0)]


@router.get("/sources", response_model=list[SourceRead])
def sources(svc: Discovery) -> list[SourceRead]:
    return [SourceRead.model_validate(row) for row in svc.repo.sources()]


@router.post("/sources", response_model=SourceRead, status_code=201)
def create_source(data: SourceCreate, user: Writer, svc: Discovery) -> SourceRead:
    return SourceRead.model_validate(svc.create_source(data))


@router.post("/sources/{source}/toggle", response_model=SourceRead)
def toggle(source: UUID, user: Writer, svc: Discovery) -> SourceRead:
    svc.authorize(True)
    svc.repo.lock()
    row = svc.source(source)
    row.enabled = not row.enabled
    svc.repo.save_source(row)
    svc.identity.record(
        user, "discovery.source_toggled", row.id, svc.repo.workspace, svc.repo.brand
    )
    return SourceRead.model_validate(row)


@router.post("/sources/{source}/runs", response_model=RunRead, status_code=201)
def run(source: UUID, user: Writer, svc: Discovery, request: Request) -> RunRead:
    return RunRead.model_validate(svc.run(source, request.app.state.fetch_feed))


@router.get("/runs", response_model=list[RunRead])
def runs(svc: Discovery, offset: Offset = 0) -> list[RunRead]:
    return [RunRead.model_validate(row) for row in svc.repo.runs(offset)]


@router.get("/candidates", response_model=list[CandidateRead])
def candidates(
    svc: Discovery,
    status: Literal["INBOX", "APPROVED", "REJECTED"] | None = None,
    search: str = Query(default="", max_length=120),
    topic: str = Query(default="", max_length=100),
    order: Literal["score", "newest"] = "score",
    offset: Offset = 0,
) -> list[CandidateRead]:
    return [svc.read(row) for row in svc.repo.candidates(status, search, topic, order, offset)]


@router.patch("/candidates/{candidate}", response_model=CandidateRead)
def review(candidate: UUID, data: CandidateReview, user: Writer, svc: Discovery) -> CandidateRead:
    return svc.review(candidate, data)


@router.post("/candidates/{candidate}/route", response_model=CandidateRead)
def route(candidate: UUID, data: RouteCandidate, user: Writer, svc: Discovery) -> CandidateRead:
    target = DiscoveryService(
        DiscoveryRepository(svc.repo.db, svc.repo.workspace, data.target_brand_id),
        svc.identity,
        user,
    )
    return svc.route(candidate, target)
