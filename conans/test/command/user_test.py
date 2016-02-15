import unittest
from conans.test.tools import TestClient, TestServer


class UserTest(unittest.TestCase):

    def test_command_user(self):
        """ Test that the user can be shown and changed, and it is reflected in the
        user cache localdb
        """
        conan = TestClient()
        conan.run('user')
        self.assertIn('Current user: None (anonymous)', conan.user_io.out)
        conan.run('user john')
        self.assertIn('Change user from None to john', conan.user_io.out)
        self.assertEqual(('john', None), conan.localdb.get_login())
        conan.run('user will')
        self.assertIn('Change user from john to will', conan.user_io.out)
        self.assertEqual(('will', None), conan.localdb.get_login())
        conan.run('user none')
        self.assertIn('Change user from will to None (anonymous)', conan.user_io.out)
        self.assertEqual((None, None), conan.localdb.get_login())
        conan.run('user')
        self.assertIn('Current user: None (anonymous)', conan.user_io.out)

    def test_command_user_with_password(self):
        """ Checks the -p option, that obtains a token from the password.
        Useful for integrations as travis, that interactive password is not
        possible
        """
        test_server = TestServer([("*/*@*/*", "*")],  # read permissions
                                 [],  # write permissions
                                 users={"lasote": "mypass"})  # exported users and passwords
        servers = {"default": test_server}
        conan = TestClient(servers=servers, users=[("lasote", "mypass")])  # Mocked userio
        conan.run('user dummy -p ping_pong2', ignore_error=True)
        self.assertIn("ERROR: Wrong user or password", conan.user_io.out)
        conan.run('user lasote -p mypass')
        self.assertNotIn("ERROR: Wrong user or password", conan.user_io.out)
        self.assertIn("Change user from None to lasote", conan.user_io.out)
        conan.run('user none')
        self.assertIn('Change user from lasote to None (anonymous)', conan.user_io.out)
        self.assertEqual((None, None), conan.localdb.get_login())
        conan.run('user')
        self.assertIn('Current user: None (anonymous)', conan.user_io.out)

    def test_command_user_with_password_spaces(self):
        """ Checks the -p option, that obtains a token from the password.
        Useful for integrations as travis, that interactive password is not
        possible
        """
        test_server = TestServer([("*/*@*/*", "*")],  # read permissions
                                 [],  # write permissions
                                 users={"lasote": 'my "password'})
        servers = {"default": test_server}
        conan = TestClient(servers=servers, users=[("lasote", "mypass")])
        conan.run(r'user lasote -p="my \"password"')
        self.assertNotIn("ERROR: Wrong user or password", conan.user_io.out)
        self.assertIn("Change user from None to lasote", conan.user_io.out)
        conan.run('user none')
        conan.run(r'user lasote -p "my \"password"')
        self.assertNotIn("ERROR: Wrong user or password", conan.user_io.out)
        self.assertIn("Change user from None to lasote", conan.user_io.out)
