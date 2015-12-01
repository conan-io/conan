import unittest
from conans.server.crypto.jwt.jwt_credentials_manager import JWTCredentialsManager
from conans.server.crypto.jwt.jwt_manager import JWTManager
from datetime import timedelta
import time
import jwt
from jwt import DecodeError


class JwtTest(unittest.TestCase):

    def setUp(self):
        unittest.TestCase.setUp(self)
        self.secret = "123123123qweqwe"
        self.expire_time = timedelta(seconds=1)  # No lower resolution available

    def jwt_manager_test(self):
        # Instance the manager to generate tokens that expires in 10 ms

        manager = JWTManager(self.secret, self.expire_time)

        # Encrypt a profile
        profile = {"hello": "world"}
        token = manager.get_token_for(profile)

        # Decrypt the profile
        decrypted_profile = manager.get_profile(token)
        self.assertEquals(profile, decrypted_profile)

        # Now wait 2 seconds and check if its valid now
        time.sleep(2)
        self.assertRaises(jwt.ExpiredSignature, manager.get_profile, token)

    def jwt_credentials_manager_test(self):
        manager = JWTCredentialsManager(self.secret, self.expire_time)
        token = manager.get_token_for("lasote")
        self.assertEquals(manager.get_user(token), "lasote")
        self.assertRaises(DecodeError, manager.get_user, "invalid_user")
