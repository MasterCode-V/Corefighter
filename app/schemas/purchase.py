from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.enums import ImageType, PurchaseStatus


class ProductBase(BaseModel):
    manufacturer: Optional[str] = None
    product_name: Optional[str] = None
    model_number: Optional[str] = None
    category: Optional[str] = None
    condition: Optional[str] = None
    characteristics: Optional[str] = None
    quantity: int = 1
    quantity_unit: str = "点"
    price: Optional[float] = None


class ProductCreate(ProductBase):
    sort_order: int = 0


class ProductRead(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sort_order: int


class PurchaseCreate(BaseModel):
    store_id: uuid.UUID
    persona_id: Optional[uuid.UUID] = None
    purchase_date: Optional[str] = None
    purchase_method: Optional[str] = None
    purchase_area: Optional[str] = None
    quantity: int = 1
    quantity_unit: str = "点"
    manufacturer: Optional[str] = None
    product_name: Optional[str] = None
    model_number: Optional[str] = None
    category: Optional[str] = None
    condition: Optional[str] = None
    characteristics: Optional[str] = None
    price: Optional[float] = None
    manual_notes: Optional[str] = None
    extra_info: dict = Field(default_factory=dict)
    user_instructions: Optional[str] = None
    # Optional multi-product list. When provided it takes precedence over the
    # single manufacturer/product_name/... fields above.
    products: Optional[List[ProductCreate]] = None


class PurchaseUpdate(BaseModel):
    """Used by staff to correct AI-extracted product info (workflow 4 review step)."""

    persona_id: Optional[uuid.UUID] = None
    purchase_date: Optional[str] = None
    purchase_method: Optional[str] = None
    purchase_area: Optional[str] = None
    quantity: Optional[int] = None
    quantity_unit: Optional[str] = None
    manufacturer: Optional[str] = None
    product_name: Optional[str] = None
    model_number: Optional[str] = None
    category: Optional[str] = None
    condition: Optional[str] = None
    characteristics: Optional[str] = None
    price: Optional[float] = None
    manual_notes: Optional[str] = None
    extra_info: Optional[dict] = None
    user_instructions: Optional[str] = None
    # When provided, replaces the entire product list for the purchase.
    products: Optional[List[ProductCreate]] = None


class PurchaseImageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    image_type: ImageType
    url: str
    filename: str
    content_type: str
    size: int
    sort_order: int
    wordpress_media_id: Optional[int] = None


class PurchaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    store_id: uuid.UUID
    created_by: Optional[uuid.UUID]
    persona_id: Optional[uuid.UUID]
    status: PurchaseStatus
    purchase_date: Optional[str]
    purchase_method: Optional[str]
    purchase_area: Optional[str]
    quantity: int
    quantity_unit: str
    manufacturer: Optional[str]
    product_name: Optional[str]
    model_number: Optional[str]
    category: Optional[str]
    condition: Optional[str]
    characteristics: Optional[str]
    price: Optional[float]
    manual_notes: Optional[str]
    extra_info: dict
    ai_extraction: dict
    user_instructions: Optional[str]
    created_at: datetime
    updated_at: datetime
    images: List[PurchaseImageRead] = []
    products: List[ProductRead] = []
