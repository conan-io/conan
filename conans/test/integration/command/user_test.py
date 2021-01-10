import json
import unittest
from collections import OrderedDict

from conans.test.utils.tools import TestClient, TestServer


class UserTest(unittest.TestCase):

    def test_command_user_no_remotes(self):
        """ Test that proper error is reported when no remotes are defined and conan user is executed
        """
        client = TestClient()
        with self.assertRaises(Exception):
            client.run("user")
        self.assertIn("ERROR: No remotes defined", client.out)

        with self.assertRaises(Exception):
            client.run("user -r wrong_remote")
        self.assertIn("ERROR: No remote 'wrong_remote' defined", client.out)

    def test_command_user_list(self):
        """ Test list of user is reported for all remotes or queried remote
        """
        servers = OrderedDict()
        servers["default"] = TestServer()
        servers["test_remote_1"] = TestServer()
        client = TestClient(servers=servers)

        # Test with wrong remote right error is reported
        with self.assertRaises(Exception):
            client.run("user -r Test_Wrong_Remote")
        self.assertIn("ERROR: No remote 'Test_Wrong_Remote' defined", client.out)

        # Test user list for requested remote reported
        client.run("user -r test_remote_1")
        self.assertIn("Current user of remote 'test_remote_1' set to: 'None' (anonymous)",
                      client.out)
        self.assertNotIn("Current user of 'default' remote set to: 'None' (anonymous)", client.out)

        # Test user list for all remotes is reported
        client.run("user")
        self.assertIn("Current user of remote 'test_remote_1' set to: 'None' (anonymous)",
                      client.out)
        self.assertIn("Current user of remote 'default' set to: 'None' (anonymous)", client.out)

    def test_with_no_user(self):
        test_server = TestServer()
        client = TestClient(servers={"default": test_server})
        client.run('user -p test', assert_error=True)
        self.assertIn("ERROR: User for remote 'default' is not defined. [Remote: default]",
                      client.out)

    def test_with_remote_no_connect(self):
        test_server = TestServer()
        client = TestClient(servers={"default": test_server})
        client.run('user')
        self.assertIn("Current user of remote 'default' set to: 'None' (anonymous)", client.out)

        client.run('user john')
        self.assertIn("Changed user of remote 'default' from 'None' (anonymous) to 'john'",
                      client.out)
        localdb = client.cache.localdb
        self.assertEqual(('john', None, None), localdb.get_login(test_server.fake_url))

        client.run('user will')
        self.assertIn("Changed user of remote 'default' from 'john' to 'will'", client.out)
        self.assertEqual(('will', None, None), localdb.get_login(test_server.fake_url))

        client.run('user None')
        self.assertIn("Changed user of remote 'default' from 'will' to 'None' (anonymous)",
                      client.out)
        self.assertEqual((None, None, None), localdb.get_login(test_server.fake_url))

        client.run('user')
        self.assertIn("Current user of remote 'default' set to: 'None' (anonymous)", client.out)

    def test_command_user_with_password(self):
        """ Checks the -p option, that obtains a token from the password.
        Useful for integrations as travis, that interactive password is not
        possible
        """
        test_server = TestServer()
        servers = {"default": test_server}
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        client.run('user dummy -p ping_pong2', assert_error=True)
        self.assertIn("ERROR: Wrong user or password", client.out)
        client.run('user lasote -p mypass')
        self.assertNotIn("ERROR: Wrong user or password", client.out)
        self.assertIn("Changed user of remote 'default' from 'None' (anonymous) to 'lasote'",
                      client.out)
        client.run('user none')
        self.assertIn("Changed user of remote 'default' from 'lasote' to 'None' (anonymous)",
                      client.out)
        localdb = client.cache.localdb
        self.assertEqual((None, None, None), localdb.get_login(test_server.fake_url))
        client.run('user')
        self.assertIn("Current user of remote 'default' set to: 'None' (anonymous)", client.out)

    def test_command_user_with_password_spaces(self):
        """ Checks the -p option, that obtains a token from the password.
        Useful for integrations as travis, that interactive password is not
        possible
        """
        test_server = TestServer(users={"lasote": 'my "password'})
        servers = {"default": test_server}
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        client.run(r'user lasote -p="my \"password"')
        self.assertNotIn("ERROR: Wrong user or password", client.out)
        self.assertIn("Changed user of remote 'default' from 'None' (anonymous) to 'lasote'",
                      client.out)
        client.run('user none')
        client.run(r'user lasote -p "my \"password"')
        self.assertNotIn("ERROR: Wrong user or password", client.out)
        self.assertIn("Changed user of remote 'default' from 'None' (anonymous) to 'lasote'",
                      client.out)

    def test_clean(self):
        test_server = TestServer()
        servers = {"default": test_server}
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        base = '''
from conans import ConanFile

class ConanLib(ConanFile):
    name = "lib"
    version = "0.1"
'''
        files = {"conanfile.py": base}
        client.save(files)
        client.run("export . lasote/stable")
        client.run("upload lib/0.1@lasote/stable")
        client.run("user")
        self.assertIn("Current user of remote 'default' set to: 'lasote'", client.out)
        client.run("user --clean")
        client.run("user")
        self.assertNotIn("lasote", client.out)
        self.assertIn("Current user of remote 'default' set to: 'None' (anonymous)", client.out)
        client.run("upload lib/0.1@lasote/stable")
        client.run("user")
        self.assertIn("Current user of remote 'default' set to: 'lasote'", client.out)

    def test_command_user_with_interactive_password(self):
        test_server = TestServer()
        servers = {"default": test_server}
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        client.run('user -p -r default lasote')
        self.assertIn('Please enter a password for "lasote" account:', client.out)
        client.run("user")
        self.assertIn("Current user of remote 'default' set to: 'lasote'", client.out)

    def test_command_interactive_only(self):
        test_server = TestServer()
        servers = {"default": test_server}
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        client.run('user -p')
        self.assertIn('Please enter a password for "lasote" account:', client.out)
        client.run("user")
        self.assertIn("Current user of remote 'default' set to: 'lasote'", client.out)

    def test_command_user_with_interactive_password_login_prompt_disabled(self):
        """ Interactive password should not work.
        """
        test_server = TestServer()
        servers = {"default": test_server}
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        client.run('config set general.non_interactive=True')
        client.run('user -p -r default lasote', assert_error=True)
        self.assertIn('ERROR: Conan interactive mode disabled', client.out)
        self.assertNotIn("Please enter a password for \"lasote\" account:", client.out)
        client.run("user")
        self.assertIn("Current user of remote 'default' set to: 'None' (anonymous)", client.out)
        client.run("user -p", assert_error=True)
        self.assertIn('ERROR: Conan interactive mode disabled', client.out)
        self.assertNotIn("Remote 'default' username:", client.out)

    def test_authenticated(self):
        test_server = TestServer(users={"lasote": "mypass", "danimtb": "passpass"})
        servers = OrderedDict()
        servers["default"] = test_server
        servers["other_server"] = TestServer()
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass"),
                                                                ("danimtb", "passpass")],
                                                    "other_server": []})
        client.run("user")
        self.assertIn("Current user of remote 'default' set to: 'None' (anonymous)", client.out)
        self.assertNotIn("[Authenticated]", client.out)
        client.run('user bad_user')
        client.run("user")
        self.assertNotIn("[Authenticated]", client.out)
        client.run("user lasote")
        client.run("user")
        self.assertNotIn("[Authenticated]", client.out)
        client.run("user lasote -p mypass")
        client.run("user")
        self.assertIn("Current user of remote 'default' set to: 'lasote' [Authenticated]",
                      client.out)
        client.run("user danimtb -p passpass")
        client.run("user")
        self.assertIn("Current user of remote 'default' set to: 'danimtb' [Authenticated]",
                      client.out)
        client.run("user lasote -r other_server")
        client.run("user")
        self.assertIn("Current user of remote 'default' set to: 'danimtb' [Authenticated]",
                      client.out)
        self.assertIn("Current user of remote 'other_server' set to: 'lasote'", client.out)
        client.run("user lasote -r default")
        client.run("user")
        self.assertIn("Current user of remote 'default' set to: 'lasote'", client.out)
        self.assertIn("Current user of remote 'other_server' set to: 'lasote'", client.out)
        self.assertNotIn("[Authenticated]", client.out)

    def test_json(self):
        def _compare_dicts(first_dict, second_dict):
            self.assertTrue(set(first_dict), set(second_dict))

        default_server = TestServer(users={"lasote": "mypass", "danimtb": "passpass"})
        other_server = TestServer()
        servers = OrderedDict()
        servers["default"] = default_server
        servers["other_server"] = other_server
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass"),
                                                                ("danimtb", "passpass")],
                                                    "other_server": []})
        client.run("user --json user.json")
        content = client.load("user.json")
        info = json.loads(content)
        _compare_dicts({"error": False,
                        "remotes": [
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
                        ]}, info)

        client.run('user bad_user')
        client.run("user --json user.json")
        content = client.load("user.json")
        info = json.loads(content)
        _compare_dicts({"error": False,
                        "remotes": [
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
                        ]}, info)

        client.run("user lasote")
        client.run("user --json user.json")
        content = client.load("user.json")
        info = json.loads(content)
        _compare_dicts({"error": False,
                        "remotes": [
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
                        ]}, info)

        client.run("user lasote -p mypass")
        client.run("user --json user.json")
        content = client.load("user.json")
        info = json.loads(content)
        _compare_dicts({"error": False,
                        "remotes": [
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
                        ]}, info)

        client.run("user danimtb -p passpass")
        client.run("user --json user.json")
        content = client.load("user.json")
        info = json.loads(content)
        _compare_dicts({"error": False,
                        "remotes": [
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
                        ]}, info)

        client.run("user lasote -r other_server")
        client.run("user --json user.json")
        content = client.load("user.json")
        info = json.loads(content)
        _compare_dicts({"error": False,
                        "remotes": [
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
                        ]}, info)

        client.run("user lasote -r default")
        client.run("user --json user.json")
        content = client.load("user.json")
        info = json.loads(content)
        _compare_dicts({"error": False,
                        "remotes": [
                            {
                                "name": "default",
                                "authenticated": False,
                                "user_name": "lasote"
                            },
                            {
                                "name": "other_server",
                                "authenticated": False,
                                "user_name": "lasote"
                            }
                        ]}, info)

    def test_skip_auth(self):
        default_server = TestServer(users={"lasote": "mypass", "danimtb": "passpass"})
        servers = OrderedDict()
        servers["default"] = default_server
        client = TestClient(servers=servers)
        # Regular auth
        client.run("user lasote -r default -p mypass")

        # Now skip the auth
        client.run("user lasote -r default -p BAD_PASS --skip-auth")
        self.assertIn("User of remote 'default' is already 'lasote'", client.out)

        client.run("user lasote -r default -p BAD_PASS", assert_error=True)
        self.assertIn("Wrong user or password", client.out)

        # Login again correctly
        client.run("user lasote -r default -p mypass")

        # If we try to skip the auth for a user not logged, it will fail, because
        # we don't have credentials for that user
        client.run("user danimtb -r default -p BAD_PASS --skip-auth", assert_error=True)
        self.assertIn("Wrong user or password", client.out)

        # Login again correctly
        client.run("user lasote -r default -p mypass")

        # Now try to skip without specifying user
        client.run("user -r default -p BAD_PASS --skip-auth")
