"""Read and write the creator database (spec §4.4, §4.9, §4.11).

Every function takes an optional `session_factory` (tests pass their own); otherwise the
app's database is used. Works on Postgres (production, with pgvector) and SQLite (tests).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional, Sequence

import numpy as np
from sqlalchemy import delete, func, or_, select, text, update

from app.creators import constants as C
from app.metrics.stats import follower_tier
from app.models.creator import (
    Creator,
    CreatorEmbedding,
    CreatorJudgment,
    CreatorPerson,
    CreatorSnapshot,
    PersonLink,
)
from app.platforms.base import CreatorProfile


def _factory(session_factory):
    if session_factory is not None:
        return session_factory
    from app.db.database import AsyncSessionLocal

    return AsyncSessionLocal


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _sha(parts: Any) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def _jsonable(value: Any) -> Any:
    """Make posts (with datetimes) safe for JSON columns."""
    return json.loads(json.dumps(value, default=lambda o: o.isoformat() if isinstance(o, datetime) else str(o)))


# --- Hashes used as cache keys --------------------------------------------------------------


def content_hash(profile: CreatorProfile) -> str:
    """Changes when what Jev reads changes (bio, name, post texts)."""
    return _sha(
        {
            "name": profile.get("display_name"),
            "bio": profile.get("bio"),
            "posts": [p.get("text") for p in profile.get("recent_posts") or []],
        }
    )


def brief_hash(brief: Any) -> str:
    return _sha(brief.__dict__ if hasattr(brief, "__dict__") else brief)


# --- Profiles -------------------------------------------------------------------------------------


def _row_values(profile: CreatorProfile, now: datetime) -> dict:
    platform = profile["platform"]
    ttl = C.DATA_TTL.get(platform)
    return {
        "handle": profile.get("handle"),
        "display_name": profile.get("display_name"),
        "bio": profile.get("bio"),
        "url": profile.get("url"),
        "avatar_url": profile.get("avatar_url"),
        "followers": profile.get("followers"),
        "tier": follower_tier(profile.get("followers")),
        "country": profile.get("country"),
        "language": profile.get("language"),
        "contacts": _jsonable(profile.get("contacts") or {}),
        "cross_links": _jsonable(profile.get("cross_links") or {}),
        "external_links": _jsonable(profile.get("external_links") or []),
        "source": profile.get("source"),
        "last_fetched_at": _aware(profile.get("fetched_at")) or now,
        "data_expires_at": (now + ttl) if ttl else None,
    }


async def upsert_profile(profile: CreatorProfile, *, session_factory=None) -> str:
    """Insert or update one account. Returns its creator_id."""
    if not profile.get("platform") or not profile.get("platform_id"):
        raise ValueError("profile needs platform and platform_id")
    now = _now()
    async with _factory(session_factory)() as session:
        row = (
            await session.execute(
                select(Creator).where(Creator.platform == profile["platform"], Creator.platform_id == profile["platform_id"])
            )
        ).scalar_one_or_none()
        values = _row_values(profile, now)
        if row is None:
            row = Creator(platform=profile["platform"], platform_id=profile["platform_id"], **values)
            session.add(row)
        else:
            for k, v in values.items():
                setattr(row, k, v)
        await session.commit()
        return row.creator_id


async def save_snapshot(
    creator_id: str, profile: CreatorProfile, metrics: Optional[dict] = None, *, session_factory=None
) -> str:
    """Store posts + metrics at this point in time and copy the latest metrics onto the creator."""
    now = _now()
    metrics = _jsonable(metrics) if metrics else None
    async with _factory(session_factory)() as session:
        snap = CreatorSnapshot(
            creator_id=creator_id,
            captured_at=_aware(profile.get("fetched_at")) or now,
            followers=profile.get("followers"),
            recent_posts=_jsonable(profile.get("recent_posts") or []),
            metrics=metrics,
        )
        session.add(snap)
        if metrics:
            await session.execute(
                update(Creator)
                .where(Creator.creator_id == creator_id)
                .values(
                    latest_metrics=metrics,
                    latest_engagement_rate=metrics.get("engagement_rate"),
                    latest_median_views=metrics.get("median_views"),
                )
            )
        await session.commit()
        return snap.snapshot_id


def _profile_from_row(row: Creator, posts: Optional[list] = None) -> CreatorProfile:
    return CreatorProfile(
        creator_id=row.creator_id,
        platform=row.platform,
        platform_id=row.platform_id,
        handle=row.handle,
        display_name=row.display_name,
        bio=row.bio or "",
        url=row.url,
        avatar_url=row.avatar_url,
        person_id=row.person_id,
        followers=row.followers or 0,
        country=row.country,
        language=row.language,
        external_links=row.external_links or [],
        contacts=row.contacts or {},
        cross_links=row.cross_links or {},
        recent_posts=posts or [],
        fetched_at=_aware(row.last_fetched_at),
        source=row.source,
    )


@dataclass
class FreshSplit:
    fresh: dict[str, CreatorProfile]  # platform_id -> stored profile (posts still need a fresh fetch)
    to_fetch: list[str]  # platform_ids with no usable stored profile


async def split_fresh(
    platform: str,
    platform_ids: Sequence[str],
    *,
    max_age: timedelta = C.PROFILE_MAX_AGE,
    now: Optional[datetime] = None,
    session_factory=None,
) -> FreshSplit:
    """Which accounts can reuse their stored profile (fetched within max_age and not expired)."""
    ids = list(dict.fromkeys(platform_ids))  # dedupe, keep order
    if not ids:
        return FreshSplit({}, [])
    now = _aware(now) or _now()
    async with _factory(session_factory)() as session:
        rows = (
            await session.execute(select(Creator).where(Creator.platform == platform, Creator.platform_id.in_(ids)))
        ).scalars().all()
    fresh = {}
    for row in rows:
        fetched, expires = _aware(row.last_fetched_at), _aware(row.data_expires_at)
        if fetched and now - fetched <= max_age and (expires is None or expires > now):
            fresh[row.platform_id] = _profile_from_row(row)
    return FreshSplit(fresh=fresh, to_fetch=[i for i in ids if i not in fresh])


async def get_creator(creator_id: str, *, with_latest_posts: bool = True, session_factory=None) -> Optional[CreatorProfile]:
    async with _factory(session_factory)() as session:
        row = await session.get(Creator, creator_id)
        if row is None:
            return None
        posts = None
        if with_latest_posts:
            snap = (
                await session.execute(
                    select(CreatorSnapshot)
                    .where(CreatorSnapshot.creator_id == creator_id)
                    .order_by(CreatorSnapshot.captured_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            posts = snap.recent_posts if snap else None
        return _profile_from_row(row, posts)


async def get_creators(creator_ids: Sequence[str], *, session_factory=None) -> dict[str, CreatorProfile]:
    """Many creators with their latest posts, in two queries (for pipeline steps)."""
    ids = list(dict.fromkeys(creator_ids))
    if not ids:
        return {}
    async with _factory(session_factory)() as session:
        rows = (await session.execute(select(Creator).where(Creator.creator_id.in_(ids)))).scalars().all()
        snaps = (
            await session.execute(
                select(CreatorSnapshot).where(CreatorSnapshot.creator_id.in_(ids)).order_by(CreatorSnapshot.captured_at)
            )
        ).scalars().all()
    latest = {s.creator_id: s for s in snaps}  # ordered by time, so the last one wins
    out = {}
    for row in rows:
        snap = latest.get(row.creator_id)
        profile = _profile_from_row(row, snap.recent_posts if snap else None)
        profile["metrics"] = snap.metrics if snap else None
        out[row.creator_id] = profile
    return out


async def creator_ids_for(platform: str, platform_ids: Sequence[str], *, session_factory=None) -> dict[str, str]:
    """platform_id -> creator_id for accounts already in the database."""
    if not platform_ids:
        return {}
    async with _factory(session_factory)() as session:
        rows = (
            await session.execute(
                select(Creator.platform_id, Creator.creator_id).where(
                    Creator.platform == platform, Creator.platform_id.in_(list(platform_ids))
                )
            )
        ).all()
    return {r[0]: r[1] for r in rows}


# --- Peers and training data -----------------------------------------------------------------------


async def peer_engagement(platform: str, tier: str, *, limit: int = 5000, session_factory=None) -> list[float]:
    """Latest engagement rates of creators on the same platform and tier (for percentiles)."""
    async with _factory(session_factory)() as session:
        rows = (
            await session.execute(
                select(Creator.latest_engagement_rate)
                .where(Creator.platform == platform, Creator.tier == tier, Creator.latest_engagement_rate.is_not(None))
                .limit(limit)
            )
        ).scalars().all()
    return [float(r) for r in rows]


async def anomaly_training_rows(platform: str, *, limit: int = 20000, session_factory=None) -> list[dict]:
    """Latest metrics of every creator on a platform (to train the fake-engagement model)."""
    async with _factory(session_factory)() as session:
        rows = (
            await session.execute(
                select(Creator.latest_metrics).where(Creator.platform == platform, Creator.latest_metrics.is_not(None)).limit(limit)
            )
        ).scalars().all()
    return [r for r in rows if isinstance(r, dict)]


# --- Jev answer cache ------------------------------------------------------------------------------------


async def get_cached_judgment(
    creator_id: str, content_hash_: str, brief_hash_: str, questions_version: str, *, session_factory=None
) -> Optional[dict]:
    async with _factory(session_factory)() as session:
        row = (
            await session.execute(
                select(CreatorJudgment).where(
                    CreatorJudgment.creator_id == creator_id,
                    CreatorJudgment.content_hash == content_hash_,
                    CreatorJudgment.brief_hash == brief_hash_,
                    CreatorJudgment.questions_version == questions_version,
                )
            )
        ).scalar_one_or_none()
        return row.answers if row else None


async def save_judgment(
    creator_id: str,
    content_hash_: str,
    brief_hash_: str,
    questions_version: str,
    judgment: dict,
    *,
    campaign_id: Optional[str] = None,
    session_factory=None,
) -> None:
    """Store a Judgment.to_dict(). LLM-fallback answers are not cached (they're less reliable)."""
    if judgment.get("source") != "jev":
        return
    async with _factory(session_factory)() as session:
        existing = (
            await session.execute(
                select(CreatorJudgment).where(
                    CreatorJudgment.creator_id == creator_id,
                    CreatorJudgment.content_hash == content_hash_,
                    CreatorJudgment.brief_hash == brief_hash_,
                    CreatorJudgment.questions_version == questions_version,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return
        session.add(
            CreatorJudgment(
                creator_id=creator_id,
                campaign_id=campaign_id,
                content_hash=content_hash_,
                brief_hash=brief_hash_,
                questions_version=questions_version,
                model=judgment.get("model"),
                source=judgment.get("source"),
                answers=_jsonable(judgment),
                input_tokens=judgment.get("input_tokens"),
            )
        )
        await session.commit()


# --- Embeddings and similar-creator search ---------------------------------------------------------------


def text_hash(text_: str) -> str:
    return hashlib.sha256(text_.encode()).hexdigest()


def _vector_literal(values: Sequence[float]) -> str:
    return "[" + ",".join(repr(float(v)) for v in values) + "]"


def _parse_vector(raw: Any) -> list[float]:
    if isinstance(raw, (list, tuple)):
        return [float(v) for v in raw]
    return [float(v) for v in json.loads(raw)]


def _check_dim(values: Sequence[float]) -> None:
    if len(values) != C.EMBEDDING_DIM:
        raise ValueError(f"embedding must have {C.EMBEDDING_DIM} values, got {len(values)}")


async def save_embedding(
    creator_id: str, embedding: Sequence[float], text_hash_: str, *, model: str = C.EMBEDDING_MODEL, session_factory=None
) -> None:
    _check_dim(embedding)
    literal = _vector_literal(embedding)
    async with _factory(session_factory)() as session:
        is_pg = session.bind.dialect.name == "postgresql"
        await session.execute(delete(CreatorEmbedding).where(CreatorEmbedding.creator_id == creator_id))
        value_sql = "CAST(:emb AS vector)" if is_pg else ":emb"
        await session.execute(
            text(
                "INSERT INTO creator_embeddings (creator_id, model, text_hash, embedding) "
                f"VALUES (:cid, :model, :hash, {value_sql})"
            ),
            {"cid": creator_id, "model": model, "hash": text_hash_, "emb": literal},
        )
        await session.commit()


async def get_embedding(
    creator_id: str, text_hash_: str, *, model: str = C.EMBEDDING_MODEL, session_factory=None
) -> Optional[list[float]]:
    """Cached embedding, only if it was made from the same text with the same model."""
    async with _factory(session_factory)() as session:
        is_pg = session.bind.dialect.name == "postgresql"
        col = "CAST(embedding AS text)" if is_pg else "embedding"
        row = (
            await session.execute(
                text(f"SELECT {col} FROM creator_embeddings WHERE creator_id = :cid AND text_hash = :hash AND model = :model"),
                {"cid": creator_id, "hash": text_hash_, "model": model},
            )
        ).first()
    return _parse_vector(row[0]) if row else None


@dataclass
class SimilarCreator:
    creator_id: str
    platform: str
    platform_id: str
    display_name: Optional[str]
    followers: Optional[int]
    similarity: float  # cosine similarity, 1 = identical


async def similar_creators(
    query: Sequence[float],
    *,
    platforms: Optional[Iterable[str]] = None,
    min_followers: int = 0,
    max_followers: Optional[int] = None,
    limit: int = 50,
    session_factory=None,
) -> list[SimilarCreator]:
    """Nearest creators by embedding (pgvector on Postgres; exact numpy search on SQLite)."""
    _check_dim(query)
    platforms = list(platforms) if platforms else None
    params: dict[str, Any] = {"min_f": min_followers, "lim": limit}
    filters = ["COALESCE(c.followers, 0) >= :min_f"]
    if max_followers is not None:
        filters.append("COALESCE(c.followers, 0) <= :max_f")
        params["max_f"] = max_followers
    if platforms:
        names = [f":p{i}" for i in range(len(platforms))]
        filters.append(f"c.platform IN ({', '.join(names)})")
        params.update({f"p{i}": p for i, p in enumerate(platforms)})
    where = " AND ".join(filters)

    async with _factory(session_factory)() as session:
        is_pg = session.bind.dialect.name == "postgresql"
        if is_pg:
            params["q"] = _vector_literal(query)
            rows = (
                await session.execute(
                    text(
                        "SELECT c.creator_id, c.platform, c.platform_id, c.display_name, c.followers, "
                        "1 - (e.embedding <=> CAST(:q AS vector)) AS similarity "
                        "FROM creator_embeddings e JOIN creators c ON c.creator_id = e.creator_id "
                        f"WHERE {where} ORDER BY e.embedding <=> CAST(:q AS vector) LIMIT :lim"
                    ),
                    params,
                )
            ).all()
            return [SimilarCreator(r[0], r[1], r[2], r[3], r[4], round(float(r[5]), 6)) for r in rows]

        rows = (
            await session.execute(
                text(
                    "SELECT c.creator_id, c.platform, c.platform_id, c.display_name, c.followers, e.embedding "
                    "FROM creator_embeddings e JOIN creators c ON c.creator_id = e.creator_id "
                    f"WHERE {where}"
                ),
                params,
            )
        ).all()
    q = np.asarray(query, dtype=float)
    qn = np.linalg.norm(q) or 1.0
    scored = []
    for r in rows:
        v = np.asarray(_parse_vector(r[5]), dtype=float)
        sim = float(v @ q / ((np.linalg.norm(v) or 1.0) * qn))
        scored.append(SimilarCreator(r[0], r[1], r[2], r[3], r[4], round(sim, 6)))
    scored.sort(key=lambda s: s.similarity, reverse=True)
    return scored[:limit]


# --- One person, several accounts --------------------------------------------------------------------------


async def link_accounts(
    creator_a: str,
    creator_b: str,
    *,
    source: str,
    confidence: float = 1.0,
    suggest_only: bool = False,
    session_factory=None,
) -> Optional[str]:
    """Mark two accounts as the same person. Returns the person_id, or None if only suggested.

    Self/reverse links (one account links to the other) merge right away. A name match only
    merges at confidence >= NAME_MATCH_MERGE_FROM; below that it's stored as a suggestion.
    `suggest_only`: store it as a suggestion whatever the confidence (shown as "Probably also").
    """
    if creator_a == creator_b:
        raise ValueError("cannot link an account to itself")
    merge = not suggest_only and (source in C.AUTO_MERGE_SOURCES or (source == C.LINK_NAME_MATCH and confidence >= C.NAME_MATCH_MERGE_FROM))
    async with _factory(session_factory)() as session:
        a, b = await session.get(Creator, creator_a), await session.get(Creator, creator_b)
        if a is None or b is None:
            raise ValueError("both creators must exist")

        if not merge:
            # Record the suggestion on b without changing who it belongs to.
            if a.person_id is None:
                person = CreatorPerson(display_name=a.display_name)
                session.add(person)
                await session.flush()
                a.person_id = person.person_id
                await session.merge(PersonLink(creator_id=a.creator_id, person_id=person.person_id, link_source=C.LINK_SELF, confidence=1.0, status="linked"))
            existing = await session.get(PersonLink, b.creator_id)
            if existing is None:
                session.add(PersonLink(creator_id=b.creator_id, person_id=a.person_id, link_source=source, confidence=confidence, status="suggested"))
            await session.commit()
            return None

        # Pick the surviving person: a's if it has one, else b's, else a new one.
        target = a.person_id or b.person_id
        if target is None:
            person = CreatorPerson(display_name=a.display_name or b.display_name)
            session.add(person)
            await session.flush()
            target = person.person_id

        # If b already belonged to another person, move that whole person into target.
        for old in {a.person_id, b.person_id} - {None, target}:
            await session.execute(update(Creator).where(Creator.person_id == old).values(person_id=target))
            await session.execute(update(PersonLink).where(PersonLink.person_id == old).values(person_id=target))
            await session.execute(delete(CreatorPerson).where(CreatorPerson.person_id == old))

        for creator, src, conf in ((a, C.LINK_SELF, 1.0), (b, source, confidence)):
            creator.person_id = target
            link = await session.get(PersonLink, creator.creator_id)
            if link is None:
                session.add(PersonLink(creator_id=creator.creator_id, person_id=target, link_source=src, confidence=conf, status="linked"))
            else:
                link.person_id, link.status = target, "linked"
                if creator is b:
                    link.link_source, link.confidence = src, conf
        await session.commit()
        return target


async def find_by_keys(keys: Sequence[tuple[str, str]], *, session_factory=None) -> dict[tuple[str, str], str]:
    """{(platform, key): creator_id} for accounts we've measured, matched by platform id or handle (any case).
    Keys come from app/creators/identity.parse_link ("@handle" for YouTube handles)."""
    out: dict[tuple[str, str], str] = {}
    wanted = [(p, k) for p, k in dict.fromkeys(keys) if p and k]
    if not wanted:
        return out
    by_platform: dict[str, set[str]] = {}
    for p, k in wanted:
        by_platform.setdefault(p, set()).add(k)
    async with _factory(session_factory)() as session:
        for p, ks in by_platform.items():
            plain = {k.lstrip("@").lower() for k in ks}
            rows = (await session.execute(select(Creator.creator_id, Creator.platform_id, Creator.handle).where(
                Creator.platform == p,
                or_(Creator.platform_id.in_(list(ks)), func.lower(func.ltrim(Creator.handle, "@")).in_(list(plain)),
                    func.lower(Creator.platform_id).in_(list(plain)))))).all()
            for cid, pid, handle in rows:
                for k in ks:
                    bare = k.lstrip("@").lower()
                    if k == pid or bare == (pid or "").lower() or bare == (handle or "").lstrip("@").lower():
                        out[(p, k)] = cid
    return out


async def people_of(creator_ids: Sequence[str], *, session_factory=None) -> dict[str, dict]:
    """{creator_id: {"person_id", "accounts": [{creator_id, status, source}]}} for these accounts: the other
    accounts linked to the same person, plus suggestions ("suggested") pointing at them."""
    ids = list(dict.fromkeys(creator_ids))
    if not ids:
        return {}
    async with _factory(session_factory)() as session:
        persons = dict((await session.execute(select(Creator.creator_id, Creator.person_id).where(Creator.creator_id.in_(ids)))).all())
        # an account suggested for someone else's person: show that person's accounts from its side too
        suggested_for = dict((await session.execute(select(PersonLink.creator_id, PersonLink.person_id).where(
            PersonLink.creator_id.in_(ids), PersonLink.status == "suggested"))).all())
        pids = {p for p in persons.values() if p} | set(suggested_for.values())
        members = (await session.execute(select(Creator.creator_id, Creator.person_id).where(Creator.person_id.in_(list(pids))))).all() if pids else []
        links = {l.creator_id: l for l in (await session.execute(select(PersonLink).where(PersonLink.person_id.in_(list(pids))))).scalars()} if pids else {}
    out: dict[str, dict] = {}
    for cid in ids:
        pid = persons.get(cid)
        accounts = []
        if pid:
            accounts = [{"creator_id": m, "status": "linked", "source": (links.get(m).link_source if links.get(m) else C.LINK_SELF)}
                        for m, mp in members if mp == pid and m != cid]
            accounts += [{"creator_id": l.creator_id, "status": "suggested", "source": l.link_source}
                         for l in links.values() if l.status == "suggested" and l.creator_id != cid
                         and l.creator_id not in {a["creator_id"] for a in accounts}]
        other = suggested_for.get(cid)
        if other and other != pid:
            seen = {a["creator_id"] for a in accounts}
            accounts += [{"creator_id": m, "status": "suggested", "source": C.LINK_NAME_MATCH}
                         for m, mp in members if mp == other and m != cid and m not in seen]
        out[cid] = {"person_id": pid, "accounts": accounts}
    return out


async def person_accounts(person_id: str, *, session_factory=None) -> list[CreatorProfile]:
    async with _factory(session_factory)() as session:
        rows = (await session.execute(select(Creator).where(Creator.person_id == person_id))).scalars().all()
    return [_profile_from_row(r) for r in rows]


# --- Expiry (YouTube 30-day rule; used by the refresh job, roadmap F1.11) ----------------------------------------


async def expired_creator_ids(*, now: Optional[datetime] = None, limit: int = 500, session_factory=None) -> list[str]:
    now = _aware(now) or _now()
    async with _factory(session_factory)() as session:
        rows = (
            await session.execute(
                select(Creator.creator_id).where(Creator.data_expires_at.is_not(None), Creator.data_expires_at <= now).limit(limit)
            )
        ).scalars().all()
    return list(rows)


async def delete_creator(creator_id: str, *, session_factory=None) -> None:
    """Remove an account and everything stored about it (expiry or a deletion request)."""
    async with _factory(session_factory)() as session:
        for model in (CreatorSnapshot, CreatorJudgment, CreatorEmbedding, PersonLink):
            await session.execute(delete(model).where(model.creator_id == creator_id))
        await session.execute(delete(Creator).where(Creator.creator_id == creator_id))
        await session.commit()


async def count_creators(platform: Optional[str] = None, *, session_factory=None) -> int:
    async with _factory(session_factory)() as session:
        q = select(func.count()).select_from(Creator)
        if platform:
            q = q.where(Creator.platform == platform)
        return int((await session.execute(q)).scalar_one())
