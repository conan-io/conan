import os
import textwrap

import pytest

from conan.test.utils.tools import TestClient
from conans.util.files import save


class TestErrorsAuthPlugin:
    """ when the plugin fails, we want a clear message and a helpful trace
    """
    def test_error_profile_plugin(self):
        c = TestClient(default_server_user=True)
        auth_plugin = textwrap.dedent("""\
            def auth_plugin(remote, user=None, password=None):
                raise Exception("Test Error")
            """)
        save(os.path.join(c.cache.plugins_path, "auth.py"), auth_plugin)
        c.run("remote logout default")
        c.run("remote login default", assert_error=True)
        assert "Error while processing 'auth.py' plugin" in c.out
        assert "Test Error" in c.out

    def test_remove_plugin_file(self):
        c = TestClient()
        c.run("version")  # to trigger the creation
        os.remove(os.path.join(c.cache.plugins_path, "auth.py"))
        c.run("remote add default http://fake")
        c.run("remote login default", assert_error=True)
        assert "ERROR: The 'auth.py' plugin file doesn't exist" in c.out

    @pytest.mark.parametrize("password", ["password", "bad-password"])
    def test_profile_plugin_direct_credentials(self, password):
        should_fail = password == "bad-password"
        c = TestClient(default_server_user=True)
        auth_plugin = textwrap.dedent(f"""\
            def auth_plugin(remote, user=None, password=None):
                return "admin", "{password}"
            """)
        save(os.path.join(c.cache.plugins_path, "auth.py"), auth_plugin)
        c.run("remote logout default")
        c.run("remote login default", assert_error=should_fail)
        if should_fail:
            assert "ERROR: Wrong user or password. [Remote: default]" in c.out
        else:
            assert "Changed user of remote 'default' from 'None' (anonymous) to 'admin' (authenticated)" in c.out

    def test_profile_plugin_fallback(self):
        c = TestClient(default_server_user=True)
        auth_plugin = textwrap.dedent("""\
                def auth_plugin(remote, user=None, password=None):
                    return None, None
                """)
        save(os.path.join(c.cache.plugins_path, "auth.py"), auth_plugin)
        c.run("remote logout default")
        c.run("remote login default")
        # As the auth plugin is not returning any password the code is falling back to the rest of
        # the input methods in this case the stdin provided by TestClient.
        assert "Changed user of remote 'default' from 'None' (anonymous) to 'admin' (authenticated)" in c.out
