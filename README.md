# Trading System Backend

Mini trading backend built with FastAPI, MySQL, Redis, WebSockets, and a basic built-in frontend for the interview assignment.

## Features

- Create users and auto-provision wallets with `₹10,00,000`
- Mock live market prices stored in Redis and updated every second
- Execute market `BUY` and `SELL` orders instantly
- Maintain positions with average price tracking
- Return portfolio with current price and unrealized PnL
- Return order history per user
- Push order execution events over WebSocket
- Serve a basic frontend dashboard from `/`

## Architecture

- FastAPI serves REST APIs and the WebSocket endpoint.
- FastAPI also serves a lightweight static frontend for demo and submission purposes.
- MySQL stores durable entities: users, wallets, positions, and orders.
- Redis stores live prices under keys like `price:SBIN`.
- A background task updates prices every second using a bounded random walk.
- Orders are executed immediately at the latest Redis price and persisted in MySQL.
- A lightweight WebSocket manager pushes order execution updates to connected users.

## Project Structure

```text
app/
  config.py
  database.py
  dependencies.py
  main.py
  market_data.py
  models.py
  schemas.py
  static/
  services.py
  websocket_manager.py
docker-compose.yml
Dockerfile
requirements.txt
```

## Setup

1. Copy the environment file:

```bash
cp .env.example .env
```

2. Start the stack:

```bash
docker compose up --build
```

3. Open the API docs:

- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- Frontend dashboard: [http://localhost:8000/](http://localhost:8000/)

## Run Without Docker

Use Python `3.12` or `3.13`.

1. Create and activate a virtual environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set local environment variables in `.env`:

```env
APP_NAME=Trading System API
DEBUG=false
DATABASE_URL=mysql+pymysql://trader:trader@localhost:3306/trading_system
REDIS_URL=redis://localhost:6379/0
```

4. Start the app:

```bash
python run.py
```

## Deploy

Recommended platform: Railway, because its official templates support FastAPI app services plus MySQL and Redis in the same project.

### Railway deploy steps

1. Push this project to a GitHub repository.
2. Create a new Railway project.
3. Add a `MySQL` service from Railway's database templates.
4. Add a `Redis` service from Railway's database templates.
5. Add a new app service and connect your GitHub repository.
6. Railway will detect the `Dockerfile` and build the API service automatically.
7. In the API service variables, add:

```env
APP_NAME=Trading System API
DEBUG=false
DATABASE_URL=${{MySQL.MYSQL_URL}}
REDIS_URL=${{Redis.REDIS_URL}}
```

8. Deploy the staged changes.
9. Open the generated Railway domain for the API service.

### Notes for Railway

- The app already exposes `/health`, `/docs`, and `/` for health checks and demos.
- The Dockerfile now uses `${PORT}` automatically, which Railway requires for web services.
- If you prefer, you can skip `DATABASE_URL` and instead map `MYSQLHOST`, `MYSQLPORT`, `MYSQLUSER`, `MYSQLPASSWORD`, and `MYSQLDATABASE`; the app supports those Railway-style variables too.

## Local Python Runtime

- Recommended local runtime: Python `3.12` or `3.13`
- Python `3.14` may fail while installing `pydantic-core` depending on your machine setup

## API Summary

### Create User

```http
POST /users
```

```json
{
  "name": "Manali",
  "email": "manali@example.com"
}
```

### Place Order

```http
POST /orders
```

```json
{
  "user_id": 1,
  "symbol": "SBIN",
  "qty": 10,
  "side": "BUY"
}
```

### Portfolio

```http
GET /portfolio/1
```

### Current User Details

```http
GET /users/1
```

### Order History

```http
GET /orders/1
```

### Market Prices

```http
GET /market/prices
```

### WebSocket

```text
ws://localhost:8000/ws/1
```

Order execution event payload:

```json
{
  "event": "order_executed",
  "symbol": "SBIN",
  "qty": 10,
  "side": "BUY",
  "price": 820.50,
  "status": "COMPLETED",
  "wallet_balance": 991795.00
}
```

## Notes

- The service initializes prices for `SBIN`, `RELIANCE`, `TCS`, `INFY`, and `HDFCBANK`.
- Prices are read from Redis only, as required by the assignment.
- Orders are treated as market orders and always execute instantly.
- Wallet balance and positions are updated in the same database transaction.
- The frontend uses the same APIs plus a WebSocket connection for real-time order updates.

## Postman

Import the bundled collection:

- `postman_collection.json`
