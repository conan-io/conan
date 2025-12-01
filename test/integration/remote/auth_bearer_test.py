from bottle import request

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient, TestServer


class AuthorizationHeaderSpy:
    """ Generic plugin to handle Authorization header. Must be extended and implement
    some abstract methods in subclasses"""

    name = 'authorizationheaderspy'
    api = 2

    def __init__(self):
        self.auths = []

    def apply(self, callback, context):  # noqa
        auth = request.headers.get("Authorization")
        name = callback.__name__
        self.auths.append((name, auth))
        return callback


class TestAuthorizeBearer:

    def test_basic(self):
        auth = AuthorizationHeaderSpy()
        server = TestServer(plugins=[auth])
        client = TestClient(servers={"default": server}, inputs=["admin", "password"])
        client.save({"conanfile.py": GenConanfile("hello", "0.1")})
        client.run("export . --user=lasote --channel=stable")
        errors = client.run("upload hello/0.1@lasote/stable -r default --only-recipe")
        assert not errors

        expected_calls = [('get_recipe_revisions_references', None),
                          ('check_credentials', None),
                          ('authenticate', 'Basic'),
                          ('upload_recipe_file', 'Bearer')]

        assert len(expected_calls) == len(auth.auths)
        for i, (method, auth_type) in enumerate(expected_calls):
            real_call = auth.auths[i]
            assert method == real_call[0]
            if auth_type:
                assert auth_type in real_call[1]
