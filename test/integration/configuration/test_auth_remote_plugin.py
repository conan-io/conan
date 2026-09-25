import textwrap

import pytest

from conan.test.utils.tools import TestClient, TestServer


class TestAuthRemotePlugin:

    def test_error_auth_remote_plugin(self):
        """ Test when the plugin fails, we want a clear message and a helpful trace
        """
        c = TestClient(default_server_user=True)
        auth_plugin = textwrap.dedent("""\
            def auth_remote_plugin(remote, user=None):
                raise Exception("Test Error")
            """)
        c.save_home({"extensions/plugins/auth_remote.py": auth_plugin})
        c.run("remote logout default")
        c.run("remote login default", assert_error=True)
        assert "Error while processing 'auth_remote.py' plugin" in c.out
        assert "ERROR: Error while processing 'auth_remote.py' plugin, line " in c.out

    @pytest.mark.parametrize("password", ["password", "bad-password"])
    def test_auth_remote_plugin_direct_credentials(self, password):
        """ Test when the plugin give a correct and wrong password, we want a message about
        the success or fail in login
        """
        should_fail = password == "bad-password"
        c = TestClient(default_server_user=True)
        auth_plugin = textwrap.dedent(f"""\
            def auth_remote_plugin(remote, user=None):
                return "admin", "{password}"
            """)
        c.save_home({"extensions/plugins/auth_remote.py": auth_plugin})
        c.run("remote logout default")
        c.run("remote login default", assert_error=should_fail)
        if should_fail:
            assert "ERROR: Wrong user or password. [Remote: default]" in c.out
        else:
            assert ("Changed user of remote 'default' from 'None' (anonymous) to "
                    "'admin' (authenticated)") in c.out

    def test_auth_remote_plugin_fallback(self):
        """ Test when the plugin do not give any user or password, we want the code to continue with
            the rest of the input methods
        """
        c = TestClient(default_server_user=True)
        auth_plugin = textwrap.dedent("""\
                def auth_remote_plugin(remote, user=None):
                    return None, None
                """)
        c.save_home({"extensions/plugins/auth_remote.py": auth_plugin})
        c.run("remote logout default")
        c.run("remote login default")
        # As the auth plugin is not returning any password the code is falling back to the rest of
        # the input methods in this case the stdin provided by TestClient.
        assert ("Changed user of remote 'default' from 'None' (anonymous) to "
                "'admin' (authenticated)") in c.out

    def test_creds_caching_multiple_remotes(self):
        """ The auth plugin can cache partial results and credentials to avoid repeated
        multiple interactive requests, reusing the same inputs for all remotes
        https://github.com/conan-io/conan/issues/19772
        """
        c = TestClient(servers={"server1": TestServer(users={"admin1": "passwd"}),
                                "server2": TestServer(users={"admin2": "passwd"})})
        auth_plugin = textwrap.dedent("""\
            count = 0
            def auth_remote_plugin(remote, user=None):
                global count
                count = count + 1
                return f"admin{count}", "passwd"
            """)
        c.save_home({"extensions/plugins/auth_remote.py": auth_plugin})
        c.run("remote auth *")  # Triggers all remotes
        assert "Authenticated in remote 'server1' with user 'admin1'" in c.out
        assert "Authenticated in remote 'server2' with user 'admin2'" in c.out
