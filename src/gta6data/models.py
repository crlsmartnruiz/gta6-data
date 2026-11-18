"""Domain models.

NOTE: Field shapes are provisional scaffolding. Final schemas must be locked
during launch-week datamining (Nov 19-22) once real game data exists.
All models carry `source` and `updated_at` so every record stays auditable.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Vehicle(BaseModel):
    id: str  # stable slug, e.g. "cheetah-classic"
    name: str
    manufacturer: str | None = None
    vehicle_class: str | None = None  # "sports", "super", "off-road", ...
    price: int | None = None  # in-game currency
    notes: str | None = None  # free-text description from the source
    stats: dict[str, float] = Field(default_factory=dict)  # speed/accel/handling if exposed
    source: str
    updated_at: datetime = Field(default_factory=utcnow)


class Location(BaseModel):
    id: str
    name: str
    area: str | None = None  # district/island name once confirmed
    kind: str | None = None  # "shop", "mission", "collectible", "property", ...
    lat: float | None = None
    lon: float | None = None
    notes: str | None = None
    source: str
    updated_at: datetime = Field(default_factory=utcnow)


class Mission(BaseModel):
    id: str
    name: str
    kind: str | None = None  # "story", "side", "event", ...
    reward: str | None = None
    prereq: list[str] = Field(default_factory=list)
    source: str
    updated_at: datetime = Field(default_factory=utcnow)


class PricePoint(BaseModel):
    """One observed in-game economy sample (store prices, market items)."""

    id: str
    item_id: str
    price: int
    currency: str = "GTA$"
    observed_at: datetime = Field(default_factory=utcnow)
    source: str
    updated_at: datetime = Field(default_factory=utcnow)
