from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.models import Order, OrderSide, OrderStatus, Position, User, Wallet
from app.schemas import OrderEvent

settings = get_settings()
TWOPLACES = Decimal("0.01")


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


async def get_live_price(redis: Redis, symbol: str) -> Decimal:
    price = await redis.get(f"price:{symbol.upper()}")
    if price is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Live price not available for symbol '{symbol.upper()}'.",
        )
    return quantize_money(Decimal(price))


def create_user(db: Session, name: str, email: str) -> User:
    existing = db.scalar(select(User).where(User.email == email))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists.",
        )

    user = User(name=name, email=email)
    wallet = Wallet(balance=quantize_money(Decimal(str(settings.starting_wallet_balance))))
    user.wallet = wallet
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_or_404(db: Session, user_id: int) -> User:
    user = db.scalar(
        select(User)
        .where(User.id == user_id)
        .options(joinedload(User.wallet))
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return user


async def place_order(db: Session, redis: Redis, user_id: int, symbol: str, qty: int, side: OrderSide) -> tuple[Order, Wallet]:
    symbol = symbol.upper()
    live_price = await get_live_price(redis, symbol)
    order_value = quantize_money(live_price * qty)

    user = get_user_or_404(db, user_id)
    if user.wallet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found.")

    wallet = db.scalar(select(Wallet).where(Wallet.user_id == user_id).with_for_update())
    if wallet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found.")

    position = db.scalar(
        select(Position)
        .where(Position.user_id == user_id, Position.symbol == symbol)
        .with_for_update()
    )

    if side == OrderSide.BUY:
        if wallet.balance < order_value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient wallet balance for this order.",
            )
        wallet.balance = quantize_money(wallet.balance - order_value)
        if position is None:
            position = Position(
                user_id=user_id,
                symbol=symbol,
                quantity=qty,
                average_price=live_price,
            )
            db.add(position)
        else:
            total_qty = position.quantity + qty
            total_cost = (position.average_price * position.quantity) + (live_price * qty)
            position.quantity = total_qty
            position.average_price = quantize_money(total_cost / total_qty)
    else:
        if position is None or position.quantity < qty:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient position quantity for this sell order.",
            )
        wallet.balance = quantize_money(wallet.balance + order_value)
        remaining_qty = position.quantity - qty
        if remaining_qty == 0:
            db.delete(position)
        else:
            position.quantity = remaining_qty

    order = Order(
        user_id=user_id,
        symbol=symbol,
        qty=qty,
        side=side,
        price=live_price,
        status=OrderStatus.COMPLETED,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    db.refresh(wallet)
    return order, wallet


async def build_order_event(order: Order, wallet: Wallet) -> dict:
    return OrderEvent(
        symbol=order.symbol,
        qty=order.qty,
        side=order.side,
        price=quantize_money(order.price),
        status=order.status,
        wallet_balance=quantize_money(wallet.balance),
    ).model_dump(mode="json")
