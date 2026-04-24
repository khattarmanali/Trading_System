from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import OrderSide, OrderStatus


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr


class WalletResponse(BaseModel):
    balance: Decimal

    model_config = ConfigDict(from_attributes=True)


class UserResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    wallet: WalletResponse

    model_config = ConfigDict(from_attributes=True)


class UserSummaryResponse(BaseModel):
    id: int
    name: str
    email: EmailStr
    wallet: WalletResponse

    model_config = ConfigDict(from_attributes=True)


class OrderCreate(BaseModel):
    user_id: int
    symbol: str = Field(min_length=1, max_length=25)
    qty: int = Field(gt=0)
    side: OrderSide


class OrderResponse(BaseModel):
    id: int
    user_id: int
    symbol: str
    qty: int
    side: OrderSide
    price: Decimal
    status: OrderStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PortfolioItemResponse(BaseModel):
    symbol: str
    quantity: int
    average_price: Decimal
    current_price: Decimal
    unrealized_pnl: Decimal


class OrderEvent(BaseModel):
    event: str = "order_executed"
    symbol: str
    qty: int
    side: OrderSide
    price: Decimal
    status: OrderStatus
    wallet_balance: Decimal


class MarketPriceResponse(BaseModel):
    symbol: str
    price: Decimal
