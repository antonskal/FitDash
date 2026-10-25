from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from garminconnect import GarminConnectAuthenticationError, GarminConnectConnectionError, GarminConnectTooManyRequestsError
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.api import deps
from app.garmin import GarminClient
from app.garmin.client import GarminNotAuthenticated

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=1)


class MfaRequest(BaseModel):
    code: str = Field(min_length=4, max_length=12)


@router.get("/status")
def status(client: GarminClient = Depends(deps.garmin)):
    return client.status().to_dict()


@router.post("/login")
async def login(body: LoginRequest, client: GarminClient = Depends(deps.garmin)):
    try:
        result = await run_in_threadpool(client.login, body.email.strip(), body.password)
    except GarminConnectTooManyRequestsError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except GarminConnectAuthenticationError as exc:
        raise HTTPException(status_code=401, detail=_clean(str(exc))) from exc
    except GarminConnectConnectionError as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach Garmin Connect: {exc}") from exc
    return result.to_dict()


@router.post("/mfa")
async def mfa(body: MfaRequest, client: GarminClient = Depends(deps.garmin)):
    try:
        result = await run_in_threadpool(client.submit_mfa, body.code)
    except GarminNotAuthenticated as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except GarminConnectAuthenticationError as exc:
        raise HTTPException(status_code=401, detail=_clean(str(exc))) from exc
    except GarminConnectConnectionError as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach Garmin Connect: {exc}") from exc
    return result.to_dict()


@router.post("/logout")
def logout(client: GarminClient = Depends(deps.garmin)):
    client.logout()
    return client.status().to_dict()


def _clean(msg: str) -> str:
    # garminconnect produces multi-line bullet lists; keep the first meaningful line.
    return msg.splitlines()[0] if msg else "Authentication failed"
