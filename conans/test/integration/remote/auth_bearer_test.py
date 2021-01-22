import unittest

from bottle import request
from parameterized.parameterized import parameterized
import pytest

from conans.test.utils.tools import TestClient, TestServer
from conans.util.env_reader import get_env
from conans.util.files import save

conanfile = """
from conans import ConanFile

class OpenSSLConan(ConanFile):
    name = "Hello"
    version = "0.1"
"""


class AuthorizationHeaderSpy(object):
    """ Generic plugin to handle Authorization header. Must be extended and implement
    some abstract methods in subclasses"""

    name = 'authorizationheaderspy'
    api = 2

    def __init__(self):
        self.auths = []

    def apply(self, callback, context):  # @UnusedVariable
        auth = request.headers.get("Authorization")
        name = callback.__name__
        self.auths.append((name, auth))
        return callback


class ReturnHandlerPlugin(object):

    name = 'ReturnHandlerPluginSpy'
    api = 2

    def apply(self, callback, _):
        """Apply plugin"""
        def wrapper(*args, **kwargs):
            """Capture possible exceptions to manage the return"""
            result = callback(*args, **kwargs)
            if isinstance(result, dict):
                for k, v in result.items():
                    result[k] = v.split("?signature=")[0]
            return result
        return wrapper


class AuthorizeBearerTest(unittest.TestCase):

    @parameterized.expand([(False, ), (True, )])
    def test_basic(self, artifacts_properties):
        auth = AuthorizationHeaderSpy()
        server = TestServer(plugins=[auth])
        servers = {"default": server}
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        if artifacts_properties:
            save(client.cache.artifacts_properties_path, "key=value")
        client.save({"conanfile.py": conanfile})
        client.run("export . lasote/stable")
        errors = client.run("upload Hello/0.1@lasote/stable")
        self.assertFalse(errors)

        if not client.cache.config.revisions_enabled:
            expected_calls = [('ping', None),
                              ('get_recipe_manifest_url', None),
                              ('check_credentials', None),
                              ('authenticate', 'Basic'),
                              ('get_recipe_snapshot', 'Bearer'),
                              ('get_conanfile_upload_urls', 'Bearer'),
                              ('put', None)]
        else:
            expected_calls = [('ping', None),
                              ('get_recipe_file', None),
                              ('check_credentials', None),
                              ('authenticate', 'Basic'),
                              ('get_recipe_file_list', 'Bearer'),
                              ('upload_recipe_file', 'Bearer')]

        self.assertEqual(len(expected_calls), len(auth.auths))
        for i, (method, auth_type) in enumerate(expected_calls):
            real_call = auth.auths[i]
            self.assertEqual(method, real_call[0])
            if auth_type:
                self.assertIn(auth_type, real_call[1])

    @parameterized.expand([(False,), (True,)])
    @pytest.mark.skipif(get_env("TESTING_REVISIONS_ENABLED", False), reason="ApiV1 test")
    def test_no_signature(self, artifacts_properties):
        auth = AuthorizationHeaderSpy()
        retur = ReturnHandlerPlugin()
        server = TestServer(plugins=[auth, retur])
        servers = {"default": server}
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        if artifacts_properties:
            save(client.cache.artifacts_properties_path, "key=value")
        client.save({"conanfile.py": conanfile})
        client.run("export . lasote/stable")
        # Upload will fail, as conan_server is expecting a signed URL
        errors = client.run("upload Hello/0.1@lasote/stable", assert_error=True)
        self.assertTrue(errors)

        expected_calls = [('ping', None),
                          ('get_recipe_manifest_url', None),
                          ('check_credentials', None),
                          ('authenticate', 'Basic'),
                          ('get_recipe_snapshot', 'Bearer'),
                          ('get_conanfile_upload_urls', 'Bearer'),
                          ('put', 'Bearer')]

        self.assertEqual(len(expected_calls), len(auth.auths))
        for i, (method, auth_type) in enumerate(expected_calls):
            real_call = auth.auths[i]
            self.assertEqual(method, real_call[0])
            if auth_type:
                self.assertIn(auth_type, real_call[1])

        # The Bearer of the last two calls must be identical
        self.assertEqual(auth.auths[-1][1], auth.auths[-2][1])
