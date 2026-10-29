import re
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import HTTPException

from app.core.config import Settings
from app.modules.acquisition.models import BrandAsset, MediaObject, RightsDecision
from app.modules.acquisition.repository import AcquisitionRepository
from app.modules.acquisition.schemas import AcquisitionRequest, AssetRead, RightsCreate
from app.modules.acquisition.storage import MediaInfo, MediaStorage
from app.modules.discovery.repository import DiscoveryRepository
from app.modules.discovery.service import DiscoveryService
from app.modules.identity.models import User
from app.modules.identity.service import IdentityService
from app.modules.operations.job_models import DurableJob
from app.modules.operations.job_repository import JobRepository
from app.modules.operations.job_service import JobLifecycle, JobService


class AcquisitionService:
    def __init__(
        self,
        repo: AcquisitionRepository,
        identity: IdentityService,
        actor: User,
        settings: Settings,
    ):
        self.repo, self.identity, self.actor, self.settings = repo, identity, actor, settings

    def authorize(self, write: bool = False) -> None:
        self.identity.require_brand(self.actor, self.repo.workspace, self.repo.brand, write=write)

    def jobs(self) -> JobService:
        return JobService(
            JobRepository(self.repo.db),
            self.identity,
            self.actor,
            self.repo.workspace,
            self.repo.brand,
        )

    def rights(
        self, identifier: UUID, approved: bool = False, lock: bool = False
    ) -> RightsDecision:
        self.authorize()
        row = self.repo.rights(identifier, lock=lock)
        if row is None:
            raise HTTPException(404, "Rights decision not found")
        if approved and row.status != "APPROVED":
            raise HTTPException(409, "Rights approval is revoked")
        return row

    def approve_rights(self, data: RightsCreate) -> RightsDecision:
        self.authorize(True)
        if data.candidate_id:
            DiscoveryService(
                DiscoveryRepository(self.repo.db, self.repo.workspace, self.repo.brand),
                self.identity,
                self.actor,
            ).acquisition_candidate(data.candidate_id)
        row = self.repo.save_rights(
            RightsDecision(
                workspace_id=self.repo.workspace,
                brand_id=self.repo.brand,
                reviewed_by=self.actor.id,
                **data.model_dump(exclude={"confirmed"}),
            )
        )
        self.identity.record(
            self.actor, "rights.approved", row.id, self.repo.workspace, self.repo.brand
        )
        return row

    def revoke(self, identifier: UUID) -> RightsDecision:
        self.authorize(True)
        row = self.rights(identifier, lock=True)
        row.status = "REVOKED"
        self.repo.save_rights(row)
        self.identity.record(
            self.actor, "rights.revoked", row.id, self.repo.workspace, self.repo.brand
        )
        return row

    def acquire(self, data: AcquisitionRequest) -> DurableJob:
        self.authorize(True)
        rights = self.rights(data.rights_id, approved=True, lock=True)
        return self.jobs().enqueue(
            "acquisition.download", str(data.idempotency_key), {"rights_id": str(rights.id)}
        )

    def asset(self, identifier: UUID) -> tuple[BrandAsset, MediaObject]:
        self.authorize()
        asset = self.repo.asset(identifier)
        if asset is None:
            raise HTTPException(404, "Asset not found")
        obj = self.repo.object(asset.sha256)
        if obj is None:
            raise HTTPException(409, "Media object is unavailable")
        return asset, obj

    def read(self, asset: BrandAsset) -> AssetRead:
        _, obj = self.asset(asset.id)
        return AssetRead(
            id=asset.id,
            rights_id=asset.rights_id,
            title=asset.title,
            export_name=asset.export_name,
            sha256=obj.sha256,
            size_bytes=obj.size_bytes,
            duration=obj.duration,
            width=obj.width,
            height=obj.height,
            video_codec=obj.video_codec,
            audio_codec=obj.audio_codec,
            rights_status=self.rights(asset.rights_id).status,
            created_at=asset.created_at,
        )

    def register(
        self, rights: RightsDecision, sha256: str, size: int, info: MediaInfo, job: UUID | None
    ) -> BrandAsset:
        obj = self.repo.object(sha256)
        if obj is None:
            self.repo.save_object(
                MediaObject(
                    sha256=sha256,
                    extension=info.extension,
                    mime=info.mime,
                    size_bytes=size,
                    duration=info.duration,
                    width=info.width,
                    height=info.height,
                    video_codec=info.video_codec,
                    audio_codec=info.audio_codec,
                )
            )
        asset = self.repo.by_rights(rights.id, sha256)
        if asset is None:
            identifier = uuid4()
            title = re.sub(r"[^a-z0-9]+", "-", rights.title.casefold()).strip("-")[:100] or "media"
            filename = (
                f"{datetime.now(UTC):%Y-%m-%d}_source_{title}_"
                f"{str(identifier)[:8]}.{info.extension}"
            )
            asset = self.repo.save_asset(
                BrandAsset(
                    id=identifier,
                    workspace_id=self.repo.workspace,
                    brand_id=self.repo.brand,
                    rights_id=rights.id,
                    sha256=sha256,
                    job_id=job,
                    title=rights.title,
                    export_name=filename,
                )
            )
        self.identity.record(
            self.actor,
            "asset.acquired" if job else "asset.reused",
            asset.id,
            self.repo.workspace,
            self.repo.brand,
        )
        return asset

    def complete(
        self, job: UUID, token: UUID, rights_id: UUID, sha256: str, size: int, info: MediaInfo
    ) -> None:
        self.authorize(True)
        rights = self.rights(rights_id, approved=True, lock=True)
        jobs = JobLifecycle(JobRepository(self.repo.db))
        jobs.require_lease(job, token)
        self.register(rights, sha256, size, info, job)
        jobs.finish(job, token)

    def reuse(self, source: "AcquisitionService", source_id: UUID, rights_id: UUID) -> AssetRead:
        self.authorize(True)
        source.authorize(True)
        asset, obj = source.asset(source_id)
        origin = source.rights(asset.rights_id, approved=True)
        destination = self.rights(rights_id, approved=True, lock=True)
        if origin.source_url != destination.source_url:
            raise HTTPException(409, "Destination rights must cover the same source URL")
        # Hash-level serialization protects global object registration/reuse.
        info = MediaInfo(
            obj.extension,
            obj.mime,
            obj.duration,
            obj.width,
            obj.height,
            obj.video_codec,
            obj.audio_codec,
        )
        return self.read(self.register(destination, obj.sha256, obj.size_bytes, info, None))

    def storage(self) -> MediaStorage:
        return MediaStorage(
            self.settings.storage_root,
            self.settings.storage_quota_bytes,
            self.settings.minimum_free_bytes,
        )
