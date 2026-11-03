from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from camp_match.modules.housing.domain.value_objects import (
    BillingPeriod,
    Currency,
    PropertyType,
)


class PropertyResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    provider_id: UUID
    property_type: PropertyType
    name: str
    description: str | None
    address: str
    latitude: float
    longitude: float
    campus_id: UUID | None
    status: str

class CreatePropertySchema(BaseModel):
    name: str
    property_type: PropertyType
    description: str | None = None
    address: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    campus_id: UUID | None = None

class UpdatePropertySchema(BaseModel):
    name: str | None = None
    description: str | None = None
    address: str | None = None
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    campus_id: UUID | None = None

class UnitResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    property_id: UUID
    label: str
    total_capacity: int
    occupied_count: int
    is_furnished: bool
    has_private_bathroom: bool
    has_kitchen: bool

class CreateUnitSchema(BaseModel):
    label: str
    total_capacity: int = Field(gt=0)
    is_furnished: bool = False
    has_private_bathroom: bool = False
    has_kitchen: bool = False

class UpdateUnitSchema(BaseModel):
    label: str | None = None
    total_capacity: int | None = Field(None, gt=0)
    is_furnished: bool | None = None
    has_private_bathroom: bool | None = None
    has_kitchen: bool | None = None

class PriceSchema(BaseModel):
    amount_kobo: int
    currency: str
    period: str

class ListingResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    property_id: UUID
    unit_id: UUID
    title: str
    description: str | None
    price: PriceSchema
    status: str
    media: list[dict] = []

class CreateListingSchema(BaseModel):
    property_id: UUID
    unit_id: UUID
    title: str
    description: str | None = None
    price_amount_kobo: int = Field(ge=0)
    price_currency: Currency
    price_period: BillingPeriod

class UpdateListingSchema(BaseModel):
    title: str | None = None
    description: str | None = None
    price_amount_kobo: int | None = Field(None, ge=0)

class AvailabilityResponseSchema(BaseModel):
    available_count: int

class PropertyPageSchema(BaseModel):
    items: list[PropertyResponseSchema]
    total: int
    page: int
    page_size: int
