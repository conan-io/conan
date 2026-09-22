import json

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.env import environment_update
from conan.test.utils.tools import TestClient, TestServer


class TestRemoteForceAuth:
    """ https://github.com/conan-io/conan/issues/20338
    A remote can define that anonymous access must never be attempted, going directly
    for the authenticated credentials instead, even if the server would actually allow
    anonymous access.
    """

    @pytest.fixture
    def client(self):
        server = TestServer(users={"admin": "password"})
        # Repeated on purpose: the fixture consumes one pair for the upload below, and each
        # test method that triggers a new authentication consumes one more pair
        c = TestClient(light=True, servers={"default": server},
                       inputs=["admin", "password"] * 3)
        c.save({"conanfile.py": GenConanfile("pkg", "1.0")})
        c.run("create .")
        c.run("upload * -r=default -c")
        c.run("remove * -c")
        # The upload needed real credentials, but that must not leak into the read tests below
        c.run("remote logout default")
        return c

    def test_anonymous_by_default(self, client):
        """ A remote that allows anonymous access is used anonymously by default, even
        though valid credentials could be obtained interactively"""
        client.run("install --requires=pkg/1.0 -r=default")
        assert "requires authentication" not in client.out
        assert "Authenticated in remote 'default'" not in client.out
        client.run("remote list-users -f=json")
        assert json.loads(client.stdout) == [{"name": "default", "authenticated": False,
                                              "user_name": None}]

    def test_force_auth_skips_anonymous(self, client):
        """ Once force_auth is set, Conan must authenticate before ever
        attempting anonymous access"""
        client.run("remote update default --force-auth")
        client.run("install --requires=pkg/1.0 -r=default")
        assert "Remote 'default' requires authentication, obtaining credentials" in client.out
        assert "Authenticated in remote 'default' with user 'admin'" in client.out
        client.run("remote list-users -f=json")
        assert json.loads(client.stdout) == [{"name": "default", "authenticated": True,
                                              "user_name": "admin"}]

    def test_force_auth_only_happens_once(self, client):
        """ Once authenticated, the credentials are cached and reused, no new authentication
        is triggered on subsequent operations"""
        client.run("remote update default --force-auth")
        client.run("install --requires=pkg/1.0 -r=default")
        assert "Remote 'default' requires authentication, obtaining credentials" in client.out

        client.run("remove * -c")
        client.run("install --requires=pkg/1.0 -r=default")
        assert "Remote 'default' requires authentication, obtaining credentials" not in client.out

    def test_force_auth_uses_env_vars(self, client):
        """ The typical CI scenario from the issue: valid credentials are available via
        env-vars, but the remote unexpectedly allows anonymous access. Without
        force_auth the env-vars would be silently ignored (issue #19807), but
        force_auth forces them to be used"""
        client.run("remote update default --force-auth")
        with environment_update({"CONAN_LOGIN_USERNAME": "admin", "CONAN_PASSWORD": "password"}):
            client.run("install --requires=pkg/1.0 -r=default")
        assert "Remote 'default' requires authentication, obtaining credentials" in client.out
        assert "Authenticated in remote 'default' with user 'admin'" in client.out

    def test_force_auth_fails_without_credentials(self, client):
        """ If no credentials can be obtained and Conan cannot ask interactively, it must
        fail with a clear error, instead of silently falling back to anonymous access"""
        client.run("remote update default --force-auth")
        client.save_home({"global.conf": "core:non_interactive=True"})
        client.run("install --requires=pkg/1.0 -r=default", assert_error=True)
        assert "Conan interactive mode disabled" in client.out
        assert "requires authentication" in client.out
