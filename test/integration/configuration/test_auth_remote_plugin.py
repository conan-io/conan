import os
import textwrap

import pytest

from conan.test.utils.tools import TestClient
from conans.util.files import save


class TestAuthRemotePlugin:
    """ Test when the plugin fails, we want a clear message and a helpful trace
    """
    def test_error_auth_remote_plugin(self):
        c = TestClient(default_server_user=True)
        auth_plugin = textwrap.dedent("""\
            def auth_remote_plugin(remote, user=None):
                raise Exception("Test Error")
            """)
        save(os.path.join(c.cache.plugins_path, "auth_remote.py"), auth_plugin)
        c.run("remote logout default")
        c.run("remote login default", assert_error=True)
        assert "Error while processing 'auth_remote.py' plugin" in c.out
        assert "ERROR: Error while processing 'auth_remote.py' plugin, line " in c.out

    """ Test when the plugin give a correct and wrong password, we want a message about the success
        or fail in login
    """
    @pytest.mark.parametrize("password", ["password", "bad-password"])
    def test_auth_remote_plugin_direct_credentials(self, password):
        should_fail = password == "bad-password"
        c = TestClient(default_server_user=True)
        auth_plugin = textwrap.dedent(f"""\
            def auth_remote_plugin(remote, user=None):
                return "admin", "{password}"
            """)
        save(os.path.join(c.cache.plugins_path, "auth_remote.py"), auth_plugin)
        c.run("remote logout default")
        c.run("remote login default", assert_error=should_fail)
        if should_fail:
            assert "ERROR: Wrong user or password. [Remote: default]" in c.out
        else:
            assert "Changed user of remote 'default' from 'None' (anonymous) to 'admin' (authenticated)" in c.out


    """ Test when the plugin do not give any user or password, we want the code to continue with
        the rest of the input methods
    """
    def test_auth_remote_plugin_fallback(self):
        c = TestClient(default_server_user=True)
        auth_plugin = textwrap.dedent("""\
                def auth_remote_plugin(remote, user=None):
                    return None, None
                """)
        save(os.path.join(c.cache.plugins_path, "auth_remote.py"), auth_plugin)
        c.run("remote logout default")
        c.run("remote login default")
        # As the auth plugin is not returning any password the code is falling back to the rest of
        # the input methods in this case the stdin provided by TestClient.
        assert "Changed user of remote 'default' from 'None' (anonymous) to 'admin' (authenticated)" in c.out
