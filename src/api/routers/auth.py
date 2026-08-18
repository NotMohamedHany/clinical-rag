"""Authentication API Router."""

import logging
from fastapi import APIRouter, Depends, HTTPException, Request

from src.api.auth import (
    User,
    add_user,
    authenticate,
    create_token,
    ensure_users_csv,
    load_users,
    require_role,
    revoke_token,
)
from src.api.schemas import (
    LoginRequest,
    LoginResponse,
    SignupRequest,
    UserListItem,
    UserProfileResponse,
)

logger = logging.getLogger("clinical_rag.api.auth")

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup", response_model=LoginResponse, summary="Sign up a new user")
def signup(payload: SignupRequest) -> LoginResponse:
    """Register a new user account and return an initial bearer token."""
    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username cannot be empty")

    name = payload.name.strip() or username
    role = payload.role.strip()

    ensure_users_csv()
    try:
        add_user(username=username, role=role, name=name, password=payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    logger.info("signup user=%s role=%s", username, role)
    user = User(username=username, role=role, name=name)
    token = create_token(user)
    return LoginResponse(
        token=token, username=user.username, role=user.role, name=user.name
    )


@router.post("/login", response_model=LoginResponse, summary="Log in user")
def login(payload: LoginRequest) -> LoginResponse:
    """Exchange credentials for a bearer token.

    Uniform HTTP 401 for unknown username or incorrect password.
    """
    user = authenticate(payload.username, payload.password)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    logger.info("login user=%s role=%s", user.username, user.role)
    token = create_token(user)
    return LoginResponse(
        token=token, username=user.username, role=user.role, name=user.name
    )


@router.post("/logout", summary="Log out user")
def logout(request: Request, user: User = Depends(require_role("doctor", "patient"))) -> dict:
    """Revoke the presented bearer token."""
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    revoke_token(token)
    logger.info("logout user=%s", user.username)
    return {"ok": True}


@router.get("/me", response_model=UserProfileResponse, summary="Get current user profile")
def get_me(user: User = Depends(require_role("doctor", "patient"))) -> UserProfileResponse:
    """Return profile info for the currently authenticated user."""
    return UserProfileResponse(
        username=user.username,
        role=user.role,
        name=user.name,
    )


@router.get("/users", response_model=list[UserListItem], summary="List registered users (doctor/admin restricted)")
def list_users(user: User = Depends(require_role("doctor"))) -> list[UserListItem]:
    """List all accounts in the registry (requires 'doctor' role)."""
    users = load_users()
    return [
        UserListItem(username=uname, role=rec["role"], name=rec["name"])
        for uname, rec in users.items()
    ]
