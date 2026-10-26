import time
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

from app.config import get_settings
from app.exceptions import AuthenticationError
from app.middleware.auth import require_clerk_user
from app.models.user import User


@pytest.fixture(scope="module")
def rsa_keys():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("utf-8")
    pub_pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    # A second key to test forged tokens signed with an untrusted key
    forged_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged_priv_pem = forged_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("utf-8")

    return {
        "priv": priv_pem,
        "pub": pub_pem,
        "forged_priv": forged_priv_pem,
    }


def make_token(payload: dict, priv_key: str) -> str:
    return jwt.encode(payload, priv_key, algorithm="RS256")


@pytest.mark.asyncio
async def test_clerk_jwt_valid_with_pinned_issuer(rsa_keys):
    settings = get_settings()
    issuer = "https://clerk.agentlens.dev"
    token = make_token(
        {
            "sub": "user_clerk_123",
            "iss": issuer,
            "exp": int(time.time()) + 3600,
            "email": "test@example.com",
            "name": "Test User",
        },
        rsa_keys["priv"],
    )

    mock_db = AsyncMock()
    mock_result = MagicMock()
    fake_user = User(clerk_id="user_clerk_123", email="test@example.com", name="Test User")
    mock_result.scalar_one.return_value = fake_user
    mock_db.execute = AsyncMock(return_value=mock_result)

    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    with patch.object(settings, "local_mode", False), \
         patch.object(settings, "clerk_issuer", issuer), \
         patch("app.middleware.auth._get_jwks", new=AsyncMock(return_value=rsa_keys["pub"])):
        user = await require_clerk_user(credentials=credentials, db=mock_db)
        assert user.clerk_id == "user_clerk_123"


@pytest.mark.asyncio
async def test_clerk_jwt_wrong_issuer_rejected(rsa_keys):
    settings = get_settings()
    configured_issuer = "https://clerk.agentlens.dev"
    wrong_issuer = "https://attacker-clerk.malicious.com"
    token = make_token(
        {
            "sub": "user_clerk_123",
            "iss": wrong_issuer,
            "exp": int(time.time()) + 3600,
        },
        rsa_keys["priv"],
    )

    mock_db = AsyncMock()
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    with patch.object(settings, "local_mode", False), \
         patch.object(settings, "clerk_issuer", configured_issuer), \
         patch("app.middleware.auth._get_jwks", new=AsyncMock(return_value=rsa_keys["pub"])):
        with pytest.raises(AuthenticationError, match="Invalid or expired token"):
            await require_clerk_user(credentials=credentials, db=mock_db)


@pytest.mark.asyncio
async def test_clerk_jwt_missing_issuer_rejected(rsa_keys):
    settings = get_settings()
    configured_issuer = "https://clerk.agentlens.dev"
    token = make_token(
        {
            "sub": "user_clerk_123",
            "exp": int(time.time()) + 3600,
        },
        rsa_keys["priv"],
    )

    mock_db = AsyncMock()
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    with patch.object(settings, "local_mode", False), \
         patch.object(settings, "clerk_issuer", configured_issuer), \
         patch("app.middleware.auth._get_jwks", new=AsyncMock(return_value=rsa_keys["pub"])):
        with pytest.raises(AuthenticationError, match="Invalid or expired token"):
            await require_clerk_user(credentials=credentials, db=mock_db)


@pytest.mark.asyncio
async def test_clerk_jwt_expired_token_rejected(rsa_keys):
    settings = get_settings()
    issuer = "https://clerk.agentlens.dev"
    token = make_token(
        {
            "sub": "user_clerk_123",
            "iss": issuer,
            "exp": int(time.time()) - 100,  # in the past
        },
        rsa_keys["priv"],
    )

    mock_db = AsyncMock()
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    with patch.object(settings, "local_mode", False), \
         patch.object(settings, "clerk_issuer", issuer), \
         patch("app.middleware.auth._get_jwks", new=AsyncMock(return_value=rsa_keys["pub"])):
        with pytest.raises(AuthenticationError, match="Invalid or expired token"):
            await require_clerk_user(credentials=credentials, db=mock_db)


@pytest.mark.asyncio
async def test_clerk_jwt_forged_signature_rejected(rsa_keys):
    settings = get_settings()
    issuer = "https://clerk.agentlens.dev"
    # Signed with an untrusted private key
    token = make_token(
        {
            "sub": "user_clerk_123",
            "iss": issuer,
            "exp": int(time.time()) + 3600,
        },
        rsa_keys["forged_priv"],
    )

    mock_db = AsyncMock()
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    with patch.object(settings, "local_mode", False), \
         patch.object(settings, "clerk_issuer", issuer), \
         patch("app.middleware.auth._get_jwks", new=AsyncMock(return_value=rsa_keys["pub"])):
        with pytest.raises(AuthenticationError, match="Invalid or expired token"):
            await require_clerk_user(credentials=credentials, db=mock_db)


@pytest.mark.asyncio
async def test_clerk_jwt_missing_sub_rejected(rsa_keys):
    settings = get_settings()
    issuer = "https://clerk.agentlens.dev"
    token = make_token(
        {
            "iss": issuer,
            "exp": int(time.time()) + 3600,
            # no "sub"
        },
        rsa_keys["priv"],
    )

    mock_db = AsyncMock()
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    with patch.object(settings, "local_mode", False), \
         patch.object(settings, "clerk_issuer", issuer), \
         patch("app.middleware.auth._get_jwks", new=AsyncMock(return_value=rsa_keys["pub"])):
        with pytest.raises(AuthenticationError, match="JWT missing 'sub' claim"):
            await require_clerk_user(credentials=credentials, db=mock_db)


@pytest.mark.asyncio
async def test_clerk_jwt_missing_authorization_header():
    mock_db = AsyncMock()
    with patch("app.config.get_settings") as mock_settings:
        mock_settings.return_value.local_mode = False
        with pytest.raises(AuthenticationError, match="Missing Authorization header"):
            await require_clerk_user(credentials=None, db=mock_db)
