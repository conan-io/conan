import os
import json
import textwrap

from conan.test.utils.tools import TestClient
from conan.internal.api.remotes.localdb import LOCALDB


class TestAuthRemoteTokenPlugin:
    """Token storage functions defined in auth_remote.py fully replace LocalDB."""

    plugin = textwrap.dedent("""\
        import json, os
        _STORE = os.path.join(os.path.dirname(__file__), "..", "..", "tokens.json")

        def _load():
            if not os.path.exists(_STORE):
                return {}
            with open(_STORE) as f:
                return json.load(f)

        def _save(data):
            with open(_STORE, "w") as f:
                json.dump(data, f)

        def auth_remote_plugin(remote, user=None):
            return None, None  # no direct credentials; falls through

        def auth_remote_token_get(remote_url):
            d = _load().get(remote_url)
            if not d:
                return None, None, None
            return d["user"], d["token"], d["refresh"]

        def auth_remote_token_store(remote_url, user, token, refresh):
            data = _load()
            data[remote_url] = {"user": user, "token": token, "refresh": refresh}
            _save(data)

        def auth_remote_token_clean(remote_url):
            data = _load()
            if remote_url is None:
                data.clear()
            else:
                data.pop(remote_url, None)
            _save(data)
        """)

    def test_token_stored_only_in_plugin(self):
        c = TestClient(default_server_user=True)
        c.save_home({"extensions/plugins/auth_remote.py": self.plugin})
        c.run("remote login default -p password")

        assert not os.path.exists(os.path.join(c.cache_folder, LOCALDB))
        tokens_file = os.path.join(c.cache_folder, "tokens.json")
        data = json.load(open(tokens_file))
        assert len(data) == 1
        entry = next(iter(data.values()))
        assert entry["user"] == "admin"
        assert entry["token"]

    def test_logout_clears_plugin_store(self):
        c = TestClient(default_server_user=True)
        c.save_home({"extensions/plugins/auth_remote.py": self.plugin})
        c.run("remote login default -p password")
        c.run("remote logout default")
        data = json.load(open(os.path.join(c.cache_folder, "tokens.json")))
        assert data == {}

    def test_round_trip_token_reused(self):
        """What the plugin stores at login must be what the plugin returns on later reads.
        Verified two ways: the second command retrieves the same JWT the first one wrote,
        and the CLI reports the remote as authenticated with no LocalDB fallback in play.
        """
        c = TestClient(default_server_user=True)
        c.save_home({"extensions/plugins/auth_remote.py": self.plugin})

        c.run("remote login default -p password")
        stored = json.load(open(os.path.join(c.cache_folder, "tokens.json")))
        remote_url, entry = next(iter(stored.items()))
        assert "token" in entry

        c.run("remote list-users")
        assert "Username: admin" in c.out
        assert "authenticated: True" in c.out
        assert not os.path.exists(os.path.join(c.cache_folder, LOCALDB))

        # Tamper: swap the stored token for a known-bad one; subsequent auth must fail,
        # proving the token used comes from the plugin store (not from anywhere else).
        stored[remote_url]["token"] = "not-a-valid-token"
        with open(os.path.join(c.cache_folder, "tokens.json"), "w") as f:
            json.dump(stored, f)
        c.run("list * -r=default")
        assert "Remote 'default' needs authentication, obtaining credentials" in c.out

    def test_partial_token_functions_rejected(self):
        c = TestClient(default_server_user=True)
        broken = textwrap.dedent("""\
            def auth_remote_token_get(remote_url):
                return None, None, None
            """)
        c.save_home({"extensions/plugins/auth_remote.py": broken})
        c.run("remote login default -p password", assert_error=True)
        assert "must define all of auth_remote_token_get" in c.out
