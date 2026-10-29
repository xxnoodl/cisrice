from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException

from app.contracts.discovery import AcquisitionCandidate
from app.core.network import NetworkPolicyError as FeedError
from app.core.network import canonical_url
from app.modules.discovery.feeds import (
    FeedItem,
    feed_url,
    fingerprint,
    parse_feed,
)
from app.modules.discovery.models import Candidate, DiscoveryRun, Source
from app.modules.discovery.repository import DiscoveryRepository
from app.modules.discovery.schemas import CandidateRead, CandidateReview, SourceCreate
from app.modules.discovery.scoring import score_item
from app.modules.identity.models import User
from app.modules.identity.service import IdentityService


class DiscoveryService:
    def acquisition_candidate(self, identifier: UUID) -> AcquisitionCandidate:
        self.authorize(True)
        row = self.candidate(identifier)
        if row.status != "APPROVED":
            raise HTTPException(409, "Approve the research candidate before rights review")
        return AcquisitionCandidate(row.id, row.title, row.original_url)

    def __init__(self, repo: DiscoveryRepository, identity: IdentityService, actor: User):
        self.repo, self.identity, self.actor = repo, identity, actor

    def authorize(self, write: bool = False) -> None:
        self.identity.require_brand(self.actor, self.repo.workspace, self.repo.brand, write=write)

    def create_source(self, data: SourceCreate) -> Source:
        self.authorize(True)
        self.repo.lock()
        if len(self.repo.sources()) >= 200:
            raise HTTPException(409, "Brand source limit is 200")
        row = self.repo.save_source(
            Source(
                workspace_id=self.repo.workspace,
                brand_id=self.repo.brand,
                name=data.name,
                kind=data.kind,
                url=feed_url(data.kind, data.address),
                keywords=data.keywords,
                quality=data.quality,
                weights=data.weights,
                policy_note=data.policy_note,
            )
        )
        self.identity.record(
            self.actor, "discovery.source_created", row.id, self.repo.workspace, self.repo.brand
        )
        return row

    def source(self, identifier: UUID) -> Source:
        row = self.repo.source(identifier)
        if row is None:
            raise HTTPException(404, "Source not found")
        return row

    def run(self, identifier: UUID, fetch: Callable[[str], bytes]) -> DiscoveryRun:
        self.authorize(True)
        self.repo.lock()
        self.authorize(True)
        source = self.source(identifier)
        now = datetime.now(UTC)
        if not source.enabled:
            raise HTTPException(409, "Source paused")
        if source.last_run_at and (now - source.last_run_at).total_seconds() < 60:
            raise HTTPException(429, "Wait at least 60 seconds between source runs")
        source.last_run_at = now
        run = DiscoveryRun(
            workspace_id=self.repo.workspace,
            brand_id=self.repo.brand,
            source_id=source.id,
            state="SUCCEEDED",
            found=0,
            added=0,
            duplicates=0,
        )
        try:
            items = parse_feed(fetch(source.url))
        except FeedError as error:
            run.state, run.error = "FAILED", str(error)
        else:
            run.found = len(items)
            for item in items:
                _, added = self.import_item(item, source)
                run.added += int(added)
                run.duplicates += int(not added)
        self.repo.save_source(source)
        self.repo.save_run(run)
        self.identity.record(
            self.actor,
            "discovery.completed",
            run.id,
            self.repo.workspace,
            self.repo.brand,
            {"state": run.state},
        )
        return run

    def import_item(self, item: FeedItem, source: Source) -> tuple[Candidate, bool]:
        hashed = fingerprint(canonical_url(item.url))
        candidate = self.repo.by_url(hashed)
        added = candidate is None
        if candidate is None:
            title_hash = fingerprint(" ".join(item.title.casefold().split()))
            score, components = score_item(
                item,
                source.keywords,
                source.quality,
                not self.repo.title_count(title_hash),
                source.weights,
            )
            candidate = self.repo.save_candidate(
                Candidate(
                    workspace_id=self.repo.workspace,
                    brand_id=self.repo.brand,
                    original_url=item.url,
                    url_hash=hashed,
                    title_hash=title_hash,
                    title=item.title,
                    summary=item.summary,
                    topics=item.topics,
                    published_at=item.published_at,
                    score=score,
                    components=components,
                )
            )
        self.repo.observe(candidate, source, item.identifier, item.url)
        return candidate, added

    def read(self, row: Candidate) -> CandidateRead:
        value = CandidateRead.model_validate(row)
        value.duplicate_title = self.repo.title_count(row.title_hash) > 1
        value.observations = [
            {
                "source_id": str(o.source_id),
                "identifier": o.source_identifier,
                "original_url": o.original_url,
                "observed_at": o.observed_at.isoformat(),
            }
            for o in self.repo.observations(row.id)
        ]
        return value

    def candidate(self, identifier: UUID) -> Candidate:
        row = self.repo.candidate(identifier)
        if row is None:
            raise HTTPException(404, "Candidate not found")
        return row

    def review(self, identifier: UUID, data: CandidateReview) -> CandidateRead:
        self.authorize(True)
        row = self.candidate(identifier)
        row.status, row.notes = data.status, data.notes
        self.repo.save_candidate(row)
        self.identity.record(
            self.actor,
            "discovery.reviewed",
            row.id,
            self.repo.workspace,
            self.repo.brand,
            {"status": data.status},
        )
        return self.read(row)

    def route(self, identifier: UUID, target: "DiscoveryService") -> CandidateRead:
        self.authorize(True)
        target.authorize(True)
        if target.repo.brand == self.repo.brand:
            raise HTTPException(422, "Choose another brand")
        # Lock only destination: source is read, and no reverse lock cycle is created.
        target.repo.lock()
        target.authorize(True)
        original = self.candidate(identifier)
        observations = self.repo.observations(original.id)
        result = None
        for observation in observations:
            source = self.source(observation.source_id)
            destination = target.repo.source_url(source.url)
            if destination is None:
                if len(target.repo.sources()) >= 200:
                    raise HTTPException(409, "Destination brand source limit is 200")
                destination = target.repo.save_source(
                    Source(
                        workspace_id=target.repo.workspace,
                        brand_id=target.repo.brand,
                        name=source.name,
                        kind=source.kind,
                        url=source.url,
                        keywords=source.keywords,
                        quality=source.quality,
                        weights=source.weights,
                        policy_note=source.policy_note,
                        enabled=False,
                    )
                )
            result, _ = target.import_item(
                FeedItem(
                    observation.source_identifier,
                    observation.original_url,
                    original.title,
                    original.summary,
                    original.published_at,
                    original.topics,
                ),
                destination,
            )
        if result is None:
            raise HTTPException(409, "Candidate has no source provenance")
        # Private research notes and review state are intentionally not copied.
        target.identity.record(
            self.actor, "discovery.routed", result.id, target.repo.workspace, target.repo.brand
        )
        return target.read(result)
