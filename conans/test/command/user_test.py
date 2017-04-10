import unittest
from conans.test.utils.tools import TestClient, TestServer


class UserTest(unittest.TestCase):

    def test_command_user(self):
        """ Test that the user can be shown and changed, and it is reflected in the
        user cache localdb
        """
        client = TestClient()
        client.run('user')
        self.assertIn("ERROR: No remotes defined", client.user_io.out)

    def test_with_remote_no_connect(self):
        test_server = TestServer()
        client = TestClient(servers={"default": test_server})
        client.run('user')
        self.assertIn("Current 'default' user: None (anonymous)", client.user_io.out)

        client.run('user john')
        self.assertIn("Change 'default' user from None (anonymous) to john", client.user_io.out)
        self.assertEqual(('john', None), client.localdb.get_login(test_server.fake_url))

        client.run('user will')
        self.assertIn("Change 'default' user from john to will", client.user_io.out)
        self.assertEqual(('will', None), client.localdb.get_login(test_server.fake_url))

        client.run('user None')
        self.assertIn("Change 'default' user from will to None (anonymous)", client.user_io.out)
        self.assertEqual((None, None), client.localdb.get_login(test_server.fake_url))

        client.run('user')
        self.assertIn("Current 'default' user: None (anonymous)", client.user_io.out)

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
        self.assertIn("Change 'default' user from None (anonymous) to lasote", conan.user_io.out)
        conan.run('user none')
        self.assertIn("Change 'default' user from lasote to None (anonymous)", conan.user_io.out)
        self.assertEqual((None, None), conan.localdb.get_login(test_server.fake_url))
        conan.run('user')
        self.assertIn("Current 'default' user: None (anonymous)", conan.user_io.out)

    def test_command_user_with_password_spaces(self):
        """ Checks the -p option, that obtains a token from the password.
        Useful for integrations as travis, that interactive password is not
        possible
        """
        test_server = TestServer(users={"lasote": 'my "password'})
        servers = {"default": test_server}
        conan = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        conan.run(r'user lasote -p="my \"password"')
        self.assertNotIn("ERROR: Wrong user or password", conan.user_io.out)
        self.assertIn("Change 'default' user from None (anonymous) to lasote", conan.user_io.out)
        conan.run('user none')
        conan.run(r'user lasote -p "my \"password"')
        self.assertNotIn("ERROR: Wrong user or password", conan.user_io.out)
        self.assertIn("Change 'default' user from None (anonymous) to lasote", conan.user_io.out)

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
        client.run("export lasote/stable")
        client.run("upload lib/0.1@lasote/stable")
        client.run("user")
        self.assertIn("Current 'default' user: lasote", client.user_io.out)
        client.run("user --clean")
        client.run("user")
        self.assertNotIn("lasote", client.user_io.out)
        self.assertEqual("Current 'default' user: None (anonymous)\n", client.user_io.out)
        client.run("upload lib/0.1@lasote/stable")
        client.run("user")
        self.assertIn("Current 'default' user: lasote", client.user_io.out)
