import json
import textwrap
import time
import unittest
from collections import OrderedDict
from datetime import timedelta

from conan.internal.api.remotes.localdb import LocalDB
from conan.test.utils.tools import TestClient, TestServer
from conan.test.utils.env import environment_update


class UserTest(unittest.TestCase):

    def test_command_user_no_remotes(self):
        """ Test that proper error is reported when no remotes are defined and conan user is executed
        """
        client = TestClient()
        with self.assertRaises(Exception):
            client.run("remote list-users")
        self.assertIn("ERROR: No remotes defined", client.out)

        with self.assertRaises(Exception):
            client.run("remote login wrong_remote foo -p bar")
        self.assertIn("ERROR: Remote 'wrong_remote' can't be found or is disabled", client.out)

    def test_command_user_list(self):
        """ Test list of user is reported for all remotes or queried remote
        """
        servers = OrderedDict()
        servers["default"] = TestServer()
        servers["test_remote_1"] = TestServer()
        client = TestClient(servers=servers)

        # Test with wrong remote right error is reported
        with self.assertRaises(Exception):
            client.run("remote login Test_Wrong_Remote foo")
        self.assertIn("ERROR: Remote 'Test_Wrong_Remote' can't be found or is disabled", client.out)

        # Test user list for all remotes is reported
        client.run("remote list-users")
        assert textwrap.dedent("""
        default:
          No user
        test_remote_1:
          No user""") not in client.out

    def test_with_remote_no_connect(self):
        test_server = TestServer()
        client = TestClient(servers={"default": test_server})
        client.run('remote list-users')
        assert textwrap.dedent("""
                default:
                  No user""") not in client.out

        client.run('remote set-user default john')
        self.assertIn("Changed user of remote 'default' from 'None' (anonymous) to 'john'",
                      client.out)
        localdb = LocalDB(client.cache_folder)
        self.assertEqual(('john', None, None), localdb.get_login(test_server.fake_url))

        client.run('remote set-user default will')
        self.assertIn("Changed user of remote 'default' from 'john' (anonymous) to 'will'",
                      client.out)
        self.assertEqual(('will', None, None), localdb.get_login(test_server.fake_url))

        client.run('remote logout default')
        self.assertIn("Changed user of remote 'default' from 'will' (anonymous) "
                      "to 'None' (anonymous)",
                      client.out)
        self.assertEqual((None, None, None), localdb.get_login(test_server.fake_url))

    def test_command_user_with_password(self):
        """ Checks the -p option, that obtains a token from the password.
        Useful for integrations as travis, that interactive password is not
        possible
        """
        test_server = TestServer()
        servers = {"default": test_server}
        client = TestClient(servers=servers, inputs=["admin", "password"])
        client.run('remote login default dummy -p ping_pong2', assert_error=True)
        self.assertIn("ERROR: Wrong user or password", client.out)
        client.run('remote login default admin -p password')
        self.assertNotIn("ERROR: Wrong user or password", client.out)
        self.assertIn("Changed user of remote 'default' from 'None' (anonymous) to 'admin'",
                      client.out)
        client.run('remote logout default')
        self.assertIn("Changed user of remote 'default' from 'admin' (authenticated) "
                      "to 'None' (anonymous)", client.out)
        localdb = LocalDB(client.cache_folder)
        self.assertEqual((None, None, None), localdb.get_login(test_server.fake_url))
        client.run('remote list-users')
        assert 'default:\n  No user' in client.out

    def test_command_user_with_password_spaces(self):
        """ Checks the -p option, that obtains a token from the password.
        Useful for integrations as travis, that interactive password is not
        possible
        """
        test_server = TestServer(users={"lasote": 'my "password'})
        servers = {"default": test_server}
        client = TestClient(servers=servers, inputs=["lasote", "mypass"])
        client.run(r'remote login default lasote -p="my \"password"')
        self.assertIn("Changed user of remote 'default' from 'None' (anonymous) to 'lasote'",
                      client.out)
        client.run('remote logout default')
        client.run(r'remote login default lasote -p "my \"password"')
        self.assertNotIn("ERROR: Wrong user or password", client.out)
        self.assertIn("Changed user of remote 'default' from 'None' (anonymous) to 'lasote'",
                      client.out)

    def test_clean(self):
        test_server = TestServer()
        servers = {"default": test_server}
        client = TestClient(servers=servers, inputs=2*["admin", "password"])
        base = '''
from conan import ConanFile

class ConanLib(ConanFile):
    name = "lib"
    version = "0.1"
'''
        files = {"conanfile.py": base}
        client.save(files)
        client.run("export . --user=lasote --channel=stable")
        client.run("upload lib/0.1@lasote/stable -r default --only-recipe")
        client.run("remote list-users")
        assert 'default:\n  Username: admin\n  authenticated: True' in client.out
        client.run("remote logout default")
        self.assertIn("Changed user of remote 'default' from 'admin' (authenticated) "
                      "to 'None' (anonymous)", client.out)
        client.run("remote list-users")
        assert 'default:\n  No user' in client.out
        # --force will force re-authentication, otherwise not necessary to auth
        client.run("upload lib/0.1@lasote/stable -r default --force --only-recipe")
        client.run("remote list-users")
        assert 'default:\n  Username: admin\n  authenticated: True' in client.out

    def test_command_interactive_only(self):
        test_server = TestServer()
        servers = {"default": test_server}
        client = TestClient(servers=servers, inputs=["password"])
        client.run('remote login default admin -p')
        self.assertIn("Changed user of remote 'default' from 'None' (anonymous) "
                      "to 'admin' (authenticated)", client.out)

    def test_command_user_with_interactive_password_login_prompt_disabled(self):
        """ Interactive password should not work.
        """
        test_server = TestServer()
        servers = {"default": test_server}
        client = TestClient(servers=servers,  inputs=[])
        conan_conf = "core:non_interactive=True"
        client.save_home({"global.conf": conan_conf})
        client.run('remote login default admin -p', assert_error=True)
        self.assertIn('ERROR: Conan interactive mode disabled', client.out)
        self.assertNotIn("Please enter a password for \"admin\" account:", client.out)
        client.run("remote list-users")
        self.assertIn("default:\n  No user", client.out)

    def test_authenticated(self):
        test_server = TestServer(users={"lasote": "mypass", "danimtb": "passpass"})
        servers = OrderedDict()
        servers["default"] = test_server
        servers["other_server"] = TestServer()
        client = TestClient(servers=servers, inputs=["lasote", "mypass", "mypass", "mypass"])
        client.run("remote logout default")
        self.assertIn("Changed user of remote 'default' from "
                      "'None' (anonymous) to 'None' (anonymous)", client.out)
        self.assertNotIn("[authenticated]", client.out)
        client.run('remote set-user default bad_user')
        client.run("remote list-users")
        assert 'default:\n  Username: bad_user\n  authenticated: False' in client.out
        client.run("remote set-user default lasote")
        client.run("remote list-users")
        assert 'default:\n  Username: lasote\n  authenticated: False' in client.out
        client.run("remote login default lasote -p mypass")
        client.run("remote list-users")
        assert 'default:\n  Username: lasote\n  authenticated: True' in client.out

        client.run("remote login default danimtb -p passpass")
        self.assertIn("Changed user of remote 'default' from 'lasote' "
                      "(authenticated) to 'danimtb' (authenticated)", client.out)
        client.run("remote list-users")
        assert 'default:\n  Username: danimtb\n  authenticated: True' in client.out

    def test_json(self):
        default_server = TestServer(users={"lasote": "mypass", "danimtb": "passpass"})
        other_server = TestServer()
        servers = OrderedDict()
        servers["default"] = default_server
        servers["other_server"] = other_server
        client = TestClient(servers=servers, inputs=["lasote", "mypass", "danimtb", "passpass"])
        client.run("remote list-users -f json")
        info = json.loads(client.stdout)
        assert info == [
                            {
                                "name": "default",
                                "authenticated": False,
                                "user_name": None
                            },
                            {
                                "name": "other_server",
                                "authenticated": False,
                                "user_name": None
                            }
                        ]

        client.run('remote set-user default bad_user')
        client.run("remote list-users -f json")
        info = json.loads(client.stdout)
        assert info == [
            {
                "name": "default",
                "authenticated": False,
                "user_name": "bad_user"
            },
            {
                "name": "other_server",
                "authenticated": False,
                "user_name": None
            }
        ]

        client.run('remote set-user default lasote')
        client.run("remote list-users -f json")
        info = json.loads(client.stdout)
        assert info == [
            {
                "name": "default",
                "authenticated": False,
                "user_name": "lasote"
            },
            {
                "name": "other_server",
                "authenticated": False,
                "user_name": None
            }
        ]

        client.run("remote login default lasote -p mypass")
        client.run("remote list-users -f json")
        info = json.loads(client.stdout)
        assert info == [
            {
                "name": "default",
                "authenticated": True,
                "user_name": "lasote"
            },
            {
                "name": "other_server",
                "authenticated": False,
                "user_name": None
            }
        ]

        client.run("remote login default danimtb -p passpass")
        client.run("remote list-users -f json")
        info = json.loads(client.stdout)
        assert info == [
            {
                "name": "default",
                "authenticated": True,
                "user_name": "danimtb"
            },
            {
                "name": "other_server",
                "authenticated": False,
                "user_name": None
            }
        ]
        client.run("remote set-user other_server lasote")
        client.run("remote list-users -f json")
        info = json.loads(client.stdout)
        assert info == [
            {
                "name": "default",
                "authenticated": True,
                "user_name": "danimtb"
            },
            {
                "name": "other_server",
                "authenticated": False,
                "user_name": "lasote"
            }
        ]

        client.run("remote logout '*'")
        client.run("remote set-user default danimtb")
        client.run("remote list-users -f json")
        info = json.loads(client.stdout)
        assert info == [
            {
                "name": "default",
                "authenticated": False,
                "user_name": "danimtb"
            },
            {
                "name": "other_server",
                "authenticated": False,
                "user_name": None
            }
        ]
        client.run("remote list-users")
        assert "default:\n  Username: danimtb\n  authenticated: False" in client.out
        assert "other_server:\n  No user\n" in client.out

    def test_skip_auth(self):
        default_server = TestServer(users={"lasote": "mypass", "danimtb": "passpass"})
        servers = OrderedDict()
        servers["default"] = default_server
        client = TestClient(servers=servers)
        # Regular auth
        client.run("remote login default lasote -p mypass")

        # Now skip the auth but keeping the same user
        client.run("remote set-user default lasote")
        self.assertIn("Changed user of remote 'default' from "
                      "'lasote' (authenticated) to 'lasote' (authenticated)", client.out)

        # If we change the user the credentials are removed
        client.run("remote set-user default flanders")
        self.assertIn("Changed user of remote 'default' from "
                      "'lasote' (authenticated) to 'flanders' (anonymous)", client.out)

        client.run("remote login default lasote -p BAD_PASS", assert_error=True)
        self.assertIn("Wrong user or password", client.out)

        # Login again correctly
        client.run("remote login default lasote -p mypass")


