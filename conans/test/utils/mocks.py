import os
from collections import Counter, namedtuple
from io import StringIO

from conans import ConanFile
from conans.client.userio import UserInput
from conans.model.conf import ConfDefinition
from conans.model.layout import Folders
from conans.model.options import PackageOptions, Options


class LocalDBMock(object):

    def __init__(self, user=None, access_token=None, refresh_token=None):
        self.user = user
        self.access_token = access_token
        self.refresh_token = refresh_token

    def get_login(self, _):
        return self.user, self.access_token, self.refresh_token

    def get_username(self, _):
        return self.user

    def store(self, user, access_token, refresh_token, _):
        self.user = user
        self.access_token = access_token
        self.refresh_token = refresh_token


class MockedUserInput(UserInput):
    """
    Mock for testing. If get_username or get_password is requested will raise
    an exception except we have a value to return.
    """

    def __init__(self, non_interactive):
        """
        logins is a dict of {remote: list(user, password)}
        will return sequentially
        """
        self.logins = None
        self.login_index = Counter()
        UserInput.__init__(self, non_interactive=non_interactive)

    def get_username(self, remote_name):
        username_env = self._get_env_username(remote_name)
        if username_env:
            return username_env

        sub_dict = self.logins[remote_name]
        index = self.login_index[remote_name]
        if len(sub_dict) - 1 < index:
            raise Exception("Bad user/password in testing framework, "
                            "provide more tuples or input the right ones")
        return sub_dict[index][0]

    def get_pass(self, remote_name):
        """Overridable for testing purpose"""
        sub_dict = self.logins[remote_name]
        index = self.login_index[remote_name]
        tmp = sub_dict[index][1]
        self.login_index.update([remote_name])
        return tmp


class MockSettings(object):

    def __init__(self, values):
        self.values = values

    def get_safe(self, value):
        return self.values.get(value, None)


class MockCppInfo(object):
    def __init__(self):
        self.bin_paths = []
        self.lib_paths = []
        self.include_paths = []
        self.libs = []
        self.cflags = []
        self.cxxflags = []
        self.defines = []
        self.frameworks = []
        self.framework_paths = []


class MockConanfile(ConanFile):

    def __init__(self, settings, options=None, runner=None):
        self.display_name = ""
        self._conan_node = None
        self.folders = Folders()
        self.settings = settings
        self.settings_build = settings
        self.runner = runner
        self.options = options or MockOptions({})
        self.generators = []

        self.should_configure = True
        self.should_build = True
        self.should_install = True
        self.should_test = True

        self.package_folder = None

    def run(self, *args, **kwargs):
        if self.runner:
            kwargs["output"] = None
            self.runner(*args, **kwargs)


class ConanFileMock(ConanFile):

    def __init__(self, shared=None, options=None, options_values=None):
        options = options or ""
        self.display_name = ""
        self._conan_node = None
        self.command = None
        self.path = None
        self.settings = None
        self.settings_build = MockSettings({})
        self.options = Options(PackageOptions.loads(options))
        if options_values:
            for var, value in options_values.items():
                self.options._data[var] = value
        self.in_local_cache = False
        if shared is not None:
            self.options = namedtuple("options", "shared")(shared)
        self.should_configure = True
        self.should_build = True
        self.should_install = True
        self.should_test = True
        self.generators = []
        self.captured_env = {}
        self.folders = Folders()
        self.folders.set_base_source(".")
        self.folders.set_base_build(".")
        self.folders.set_base_install("myinstallfolder")
        self.folders.set_base_generators(".")
        self._conan_user = None
        self._conan_channel = None
        self.env_scripts = {}
        self.win_bash = None
        self.conf = ConfDefinition().get_conanfile_conf(None)

    def run(self, command, win_bash=False, subsystem=None, env=None):
        assert win_bash is False
        assert subsystem is None
        self.command = command
        self.path = os.environ["PATH"]
        self.captured_env = {key: value for key, value in os.environ.items()}


MockOptions = MockSettings


class RedirectedTestOutput(StringIO):
    def __init__(self):
        # Chage to super() for Py3
        StringIO.__init__(self)

    def clear(self):
        self.seek(0)
        self.truncate(0)

    def __repr__(self):
        return self.getvalue()

    def __str__(self, *args, **kwargs):
        return self.__repr__()

    def __eq__(self, value):
        return self.__repr__() == value

    def __ne__(self, value):
        return not self.__eq__(value)

    def __contains__(self, value):
        return value in self.__repr__()
