"""Role-based auth: CSV user registry + in-memory bearer tokens.

The registry is a plain CSV (``users.csv`` at the project root) with columns
``username,name,role,salt,password_hash``. Passwords are hashed with PBKDF2
(stdlib only - no new dependencies). On first run the file is seeded with two
demo accounts; add more with the CLI:

    python -m src.api.auth add <username> <role> [--name NAME] [--password PASS]
    python -m src.api.auth list

Tokens are random hex strings kept in memory (like the API's conversation
sessions), so they are lost on restart - clients must re-login, which also
invalidates any old token.

FastAPI dependencies live here too:

    user = Depends(get_current_user)              # 401 when unauthenticated
    user = Depends(require_role("doctor"))        # 403 when wrong role
"""

import argparse
import csv
import getpass
import hashlib
import hmac
import logging
import secrets
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from fastapi import Depends, HTTPException, Request

from src import config

logger = logging.getLogger("clinical_rag.auth")

PBKDF2_ITERATIONS = 100_000

# Seeded on first run when users.csv is missing (see ensure_users_csv).
DEMO_USERS = [
    {
        "username": "doctor",
        "name": "Dr. Demo",
        "role": "doctor",
        "password": "doctor123",
    },
    {
        "username": "patient",
        "name": "Pat Demo",
        "role": "patient",
        "password": "patient123",
    },
]

ROLES = ("doctor", "patient")

CSV_HEADER = ["username", "name", "role", "salt", "password_hash"]


@dataclass
class User:
    """An authenticated identity, attached to requests via dependencies."""

    username: str
    role: str  # "doctor" | "patient"
    name: str


import json

TOKENS_FILE = config.USERS_CSV_PATH.parent / ".tokens_registry.json"


def _load_tokens_file() -> dict[str, dict]:
    if TOKENS_FILE.exists():
        try:
            with TOKENS_FILE.open("r") as fh:
                return json.load(fh)
        except Exception:
            return {}
    return {}


def _save_tokens_file() -> None:
    try:
        with TOKENS_FILE.open("w") as fh:
            json.dump(_TOKENS, fh)
    except Exception:
        pass


_TOKENS: dict[str, dict] = _load_tokens_file()


# ---------------------------------------------------------------------------
# Bearer tokens (persisted across restarts)
# ---------------------------------------------------------------------------


def create_token(user: User) -> str:
    """Issue a new random bearer token for a user."""
    token = secrets.token_hex(32)
    _TOKENS[token] = {
        "username": user.username,
        "role": user.role,
        "name": user.name,
        "created_at": time.time(),
    }
    _save_tokens_file()
    return token


def resolve_token(token: str) -> User | None:
    """Map a token back to its user; None if unknown or expired."""
    record = _TOKENS.get(token)
    if record is None:
        disk_tokens = _load_tokens_file()
        _TOKENS.update(disk_tokens)
        record = _TOKENS.get(token)

    if record is None:
        return None
    if config.TOKEN_TTL_SECONDS > 0:
        if time.time() - record["created_at"] > config.TOKEN_TTL_SECONDS:
            _TOKENS.pop(token, None)
            _save_tokens_file()
            return None
    return User(
        username=record["username"], role=record["role"], name=record["name"]
    )


def revoke_token(token: str) -> bool:
    """Invalidate a token; False if it was not valid."""
    removed = _TOKENS.pop(token, None) is not None
    if removed:
        _save_tokens_file()
    return removed


# ---------------------------------------------------------------------------
# CSV registry
# ---------------------------------------------------------------------------


def ensure_users_csv() -> Path:
    """Create users.csv with the demo accounts if it does not exist.

    Idempotent - never overwrites an existing registry.
    """
    path = config.USERS_CSV_PATH
    if path.exists():
        return path
    logger.info("seeding demo users into %s", path)
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_HEADER)
        writer.writeheader()
        for user in DEMO_USERS:
            salt, pw_hash = hash_password(user["password"])
            writer.writerow(
                {
                    "username": user["username"],
                    "name": user["name"],
                    "role": user["role"],
                    "salt": salt,
                    "password_hash": pw_hash,
                }
            )
    return path


