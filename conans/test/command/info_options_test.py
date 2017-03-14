import unittest
from conans.test.utils.tools import TestClient


class InfoOptionsTest(unittest.TestCase):

    def info_options_test(self):
        """ packages with dash
        """
        client = TestClient()
        client.run('new My-Package/1.3@myuser/testing -t')
        # assert they are correct at least
        client.run("export myuser/testing")
        client.run("info test_package")
        self.assertIn("My-Package/1.3@myuser/testing", client.user_io.out)

        # Check that I can pass options to info
        client.run("info -o shared=True")
        self.assertIn("My-Package/1.3@PROJECT", client.user_io.out)
        client.run("info -o My-Package:shared=True")
        self.assertIn("My-Package/1.3@PROJECT", client.user_io.out)
        client.run("info test_package -o My-Package:shared=True")
        self.assertIn("My-Package/1.3@myuser/testing", client.user_io.out)

        # errors
        client.run("info -o shared2=True", ignore_error=True)
        self.assertIn("'options.shared2' doesn't exist", client.user_io.out)
        client.run("info -o My-Package:shared2=True", ignore_error=True)
        self.assertIn("'options.shared2' doesn't exist", client.user_io.out)
        client.run("info test_package -o My-Package:shared2=True", ignore_error=True)
        self.assertIn("'options.shared2' doesn't exist", client.user_io.out)
