"""Administrator bootstrap and token login endpoints."""

import hmac

from app.config import settings
from app.database import get_db
from app.middleware.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    require_admin,
    verify_password,
)
from app.middleware.rate_limit import get_client_ip, login_rate_limiter
from app.models.user import User
from app.schemas.auth import BootstrapRequest, LoginRequest, TokenResponse, UserResponse
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["Authentication"])


@router.post("/auth/bootstrap", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def bootstrap_admin(payload: BootstrapRequest, db: AsyncSession = Depends(get_db)):
    """Create the only initial administrator; disabled after the first user exists."""
    if not settings.BOOTSTRAP_TOKEN or not hmac.compare_digest(payload.bootstrap_token, settings.BOOTSTRAP_TOKEN):
        raise HTTPException(status_code=403, detail="Invalid bootstrap token")
    user_count = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    if user_count:
        raise HTTPException(status_code=409, detail="Bootstrap is disabled after the first user is created")
    user = User(email=str(payload.email).lower(), password_hash=hash_password(payload.password), full_name=payload.full_name, role="admin")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/auth/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    client_ip = get_client_ip(request)
    await login_rate_limiter.check(client_ip)
    user = (await db.execute(select(User).where(User.email == str(payload.email).lower()))).scalar_one_or_none()
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    access_token = create_access_token(user)
    response.set_cookie(
        key="eggvision_access_token",
        value=access_token,
        httponly=True,
        secure=settings.APP_ENV.lower() == "production",
        # Browser clients send the bearer token held in session storage for
        # cross-origin API requests. Keeping the cookie Lax avoids using the
        # cookie as a cross-site state-changing credential.
        samesite="lax",
        max_age=settings.JWT_EXPIRY_MINUTES * 60,
    )
    return TokenResponse(access_token=access_token)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response):
    """Clear the optional browser session cookie as well as client token storage."""
    response.delete_cookie(
        key="eggvision_access_token",
        httponly=True,
        secure=settings.APP_ENV.lower() == "production",
        samesite="lax",
    )


@router.get("/auth/me", response_model=UserResponse)
async def me(current_user: User | None = Depends(get_current_user)):
    if current_user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication is disabled for local development")
    return current_user


@router.get("/admin/users", response_model=list[UserResponse])
async def list_users(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve user directory. Strictly requires administrator role."""
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return list(result.scalars().all())