def test_user_removed_remote_removed():
    # Make sure that removing a remote clears the credentials
    # https://github.com/conan-io/conan/issues/5562
    c = TestClient(default_server_user=True)
    server_url = c.servers["default"].fake_url
    c.run("remote login default admin -p password")
    localdb = LocalDB(c.cache_folder)
    login = localdb.get_login(server_url)
    assert login[0] == "admin"
    c.run("remote remove default")
    login = localdb.get_login(server_url)
    assert login == (None, None, None)


class TestRemoteAuth:
    def test_remote_auth(self):
        servers = OrderedDict()
        servers["default"] = TestServer(users={"lasote": "mypass", "danimtb": "passpass"})
        servers["other_server"] = TestServer(users={"lasote": "mypass"})
        c = TestClient(servers=servers, inputs=["lasote", "mypass", "danimtb", "passpass",
                                                "lasote", "mypass"])
        c.run("remote auth *")
        text = textwrap.dedent("""\
            default:
                user: lasote
            other_server:
                user: lasote""")
        assert text in c.out

        c.run("remote auth * --format=json")
        result = json.loads(c.stdout)
        assert result == {'default': {'user': 'lasote'}, 'other_server': {'user': 'lasote'}}

    def test_remote_auth_with_user(self):
        servers = OrderedDict()
        servers["default"] = TestServer(users={"lasote": "mypass"})
        servers["other_server"] = TestServer()
        c = TestClient(servers=servers, inputs=["lasote", "mypass"])
        c.run("remote set-user default lasote")
        c.run("remote auth * --with-user")
        text = textwrap.dedent("""\
            default:
                user: lasote
            other_server:
                user: None""")
        assert text in c.out

    def test_remote_auth_with_user_env_var(self):
        servers = OrderedDict()
        servers["default"] = TestServer(users={"lasote": "mypass"})
        servers["other_server"] = TestServer()
        c = TestClient(servers=servers)
        with environment_update({"CONAN_LOGIN_USERNAME_DEFAULT": "lasote",
                                 "CONAN_PASSWORD_DEFAULT": "mypass"}):
            c.run("remote auth * --with-user")
        text = textwrap.dedent("""\
            default:
                user: lasote
            other_server:
                user: None""")
        assert text in c.out

    def test_remote_auth_error(self):
        servers = OrderedDict()
        servers["default"] = TestServer(users={"user": "password"})
        c = TestClient(servers=servers, inputs=["user1", "pass", "user2", "pass", "user3", "pass"])
        c.run("remote auth *")
        assert "error: Too many failed login attempts, bye!" in c.out

    def test_remote_auth_server_expire_token_secret(self):
        server = TestServer(users={"myuser": "password", "myotheruser": "otherpass"})
        c = TestClient(servers={"default": server}, inputs=["myuser", "password",
                                                            "myotheruser", "otherpass",
                                                            "user", "pass", "user", "pass",
                                                            "user", "pass"])
        c.run("remote auth *")
        assert "user: myuser" in c.out
        # Invalidate server secret
        server.test_server.ra.api_v2.credentials_manager.secret = "potato"
        c.run("remote auth *")
        assert "user: myotheruser" in c.out
        # Invalidate server secret again
        server.test_server.ra.api_v2.credentials_manager.secret = "potato2"
        c.run("remote auth *")
        assert "error: Too many failed login attempts, bye!" in c.out

    def test_remote_auth_server_expire_token(self):
        server = TestServer(users={"myuser": "password", "myotheruser": "otherpass"})
        server.test_server.ra.api_v2.credentials_manager.expire_time = timedelta(seconds=2)
        c = TestClient(servers={"default": server}, inputs=["myuser", "password",
                                                            "myotheruser", "otherpass",
                                                            "user", "pass", "user", "pass",
                                                            "user", "pass"])
        c.run("remote auth *")
        assert "user: myuser" in c.out
        # token not expired yet, should work
        c.run("remote auth *")
        assert "user: myuser" in c.out
        # Token should expire
        time.sleep(3)
        c.run("remote auth *")
        assert "user: myotheruser" in c.out
        # Token should expire
        time.sleep(3)
        c.run("remote auth *")
        assert "error: Too many failed login attempts, bye!" in c.out
