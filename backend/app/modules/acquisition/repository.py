from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.acquisition.models import BrandAsset, MediaObject, RightsDecision


class AcquisitionRepository:
    def __init__(self, db: Session, workspace: UUID, brand: UUID) -> None:
        self.db, self.workspace, self.brand = db, workspace, brand

    def rights(self, identifier: UUID, lock: bool = False) -> RightsDecision | None:
        query = (
            select(RightsDecision)
            .where(
                RightsDecision.workspace_id == self.workspace,
                RightsDecision.brand_id == self.brand,
                RightsDecision.id == identifier,
            )
            .execution_options(populate_existing=True)
        )
        return self.db.scalar(query.with_for_update() if lock else query)

    def list_rights(self, offset: int) -> list[RightsDecision]:
        return list(
            self.db.scalars(
                select(RightsDecision)
                .where(
                    RightsDecision.workspace_id == self.workspace,
                    RightsDecision.brand_id == self.brand,
                )
                .order_by(RightsDecision.created_at.desc(), RightsDecision.id)
                .offset(offset)
                .limit(50)
            )
        )

    def save_rights(self, row: RightsDecision) -> RightsDecision:
        self.db.add(row)
        self.db.flush()
        return row

    def object(self, sha256: str) -> MediaObject | None:
        return self.db.get(MediaObject, sha256)

    def save_object(self, row: MediaObject) -> MediaObject:
        self.db.add(row)
        self.db.flush()
        return row

    def asset(self, identifier: UUID) -> BrandAsset | None:
        return self.db.scalar(
            select(BrandAsset).where(
                BrandAsset.workspace_id == self.workspace,
                BrandAsset.brand_id == self.brand,
                BrandAsset.id == identifier,
            )
        )

    def by_rights(self, rights: UUID, sha256: str) -> BrandAsset | None:
        return self.db.scalar(
            select(BrandAsset).where(
                BrandAsset.workspace_id == self.workspace,
                BrandAsset.brand_id == self.brand,
                BrandAsset.rights_id == rights,
                BrandAsset.sha256 == sha256,
            )
        )

    def assets(self, offset: int) -> list[BrandAsset]:
        return list(
            self.db.scalars(
                select(BrandAsset)
                .where(BrandAsset.workspace_id == self.workspace, BrandAsset.brand_id == self.brand)
                .order_by(BrandAsset.created_at.desc(), BrandAsset.id)
                .offset(offset)
                .limit(50)
            )
        )

    def save_asset(self, row: BrandAsset) -> BrandAsset:
        self.db.add(row)
        self.db.flush()
        return row
