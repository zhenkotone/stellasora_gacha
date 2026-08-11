from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .catalog import FIVE_STAR_ITEMS, gacha_item_kind, gacha_item_name


CATEGORY_TRAVELER_LIMITED = "traveler_limited"
CATEGORY_DISC_LIMITED = "disc_limited"
CATEGORY_TRAVELER_STANDARD = "traveler_standard"
CATEGORY_DISC_STANDARD = "disc_standard"
CATEGORY_UNKNOWN = "unknown"


def classify_history_category(groups: list[dict[str, Any]]) -> str:
    gids: set[int] = set()
    for group in groups:
        try:
            gids.add(int(group.get("Gid")))
        except (TypeError, ValueError):
            continue
    if any(20_000 <= gid < 30_000 for gid in gids):
        return CATEGORY_DISC_LIMITED
    if any(10_000 <= gid < 20_000 for gid in gids):
        return CATEGORY_TRAVELER_LIMITED
    if 1 in gids:
        return CATEGORY_TRAVELER_STANDARD
    if 2 in gids:
        return CATEGORY_DISC_STANDARD
    return CATEGORY_UNKNOWN


@dataclass(frozen=True)
class FiveStarPull:
    item_id: int
    kind: str
    name: str
    pity: int
    timestamp: int
    position: int
    gid: int = 0


@dataclass(frozen=True)
class PoolStats:
    gid: int
    total_pulls: int
    start_time: int
    end_time: int
    five_stars: tuple[FiveStarPull, ...]

    @property
    def average_pulls(self) -> int | None:
        if not self.five_stars:
            return None
        return round(self.total_pulls / len(self.five_stars))

    @property
    def current_pity(self) -> int:
        """Pulls since the most recent five-star in this pool."""
        if not self.five_stars:
            return self.total_pulls
        return self.total_pulls - max(pull.position for pull in self.five_stars)


def build_pool_stats(groups: list[dict[str, Any]]) -> list[PoolStats]:
    by_pool: dict[int, list[dict[str, Any]]] = {}
    for group in groups:
        try:
            gid = int(group.get("Gid"))
        except (TypeError, ValueError):
            continue
        by_pool.setdefault(gid, []).append(group)

    pools: list[PoolStats] = []
    for gid, pool_groups in by_pool.items():
        pool_groups.sort(key=lambda item: (int(item.get("Time") or 0), int(item.get("Gid") or 0)))
        total = 0
        since_last_five = 0
        hits: list[FiveStarPull] = []
        times: list[int] = []
        for group in pool_groups:
            timestamp = int(group.get("Time") or 0)
            if timestamp:
                times.append(timestamp)
            for raw_id in group.get("Ids", []):
                total += 1
                since_last_five += 1
                try:
                    item_id = int(raw_id)
                except (TypeError, ValueError):
                    continue
                if item_id not in FIVE_STAR_ITEMS:
                    continue
                hits.append(
                    FiveStarPull(
                        item_id=item_id,
                        kind=gacha_item_kind(item_id),
                        name=gacha_item_name(item_id),
                        pity=since_last_five,
                        timestamp=timestamp,
                        position=total,
                        gid=gid,
                    )
                )
                since_last_five = 0
        pools.append(
            PoolStats(
                gid=gid,
                total_pulls=total,
                start_time=min(times, default=0),
                end_time=max(times, default=0),
                five_stars=tuple(hits),
            )
        )
    pools.sort(key=lambda item: (item.end_time, item.gid), reverse=True)
    return pools


def build_banner_stats_with_shared_pity(groups: list[dict[str, Any]]) -> list[PoolStats]:
    """Split banners by GID while carrying five-star pity across the category."""
    ordered = sorted(groups, key=lambda item: (int(item.get("Time") or 0), int(item.get("Gid") or 0)))
    banner_totals: dict[int, int] = {}
    banner_times: dict[int, list[int]] = {}
    banner_hits: dict[int, list[FiveStarPull]] = {}
    shared_position = 0
    since_last_five = 0

    for group in ordered:
        try:
            gid = int(group.get("Gid"))
        except (TypeError, ValueError):
            continue
        timestamp = int(group.get("Time") or 0)
        if timestamp:
            banner_times.setdefault(gid, []).append(timestamp)
        for raw_id in group.get("Ids", []):
            shared_position += 1
            since_last_five += 1
            banner_totals[gid] = banner_totals.get(gid, 0) + 1
            try:
                item_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            if item_id not in FIVE_STAR_ITEMS:
                continue
            banner_hits.setdefault(gid, []).append(
                FiveStarPull(
                    item_id=item_id,
                    kind=gacha_item_kind(item_id),
                    name=gacha_item_name(item_id),
                    pity=since_last_five,
                    timestamp=timestamp,
                    position=shared_position,
                    gid=gid,
                )
            )
            since_last_five = 0

    pools = [
        PoolStats(
            gid=gid,
            total_pulls=total,
            start_time=min(banner_times.get(gid, []), default=0),
            end_time=max(banner_times.get(gid, []), default=0),
            five_stars=tuple(reversed(banner_hits.get(gid, []))),
        )
        for gid, total in banner_totals.items()
    ]
    pools.sort(key=lambda item: (item.end_time, item.gid), reverse=True)
    return pools


def build_category_stat(groups: list[dict[str, Any]]) -> PoolStats | None:
    """Merge all banner IDs belonging to one official history category."""
    if not groups:
        return None
    ordered = sorted(groups, key=lambda item: (int(item.get("Time") or 0), int(item.get("Gid") or 0)))
    total = 0
    since_last_five = 0
    hits: list[FiveStarPull] = []
    times: list[int] = []
    for group in ordered:
        timestamp = int(group.get("Time") or 0)
        try:
            gid = int(group.get("Gid") or 0)
        except (TypeError, ValueError):
            gid = 0
        if timestamp:
            times.append(timestamp)
        for raw_id in group.get("Ids", []):
            total += 1
            since_last_five += 1
            try:
                item_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            if item_id not in FIVE_STAR_ITEMS:
                continue
            hits.append(
                FiveStarPull(
                    item_id=item_id,
                    kind=gacha_item_kind(item_id),
                    name=gacha_item_name(item_id),
                    pity=since_last_five,
                    timestamp=timestamp,
                    position=total,
                    gid=gid,
                )
            )
            since_last_five = 0
    # Pity is calculated chronologically; the UI presents newest results first.
    return PoolStats(0, total, min(times, default=0), max(times, default=0), tuple(reversed(hits)))
