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

    forged_pub_pem = forged_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    from jose import jwk
    key_dict = jwk.RSAKey(pub_pem, "RS256").to_dict()
    key_dict["kid"] = "key_v1"

    forged_key_dict = jwk.RSAKey(forged_pub_pem, "RS256").to_dict()
    forged_key_dict["kid"] = "forged_key"

    return {
        "priv": priv_pem,
        "pub": pub_pem,
        "jwk": key_dict,
        "forged_priv": forged_priv_pem,
        "forged_pub": forged_pub_pem,
        "forged_jwk": forged_key_dict,
    }


def make_token(payload: dict, priv_key: str, headers: dict | None = None) -> str:
    return jwt.encode(payload, priv_key, algorithm="RS256", headers=headers)


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


@pytest.mark.asyncio
async def test_clerk_jwt_invalid_token_does_not_fetch_jwks_again(rsa_keys):
    """Ordinary invalid tokens (expired, wrong issuer, forged with known kid, or malformed)
    must NOT trigger a forced JWKS refresh."""
    settings = get_settings()
    issuer = "https://clerk.agentlens.dev"
    mock_db = AsyncMock()

    # 1. Expired token
    expired_token = make_token(
        {"sub": "user_123", "iss": issuer, "exp": int(time.time()) - 50},
        rsa_keys["priv"],
        headers={"kid": "key_v1"},
    )
    # 2. Wrong issuer token
    wrong_iss_token = make_token(
        {"sub": "user_123", "iss": "https://wrong.issuer", "exp": int(time.time()) + 3600},
        rsa_keys["priv"],
        headers={"kid": "key_v1"},
    )
    # 3. Forged token with known kid
    forged_token = make_token(
        {"sub": "user_123", "iss": issuer, "exp": int(time.time()) + 3600},
        rsa_keys["forged_priv"],
        headers={"kid": "key_v1"},
    )
    # 4. Malformed token
    malformed_token = "malformed.token.string"

    mock_get_jwks = AsyncMock(return_value={"keys": [rsa_keys["jwk"]]})

    with patch.object(settings, "local_mode", False), \
         patch.object(settings, "clerk_issuer", issuer), \
         patch("app.middleware.auth._get_jwks", new=mock_get_jwks):

        for bad_token in [expired_token, wrong_iss_token, forged_token, malformed_token]:
            mock_get_jwks.reset_mock()
            creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=bad_token)
            with pytest.raises(AuthenticationError):
                await require_clerk_user(credentials=creds, db=mock_db)

            # mock_get_jwks should be called at most once (initial fetch), NEVER with force=True!
            assert mock_get_jwks.call_count == 1
            mock_get_jwks.assert_called_once_with()


@pytest.mark.asyncio
async def test_clerk_jwt_key_rotation_refreshes_and_succeeds(rsa_keys):
    """When a token presents an unknown kid, JWKS is refreshed with force=True and retry succeeds."""
    settings = get_settings()
    issuer = "https://clerk.agentlens.dev"

    # Token signed with key_v1, presenting kid "key_v1"
    token_v1 = make_token(
        {
            "sub": "user_clerk_v1",
            "iss": issuer,
            "exp": int(time.time()) + 3600,
            "email": "v1@example.com",
            "name": "V1 User",
        },
        rsa_keys["priv"],
        headers={"kid": "key_v1"},
    )

    mock_db = AsyncMock()
    mock_result = MagicMock()
    fake_user = User(clerk_id="user_clerk_v1", email="v1@example.com", name="V1 User")
    mock_result.scalar_one.return_value = fake_user
    mock_db.execute = AsyncMock(return_value=mock_result)

    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token_v1)

    call_count = 0
    async def mock_get_jwks_rot(force: bool = False):
        nonlocal call_count
        call_count += 1
        if force:
            # Rotated JWKS now contains key_v1
            return {"keys": [rsa_keys["jwk"]]}
        # Initial cached JWKS only has forged_key
        return {"keys": [rsa_keys["forged_jwk"]]}

    with patch.object(settings, "local_mode", False), \
         patch.object(settings, "clerk_issuer", issuer), \
         patch("app.middleware.auth._get_jwks", side_effect=mock_get_jwks_rot):
        user = await require_clerk_user(credentials=credentials, db=mock_db)
        assert user.clerk_id == "user_clerk_v1"
        # Initial call (without force) + key rotation retry (with force=True)
        assert call_count == 2


@pytest.mark.asyncio
async def test_clerk_jwt_refresh_throttling_protects_against_amplification():
    """Rapid requests with unknown kids do not spam the upstream endpoint beyond the throttle window."""
    import app.middleware.auth as auth_mod

    # Set up cached state as recently refreshed
    auth_mod._jwks_cache = {"keys": [{"kid": "initial_key"}]}
    auth_mod._jwks_fetched_at = time.monotonic()
    auth_mod._jwks_last_refreshed_at = time.monotonic()

    with patch("httpx.AsyncClient.get") as mock_get:
        # Call with force=True inside the 10-second window
        res = await auth_mod._get_jwks(force=True)
        # Outbound HTTP call must NOT be triggered
        mock_get.assert_not_called()
        assert res == {"keys": [{"kid": "initial_key"}]}

