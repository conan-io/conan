import os
import unittest
from conans.test.utils.tools import TestServer, TestClient
from bottle import request

from conans.util.env_reader import get_env

conanfile = """
from conans import ConanFile

class OpenSSLConan(ConanFile):
    name = "Hello"
    version = "0.1"
"""


class AuthorizationHeaderSpy(object):
    ''' Generic plugin to handle Authorization header. Must be extended and implement
    some abstract methods in subclasses'''

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
        '''Apply plugin'''
        def wrapper(*args, **kwargs):
            '''Capture possible exceptions to manage the return'''
            result = callback(*args, **kwargs)
            if isinstance(result, dict):
                for k, v in result.items():
                    result[k] = v.split("?signature=")[0]
            return result
        return wrapper


class AuthorizeBearerTest(unittest.TestCase):

    def basic_test(self):
        auth = AuthorizationHeaderSpy()
        server = TestServer(plugins=[auth])
        servers = {"default": server}
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        client.save({"conanfile.py": conanfile})
        client.run("export . lasote/stable")
        errors = client.run("upload Hello/0.1@lasote/stable")
        self.assertFalse(errors)

        if not get_env("CONAN_TESTING_SERVER_V2_ENABLED", False):
            expected_calls = [('ping', None),
                              ('get_conan_manifest_url', None),
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

    @unittest.skipIf(get_env("CONAN_TESTING_SERVER_V2_ENABLED", False), "ApiV1 test")
    def no_signature_test(self):
        auth = AuthorizationHeaderSpy()
        retur = ReturnHandlerPlugin()
        server = TestServer(plugins=[auth, retur])
        servers = {"default": server}
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        client.save({"conanfile.py": conanfile})
        client.run("export . lasote/stable")
        # Upload will fail, as conan_server is expecting a signed URL
        errors = client.run("upload Hello/0.1@lasote/stable", ignore_error=True)
        self.assertTrue(errors)

        expected_calls = [('ping', None),
                          ('get_conan_manifest_url', None),
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
