from datetime import UTC, datetime

from app.modules.discovery.feeds import FeedItem
from app.modules.discovery.schemas import DEFAULT_WEIGHTS


def score_item(
    item: FeedItem,
    keywords: list[str],
    quality: float,
    novel: bool,
    weights: dict[str, float] | None = None,
) -> tuple[float | None, dict[str, float | None]]:
    text = (item.title + " " + item.summary).casefold()
    age = (
        (datetime.now(UTC) - item.published_at).total_seconds() / 86400
        if item.published_at
        else None
    )
    components: dict[str, float | None] = {
        "relevance": sum(word.casefold() in text for word in keywords) / len(keywords)
        if keywords
        else None,
        "engagement_velocity": None,
        "shares": None,
        "saves": None,
        "freshness": max(0.0, 1 - age / 30) if age is not None and age >= 0 else None,
        "novelty": 1.0 if novel else 0.0,
        "source_quality": quality,
    }
    weights = weights or DEFAULT_WEIGHTS
    denominator = sum(weights[key] for key, value in components.items() if value is not None)
    total = sum(weights[key] * value for key, value in components.items() if value is not None)
    return (round(total / denominator * 100, 2) if denominator else None), components
