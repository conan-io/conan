from datetime import timedelta

import jwt
import pytest
from jwt import DecodeError

from conans.server.crypto.jwt.jwt_credentials_manager import JWTCredentialsManager


def test_jwt_manager():
    # Instance the manager to generate tokens that expire in 1 minute
    manager = JWTCredentialsManager(secret="1234asdf" * 4, expire_time=timedelta(minutes=1))

    # Encrypt a profile
    token = manager.get_token_for("myuser")

    # Decrypt the profile
    assert "myuser" == manager.get_user(token)
    with pytest.raises(DecodeError):
        manager.get_user("invalid_user")

    # A token that expired 2 seconds ago is not valid, without waiting for the above to expire
    expired_manager = JWTCredentialsManager(secret="1234asdf" * 4,
                                            expire_time=timedelta(seconds=-2))
    expired_token = expired_manager.get_token_for("myuser")
    with pytest.raises(jwt.ExpiredSignatureError):
        manager.get_user(expired_token)
