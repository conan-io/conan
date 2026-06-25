import os

from conans.server.plugin_loader import load_authentication_plugin
from conan.test.utils.test_files import temp_folder
from conan.internal.util.files import save


class TestAuthenticatorPlugin:

    def test_instance_authenticator(self):
        folder = temp_folder()
        plugin_path = os.path.join(folder, "plugins", "authenticator", "my_auth.py")
        my_plugin = '''
# import to test that they work
import os

def get_class():
    return MyAuthenticator()


class MyAuthenticator(object):
    def valid_user(self, username, plain_password):
        os.path.exists("somepath")  # dummy call, to test that os is not removed by GC
        return username == "foo" and plain_password == "bar"
'''
        save(plugin_path, my_plugin)

        plugin = load_authentication_plugin(folder, "my_auth")
        assert plugin.valid_user("foo", "bar")
        assert not plugin.valid_user("foo2", "bar2")