def load_users() -> dict[str, dict]:
    """Read the registry: username -> {"name", "role", "salt", "password_hash"}.

    Reads the file fresh on every call so CLI-added users are picked up
    without a server restart. Malformed lines are skipped with a warning.
    """
    path = config.USERS_CSV_PATH
    users: dict[str, dict] = {}
    if not path.exists():
        logger.warning("users registry missing at %s", path)
        return users
    with path.open(newline="") as fh:
        for lineno, row in enumerate(csv.DictReader(fh), start=2):
            if row.get("username") in (None, ""):
                logger.warning("users.csv:%d skipped (empty username)", lineno)
                continue
            if not all(row.get(col) for col in CSV_HEADER[1:]):
                logger.warning("users.csv:%d skipped (malformed row)", lineno)
                continue
            users[row["username"]] = {
                "name": row["name"],
                "role": row["role"],
                "salt": row["salt"],
                "password_hash": row["password_hash"],
            }
    return users


def add_user(username: str, role: str, name: str, password: str) -> None:
    """Append one user to the registry (creating it if needed)."""
    if role not in ROLES:
        raise ValueError(f"role must be one of {', '.join(ROLES)}")
    if not username.strip():
        raise ValueError("username must not be empty")
    users = load_users()
    if username in users:
        raise ValueError(f"user {username!r} already exists")
    salt, pw_hash = hash_password(password)
    with config.USERS_CSV_PATH.open("a", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_HEADER)
        if config.USERS_CSV_PATH.stat().st_size == 0:
            writer.writeheader()
        writer.writerow(
            {
                "username": username,
                "name": name,
                "role": role,
                "salt": salt,
                "password_hash": pw_hash,
            }
        )


# ---------------------------------------------------------------------------
# Password hashing (PBKDF2, stdlib only)
# ---------------------------------------------------------------------------


def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    """Return (salt_hex, password_hash_hex) for a plaintext password."""
    if salt is None:
        salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt, PBKDF2_ITERATIONS
    )
    return salt.hex(), digest.hex()


def verify_password(password: str, salt_hex: str, hash_hex: str) -> bool:
    """Constant-time check of a plaintext password against stored values."""
    salt = bytes.fromhex(salt_hex)
    expected = bytes.fromhex(hash_hex)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt, PBKDF2_ITERATIONS
    )
    return hmac.compare_digest(digest, expected)


def authenticate(username: str, password: str) -> User | None:
    """Verify credentials against the CSV registry.

    Returns None for BOTH unknown users and wrong passwords, so the login
    endpoint cannot be used to enumerate which usernames exist.
    """
    record = load_users().get(username)
    if record is None:
        return None
    if not verify_password(password, record["salt"], record["password_hash"]):
        return None
    return User(username=username, role=record["role"], name=record["name"])


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------


def get_current_user(request: Request) -> User:
    """Dependency: the authenticated user, or 401.

    Requires an ``Authorization: Bearer <token>`` header with a valid token.
    """
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = resolve_token(header[len("Bearer "):].strip())
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_role(*roles: str):
    """Dependency factory: user must have one of the given roles.

    401 when unauthenticated, 403 when authenticated as the wrong role.
    """

    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Requires role: {', '.join(roles)}",
            )
        return user

    return dependency


# ---------------------------------------------------------------------------
# CLI: python -m src.api.auth add <username> <role> [--name NAME] [--password PASS]
#      python -m src.api.auth list
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.api.auth", description="Manage the users.csv registry"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    add_p = sub.add_parser("add", help="Add a user (prompts for a password)")
    add_p.add_argument("username")
    add_p.add_argument("role", choices=ROLES)
    add_p.add_argument("--name", default="")
    add_p.add_argument("--password", help="Use this password instead of prompting")

    sub.add_parser("list", help="List users (never shows password hashes)")

    args = parser.parse_args(argv)

    if args.command == "list":
        users = load_users()
        if not users:
            print(f"no users - registry missing/empty at {config.USERS_CSV_PATH}")
            return 1
        print(f"{'username':<12} {'role':<9} name")
        for username, record in sorted(users.items()):
            print(f"{username:<12} {record['role']:<9} {record['name']}")
        return 0

    password = args.password or getpass.getpass("Password: ")
    name = args.name or args.username
    try:
        ensure_users_csv()
        add_user(args.username, args.role, name, password)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"added {args.username} ({args.role})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
