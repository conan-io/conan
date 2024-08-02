import time
from datetime import timedelta

import jwt
import pytest
from jwt import DecodeError

from conans.server.crypto.jwt.jwt_credentials_manager import JWTCredentialsManager


def test_jwt_manager():
    # Instance the manager to generate tokens that expires in 10 ms
    manager = JWTCredentialsManager(secret="1234asdf", expire_time=timedelta(seconds=1))

    # Encrypt a profile
    token = manager.get_token_for("myuser")

    # Decrypt the profile
    assert "myuser" == manager.get_user(token)
    with pytest.raises(DecodeError):
        manager.get_user("invalid_user")

    # Now wait 2 seconds and check if its valid now
    time.sleep(2)
    with pytest.raises(jwt.ExpiredSignatureError):
        manager.get_user(token)
