import unittest

from bottle import request

from conan.test.utils.tools import TestClient, TestServer


conanfile = """
from conan import ConanFile

class OpenSSLConan(ConanFile):
    name = "hello"
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

    def test_basic(self):
        auth = AuthorizationHeaderSpy()
        server = TestServer(plugins=[auth])
        servers = {"default": server}
        client = TestClient(servers=servers, inputs=["admin", "password"])
        client.save({"conanfile.py": conanfile})
        client.run("export . --user=lasote --channel=stable")
        errors = client.run("upload hello/0.1@lasote/stable -r default --only-recipe")
        self.assertFalse(errors)

        expected_calls = [('get_recipe_revisions_references', None),
                          ('check_credentials', None),
                          ('authenticate', 'Basic'),
                          ('upload_recipe_file', 'Bearer')]

        self.assertEqual(len(expected_calls), len(auth.auths))
        for i, (method, auth_type) in enumerate(expected_calls):
            real_call = auth.auths[i]
            self.assertEqual(method, real_call[0])
            if auth_type:
                self.assertIn(auth_type, real_call[1])
