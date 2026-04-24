from __future__ import annotations

from typing import Self

from functools import lru_cache

from pydantic import Field
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Trading System API"
    debug: bool = False
    database_url: str | None = None
    redis_url: str | None = None
    mysqlhost: str | None = None
    mysqlport: int | None = None
    mysqluser: str | None = None
    mysqlpassword: str | None = None
    mysqldatabase: str | None = None
    redishost: str | None = None
    redisport: int | None = None
    redisuser: str | None = None
    redispassword: str | None = None
    starting_wallet_balance: float = 1_000_000.0
    tracked_symbols: list[str] = ["SBIN", "RELIANCE", "TCS", "INFY", "HDFCBANK"]
    price_update_interval_seconds: float = 1.0
    initial_symbol_prices: dict[str, float] = {
        "SBIN": 820.50,
        "RELIANCE": 2950.00,
        "TCS": 4035.15,
        "INFY": 1522.80,
        "HDFCBANK": 1688.25,
    }
    price_variation_ratio: float = 0.015
    dependency_retry_attempts: int = 30
    dependency_retry_delay_seconds: float = 2.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @model_validator(mode="after")
    def populate_connection_urls(self) -> Self:
        if not self.database_url:
            if self.mysqlhost and self.mysqluser and self.mysqldatabase:
                password = self.mysqlpassword or ""
                port = self.mysqlport or 3306
                self.database_url = (
                    f"mysql+pymysql://{self.mysqluser}:{password}"
                    f"@{self.mysqlhost}:{port}/{self.mysqldatabase}"
                )
            else:
                self.database_url = (
                    "mysql+pymysql://trader:trader@localhost:3306/trading_system"
                )
        elif self.database_url.startswith("mysql://"):
            self.database_url = self.database_url.replace(
                "mysql://", "mysql+pymysql://", 1
            )

        if not self.redis_url:
            if self.redishost:
                port = self.redisport or 6379
                if self.redispassword and self.redisuser:
                    self.redis_url = (
                        f"redis://{self.redisuser}:{self.redispassword}"
                        f"@{self.redishost}:{port}/0"
                    )
                elif self.redispassword:
                    self.redis_url = (
                        f"redis://default:{self.redispassword}@{self.redishost}:{port}/0"
                    )
                else:
                    self.redis_url = f"redis://{self.redishost}:{port}/0"
            else:
                self.redis_url = "redis://localhost:6379/0"
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
