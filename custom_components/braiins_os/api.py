"""Async client for the Braiins OS Public REST API (/api/v1)."""
from __future__ import annotations

import asyncio
import time
from typing import Any

import aiohttp


class BraiinsApiError(Exception):
    """Communication error."""


class BraiinsAuthError(BraiinsApiError):
    """Bad or rejected credentials."""


def dig(data: Any, *keys: str) -> Any:
    """Safely walk nested dicts; returns None if any key is missing."""
    for key in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


class BraiinsClient:
    """REST client with automatic token handling.

    The token is refreshed (a) proactively at 90 % of the lifetime the miner
    reports in `timeout_s`, and (b) reactively when a request gets 401/403.
    """

    def __init__(self, session: aiohttp.ClientSession, host: str, port: int,
                 username: str, password: str) -> None:
        self._session = session
        self._base = f"http://{host}:{port}/api/v1"
        self._username = username
        self._password = password
        self._token: str | None = None
        self._expires: float | None = None
        self._lock = asyncio.Lock()
        self._timeout = aiohttp.ClientTimeout(total=10)

    async def _login(self) -> None:
        async with self._session.post(
            f"{self._base}/auth/login",
            json={"username": self._username, "password": self._password},
            timeout=self._timeout,
        ) as resp:
            if resp.status in (400, 401, 403):
                raise BraiinsAuthError("Login rejected")
            resp.raise_for_status()
            body = await resp.json(content_type=None)
        self._token = body["token"]
        lifetime = body.get("timeout_s") or 0
        self._expires = time.monotonic() + lifetime * 0.9 if lifetime > 0 else None

    async def _ensure_token(self, stale: str | None = None) -> str:
        """Return a valid token, logging in if missing, expired or known-stale."""
        async with self._lock:
            expired = self._expires is not None and time.monotonic() >= self._expires
            if self._token is None or expired or (stale is not None and self._token == stale):
                await self._login()
            return self._token  # type: ignore[return-value]

    async def request(self, method: str, path: str, json: Any = None) -> Any:
        try:
            token = await self._ensure_token()
            for attempt in (0, 1):
                async with self._session.request(
                    method, f"{self._base}/{path}", json=json,
                    headers={"Authorization": token}, timeout=self._timeout,
                ) as resp:
                    if resp.status in (401, 403):
                        if attempt == 0:
                            token = await self._ensure_token(stale=token)
                            continue
                        raise BraiinsAuthError("Unauthorized")
                    resp.raise_for_status()
                    if resp.status == 204:
                        return None
                    return await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise BraiinsApiError(f"Error talking to miner: {err}") from err
