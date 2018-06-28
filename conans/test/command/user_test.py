import json
import unittest

import os

from conans.test.utils.tools import TestClient, TestServer
from conans.util.files import load


class UserTest(unittest.TestCase):

    def test_command_user_no_remotes(self):
        """ Test that proper error is reported when no remotes are defined and conan user is executed
        """
        client = TestClient()
        with self.assertRaises(Exception):
            client.run("user")
        self.assertIn("ERROR: No remotes defined", client.user_io.out)

        with self.assertRaises(Exception):
            client.run("user -r wrong_remote")
        self.assertIn("ERROR: No remote 'wrong_remote' defined", client.user_io.out)

    def test_command_user_list(self):
        """ Test list of user is reported for all remotes or queried remote
        """
        servers = {
            "default": TestServer(),
            "test_remote_1": TestServer(),
        }
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
        self.assertIn("Current user of remote 'test_remote_1' set to: 'None' (anonymous)", client.out)
        self.assertIn("Current user of remote 'default' set to: 'None' (anonymous)", client.out)

    def test_with_no_user(self):
        test_server = TestServer()
        client = TestClient(servers={"default": test_server})
        error = client.run('user -p test', ignore_error=True)
        self.assertTrue(error)
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
        self.assertEqual(('john', None), client.localdb.get_login(test_server.fake_url))

        client.run('user will')
        self.assertIn("Changed user of remote 'default' from 'john' to 'will'", client.out)
        self.assertEqual(('will', None), client.localdb.get_login(test_server.fake_url))

        client.run('user None')
        self.assertIn("Changed user of remote 'default' from 'will' to 'None' (anonymous)",
                      client.out)
        self.assertEqual((None, None), client.localdb.get_login(test_server.fake_url))

        client.run('user')
        self.assertIn("Current user of remote 'default' set to: 'None' (anonymous)", client.out)

    def test_command_user_with_password(self):
        """ Checks the -p option, that obtains a token from the password.
        Useful for integrations as travis, that interactive password is not
        possible
        """
        test_server = TestServer()
        servers = {"default": test_server}
        conan = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        conan.run('user dummy -p ping_pong2', ignore_error=True)
        self.assertIn("ERROR: Wrong user or password", conan.user_io.out)
        conan.run('user lasote -p mypass')
        self.assertNotIn("ERROR: Wrong user or password", conan.user_io.out)
        self.assertIn("Changed user of remote 'default' from 'None' (anonymous) to 'lasote'",
                      conan.out)
        conan.run('user none')
        self.assertIn("Changed user of remote 'default' from 'lasote' to 'None' (anonymous)",
                      conan.out)
        self.assertEqual((None, None), conan.localdb.get_login(test_server.fake_url))
        conan.run('user')
        self.assertIn("Current user of remote 'default' set to: 'None' (anonymous)", conan.out)

    def test_command_user_with_password_spaces(self):
        """ Checks the -p option, that obtains a token from the password.
        Useful for integrations as travis, that interactive password is not
        possible
        """
        test_server = TestServer(users={"lasote": 'my "password'})
        servers = {"default": test_server}
        conan = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        conan.run(r'user lasote -p="my \"password"')
        self.assertNotIn("ERROR: Wrong user or password", conan.out)
        self.assertIn("Changed user of remote 'default' from 'None' (anonymous) to 'lasote'",
                      conan.out)
        conan.run('user none')
        conan.run(r'user lasote -p "my \"password"')
        self.assertNotIn("ERROR: Wrong user or password", conan.user_io.out)
        self.assertIn("Changed user of remote 'default' from 'None' (anonymous) to 'lasote'",
                      conan.out)

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
        self.assertIn("Current user of remote 'default' set to: 'lasote'", client.user_io.out)

    def test_command_user_with_interactive_password(self):
        test_server = TestServer()
        servers = {"default": test_server}
        conan = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        conan.run('user -p -r default lasote')
        self.assertIn('Please enter a password for "lasote" account:', conan.user_io.out)
        conan.run("user")
        self.assertIn("Current user of remote 'default' set to: 'lasote'", conan.user_io.out)

    def test_command_interactive_only(self):
        test_server = TestServer()
        servers = {"default": test_server}
        conan = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        conan.run('user -p')
        self.assertIn('Please enter a password for "lasote" account:', conan.user_io.out)
        conan.run("user")
        self.assertIn("Current user of remote 'default' set to: 'lasote'", conan.user_io.out)

    def test_command_user_with_interactive_password_login_prompt_disabled(self):
        """ Interactive password should not work.
        """
        test_server = TestServer()
        servers = {"default": test_server}
        conan = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        conan.run('config set general.non_interactive=True')
        error = conan.run('user -p -r default lasote', ignore_error=True)
        self.assertTrue(error)
        self.assertIn('ERROR: Conan interactive mode disabled', conan.user_io.out)
        self.assertNotIn("Please enter a password for \"lasote\" account:", conan.out)
        conan.run("user")
        self.assertIn("Current user of remote 'default' set to: 'None' (anonymous)", conan.out)
        error = conan.run("user -p", ignore_error=True)
        self.assertTrue(error)
        self.assertIn('ERROR: Conan interactive mode disabled', conan.out)
        self.assertNotIn("Remote 'default' username:", conan.out)

    def authenticated_test(self):
        test_server = TestServer(users={"lasote": "mypass", "danimtb": "passpass"})
        servers = {"default": test_server, "other_server": TestServer()}
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

    def json_test(self):

        def _compare_dicts(first_dict, second_dict):
            self.assertTrue(set(first_dict), set(second_dict))

        default_server = TestServer(users={"lasote": "mypass", "danimtb": "passpass"})
        other_server = TestServer()
        servers = {"default": default_server, "other_server": other_server}
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass"),
                                                                ("danimtb", "passpass")],
                                                    "other_server": []})
        client.run("user --json user.json")
        content = load(os.path.join(client.current_folder, "user.json"))
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
        content = load(os.path.join(client.current_folder, "user.json"))
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
        content = load(os.path.join(client.current_folder, "user.json"))
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
        content = load(os.path.join(client.current_folder, "user.json"))
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
        content = load(os.path.join(client.current_folder, "user.json"))
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
        content = load(os.path.join(client.current_folder, "user.json"))
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
        content = load(os.path.join(client.current_folder, "user.json"))
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
