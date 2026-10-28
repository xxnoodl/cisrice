from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.modules.discovery.models import Candidate, DiscoveryRun, Observation, Source


class DiscoveryRepository:
    def __init__(self, db: Session, workspace: UUID, brand: UUID):
        self.db, self.workspace, self.brand = db, workspace, brand

    def lock(self) -> None:
        self.db.execute(text("SET LOCAL lock_timeout = '3s'"))
        key = int.from_bytes(self.brand.bytes[:8], "big", signed=True)
        self.db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})

    def sources(self) -> list[Source]:
        return list(
            self.db.scalars(
                select(Source)
                .where(Source.workspace_id == self.workspace, Source.brand_id == self.brand)
                .order_by(Source.created_at.desc())
                .limit(200)
            )
        )

    def source(self, source: UUID) -> Source | None:
        return self.db.scalar(
            select(Source).where(
                Source.workspace_id == self.workspace,
                Source.brand_id == self.brand,
                Source.id == source,
            )
        )

    def source_url(self, url: str) -> Source | None:
        return self.db.scalar(
            select(Source).where(
                Source.workspace_id == self.workspace,
                Source.brand_id == self.brand,
                Source.url == url,
            )
        )

    def save_source(self, row: Source) -> Source:
        self.db.add(row)
        self.db.flush()
        return row

    def save_run(self, row: DiscoveryRun) -> DiscoveryRun:
        self.db.add(row)
        self.db.flush()
        return row

    def save_candidate(self, row: Candidate) -> Candidate:
        self.db.add(row)
        self.db.flush()
        return row

    def candidate(self, candidate: UUID) -> Candidate | None:
        return self.db.scalar(
            select(Candidate).where(
                Candidate.workspace_id == self.workspace,
                Candidate.brand_id == self.brand,
                Candidate.id == candidate,
            )
        )

    def by_url(self, value: str) -> Candidate | None:
        return self.db.scalar(
            select(Candidate).where(
                Candidate.workspace_id == self.workspace,
                Candidate.brand_id == self.brand,
                Candidate.url_hash == value,
            )
        )

    def title_count(self, value: str) -> int:
        return (
            self.db.scalar(
                select(func.count())
                .select_from(Candidate)
                .where(
                    Candidate.workspace_id == self.workspace,
                    Candidate.brand_id == self.brand,
                    Candidate.title_hash == value,
                )
            )
            or 0
        )

    def observe(self, candidate: Candidate, source: Source, identifier: str, url: str) -> None:
        found = self.db.scalar(
            select(Observation).where(
                Observation.candidate_id == candidate.id,
                Observation.source_id == source.id,
                Observation.workspace_id == self.workspace,
                Observation.brand_id == self.brand,
                Observation.source_identifier == identifier,
            )
        )
        if not found:
            self.db.add(
                Observation(
                    workspace_id=self.workspace,
                    brand_id=self.brand,
                    candidate_id=candidate.id,
                    source_id=source.id,
                    source_identifier=identifier,
                    original_url=url,
                )
            )
            self.db.flush()

    def observations(self, candidate: UUID) -> list[Observation]:
        return list(
            self.db.scalars(
                select(Observation)
                .where(
                    Observation.workspace_id == self.workspace,
                    Observation.brand_id == self.brand,
                    Observation.candidate_id == candidate,
                )
                .limit(200)
            )
        )

    def runs(self, offset: int) -> list[DiscoveryRun]:
        return list(
            self.db.scalars(
                select(DiscoveryRun)
                .where(
                    DiscoveryRun.workspace_id == self.workspace, DiscoveryRun.brand_id == self.brand
                )
                .order_by(DiscoveryRun.created_at.desc(), DiscoveryRun.id)
                .offset(offset)
                .limit(50)
            )
        )

    def candidates(
        self, status: str | None, search: str, topic: str, order: str, offset: int
    ) -> list[Candidate]:
        query = select(Candidate).where(
            Candidate.workspace_id == self.workspace, Candidate.brand_id == self.brand
        )
        if status:
            query = query.where(Candidate.status == status)
        if search:
            query = query.where(Candidate.title.icontains(search, autoescape=True))
        if topic:
            query = query.where(Candidate.topics.contains([topic]))
        sorting = (
            Candidate.score.desc().nullslast()
            if order == "score"
            else Candidate.discovered_at.desc()
        )
        return list(self.db.scalars(query.order_by(sorting, Candidate.id).offset(offset).limit(50)))
