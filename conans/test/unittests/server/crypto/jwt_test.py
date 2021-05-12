import time
import unittest
from datetime import timedelta

import jwt
from jwt import DecodeError

from conans.server.crypto.jwt.jwt_credentials_manager import JWTCredentialsManager
from conans.server.crypto.jwt.jwt_manager import JWTManager


class JwtTest(unittest.TestCase):

    def setUp(self):
        unittest.TestCase.setUp(self)
        self.secret = "123123123qweqwe"
        self.expire_time = timedelta(seconds=1)  # No lower resolution available

    def test_jwt_manager(self):
        # Instance the manager to generate tokens that expires in 10 ms

        manager = JWTManager(self.secret, self.expire_time)

        # Encrypt a profile
        profile = {"hello": "world"}
        token = manager.get_token_for(profile)

        # Decrypt the profile
        decrypted_profile = manager.get_profile(token)
        self.assertEqual(profile, decrypted_profile)

        # Now wait 2 seconds and check if its valid now
        time.sleep(2)
        self.assertRaises(jwt.ExpiredSignatureError, manager.get_profile, token)

    def test_jwt_credentials_manager(self):
        manager = JWTCredentialsManager(self.secret, self.expire_time)
        token = manager.get_token_for("lasote")
        self.assertEqual(manager.get_user(token), "lasote")
        self.assertRaises(DecodeError, manager.get_user, "invalid_user")
