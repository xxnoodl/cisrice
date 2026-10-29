from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from app.modules.acquisition.repository import AcquisitionRepository
from app.modules.acquisition.schemas import (
    AcquisitionRequest,
    AssetRead,
    JobRead,
    ReuseAsset,
    RightsCreate,
    RightsRead,
)
from app.modules.acquisition.service import AcquisitionService
from app.modules.acquisition.storage import MediaError
from app.modules.identity.routes import Actor, Service, Writer

router = APIRouter(prefix="/api/workspaces/{workspace}/brands/{brand}/media", tags=["acquisition"])
Offset = Annotated[int, Query(ge=0)]


def service(workspace: UUID, brand: UUID, identity: Service, actor: Actor) -> AcquisitionService:
    svc = AcquisitionService(
        AcquisitionRepository(identity.repo.db, workspace, brand),
        identity,
        actor,
        identity.settings,
    )
    svc.authorize()
    return svc


Acquisition = Annotated[AcquisitionService, Depends(service)]


@router.get("/rights", response_model=list[RightsRead])
def rights(svc: Acquisition, offset: Offset = 0) -> list[RightsRead]:
    return [RightsRead.model_validate(r) for r in svc.repo.list_rights(offset)]


@router.post("/rights", response_model=RightsRead, status_code=201)
def approve(data: RightsCreate, actor: Writer, svc: Acquisition) -> RightsRead:
    return RightsRead.model_validate(svc.approve_rights(data))


@router.post("/rights/{rights}/revoke", response_model=RightsRead)
def revoke(rights: UUID, actor: Writer, svc: Acquisition) -> RightsRead:
    return RightsRead.model_validate(svc.revoke(rights))


@router.post("/requests", response_model=JobRead, status_code=202)
def acquire(data: AcquisitionRequest, actor: Writer, svc: Acquisition) -> JobRead:
    return JobRead.model_validate(svc.acquire(data))


@router.get("/jobs", response_model=list[JobRead])
def jobs(svc: Acquisition, offset: Offset = 0) -> list[JobRead]:
    return [JobRead.model_validate(r) for r in svc.jobs().list_jobs(offset)]


@router.post("/jobs/{job}/cancel", response_model=JobRead)
def cancel(job: UUID, actor: Writer, svc: Acquisition) -> JobRead:
    return JobRead.model_validate(svc.jobs().cancel(job))


@router.get("/assets", response_model=list[AssetRead])
def assets(svc: Acquisition, offset: Offset = 0) -> list[AssetRead]:
    return [svc.read(row) for row in svc.repo.assets(offset)]


@router.get("/assets/{asset}/file")
def media_file(asset: UUID, svc: Acquisition) -> FileResponse:
    row, obj = svc.asset(asset)
    svc.rights(row.rights_id, approved=True)
    try:
        path = svc.storage().canonical(obj.sha256, obj.extension)
        if not path.is_file() or path.is_symlink() or path.stat().st_size != obj.size_bytes:
            raise MediaError("media_unavailable")
    except (MediaError, OSError):
        raise HTTPException(409, "Media object is unavailable; inspect storage health") from None
    return FileResponse(path, media_type=obj.mime, filename=row.export_name)


@router.post("/reuse", response_model=AssetRead, status_code=201)
def reuse(data: ReuseAsset, actor: Writer, svc: Acquisition) -> AssetRead:
    source = AcquisitionService(
        AcquisitionRepository(svc.repo.db, svc.repo.workspace, data.source_brand_id),
        svc.identity,
        actor,
        svc.settings,
    )
    return svc.reuse(source, data.source_asset_id, data.destination_rights_id)
