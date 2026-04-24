from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import Base, engine, get_db
from app.dependencies import get_redis
from app.market_data import cancel_background_task, seed_market_prices, update_market_prices_forever
from app.models import Order, Position, User, Wallet
from app.schemas import (
    MarketPriceResponse,
    OrderCreate,
    OrderResponse,
    PortfolioItemResponse,
    UserCreate,
    UserResponse,
    UserSummaryResponse,
)
from app.services import (
    build_order_event,
    create_user,
    get_live_price,
    get_user_or_404,
    place_order,
    quantize_money,
)
from app.websocket_manager import WebSocketManager

settings = get_settings()
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


async def wait_for_dependencies(app_settings: Settings, redis: Redis) -> None:
    last_error: Exception | None = None
    for _ in range(app_settings.dependency_retry_attempts):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            await redis.ping()
            return
        except Exception as exc:
            last_error = exc
            await asyncio.sleep(app_settings.dependency_retry_delay_seconds)
    if last_error:
        raise last_error


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    app.state.redis = redis
    app.state.ws_manager = WebSocketManager()
    await wait_for_dependencies(settings, redis)
    Base.metadata.create_all(bind=engine)
    await seed_market_prices(redis, settings)
    app.state.market_task = asyncio.create_task(update_market_prices_forever(redis, settings))
    try:
        yield
    finally:
        await cancel_background_task(getattr(app.state, "market_task", None))
        await redis.aclose()


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def frontend() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/users", response_model=UserResponse, status_code=201)
def create_user_endpoint(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    return create_user(db, payload.name, payload.email)


@app.get("/users/{user_id}", response_model=UserSummaryResponse)
def get_user_endpoint(user_id: int, db: Session = Depends(get_db)) -> User:
    return get_user_or_404(db, user_id)


@app.post("/orders", response_model=OrderResponse, status_code=201)
async def create_order_endpoint(
    payload: OrderCreate,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    order, wallet = await place_order(
        db=db,
        redis=redis,
        user_id=payload.user_id,
        symbol=payload.symbol,
        qty=payload.qty,
        side=payload.side,
    )
    event = await build_order_event(order, wallet)
    await app.state.ws_manager.broadcast_to_user(payload.user_id, event)
    return order


@app.get("/portfolio/{user_id}", response_model=list[PortfolioItemResponse])
async def get_portfolio(
    user_id: int,
    db: Session = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    positions = (
        db.query(Position)
        .filter(Position.user_id == user_id)
        .order_by(Position.symbol.asc())
        .all()
    )
    portfolio: list[PortfolioItemResponse] = []
    for position in positions:
        current_price = await get_live_price(redis, position.symbol)
        unrealized_pnl = quantize_money(
            (current_price - position.average_price) * position.quantity
        )
        portfolio.append(
            PortfolioItemResponse(
                symbol=position.symbol,
                quantity=position.quantity,
                average_price=quantize_money(position.average_price),
                current_price=current_price,
                unrealized_pnl=unrealized_pnl,
            )
        )
    return portfolio


@app.get("/orders/{user_id}", response_model=list[OrderResponse])
def get_order_history(user_id: int, db: Session = Depends(get_db)) -> list[Order]:
    return (
        db.query(Order)
        .filter(Order.user_id == user_id)
        .order_by(Order.created_at.desc(), Order.id.desc())
        .all()
    )


@app.get("/market/prices", response_model=list[MarketPriceResponse])
async def get_market_prices(redis: Redis = Depends(get_redis)) -> list[MarketPriceResponse]:
    prices: list[MarketPriceResponse] = []
    for symbol in settings.tracked_symbols:
        prices.append(
            MarketPriceResponse(
                symbol=symbol,
                price=await get_live_price(redis, symbol),
            )
        )
    return prices


@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: int):
    manager: WebSocketManager = websocket.app.state.ws_manager
    await manager.connect(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(user_id, websocket)
