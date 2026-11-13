"""Bearer-token authentication used by protected API routes."""

import uuid
from datetime import UTC, datetime, timedelta

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.user import User
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select

password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_context.verify(password, password_hash)


def create_access_token(user: User) -> str:
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.JWT_EXPIRY_MINUTES)
    return jwt.encode(
        {"sub": str(user.id), "role": user.role, "exp": expires_at},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User | None:
    """Require an active user in production while allowing anonymous local development."""
    token = credentials.credentials if credentials else request.cookies.get("eggvision_access_token")
    if not token:
        if settings.AUTH_REQUIRED:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        return None
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id = uuid.UUID(payload["sub"])
    except (JWTError, KeyError, ValueError) as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token") from error
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account is unavailable")
    return user


def require_role(required_role: str):
    """Enforce server-side role check; requires active user with the specified role."""
    async def _role_checker(current_user: User | None = Depends(get_current_user)) -> User:
        if current_user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
        if current_user.role != required_role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient administrative permissions")
        return current_user
    return _role_checker


require_admin = require_role("admin")
