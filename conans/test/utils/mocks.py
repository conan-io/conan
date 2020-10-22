import os
import sys
from collections import Counter, defaultdict, namedtuple


import six
from six import StringIO

from conans import ConanFile, Options
from conans.client.output import ConanOutput
from conans.client.userio import UserIO
from conans.model.env_info import DepsEnvInfo, EnvInfo, EnvValues
from conans.model.options import PackageOptions
from conans.model.user_info import DepsUserInfo


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


class MockedUserIO(UserIO):
    """
    Mock for testing. If get_username or get_password is requested will raise
    an exception except we have a value to return.
    """

    def __init__(self, logins, ins=sys.stdin, out=None):
        """
        logins is a dict of {remote: list(user, password)}
        will return sequentially
        """
        assert isinstance(logins, dict)
        self.logins = logins
        self.login_index = Counter()
        UserIO.__init__(self, ins, out)

    def get_username(self, remote_name):
        username_env = self._get_env_username(remote_name)
        if username_env:
            return username_env

        self._raise_if_non_interactive()
        sub_dict = self.logins[remote_name]
        index = self.login_index[remote_name]
        if len(sub_dict) - 1 < index:
            raise Exception("Bad user/password in testing framework, "
                            "provide more tuples or input the right ones")
        return sub_dict[index][0]

    def get_password(self, remote_name):
        """Overridable for testing purpose"""
        password_env = self._get_env_password(remote_name)
        if password_env:
            return password_env

        self._raise_if_non_interactive()
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
        self.cppflags = []
        self.defines = []
        self.frameworks = []
        self.framework_paths = []


class MockDepsCppInfo(defaultdict):

    def __init__(self):
        super(MockDepsCppInfo, self).__init__(MockCppInfo)
        self.include_paths = []
        self.lib_paths = []
        self.libs = []
        self.defines = []
        self.cflags = []
        self.cxxflags = []
        self.sharedlinkflags = []
        self.exelinkflags = []
        self.sysroot = ""
        self.frameworks = []
        self.framework_paths = []
        self.system_libs = []

    @property
    def deps(self):
        return self.keys()


class MockConanfile(ConanFile):

    def __init__(self, settings, options=None, runner=None):
        self.deps_cpp_info = MockDepsCppInfo()
        self.settings = settings
        self.runner = runner
        self.options = options or MockOptions({})
        self.generators = []
        self.output = TestBufferConanOutput()

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
        self.command = None
        self.path = None
        self.source_folder = self.build_folder = "."
        self.settings = None
        self.options = Options(PackageOptions.loads(options))
        if options_values:
            for var, value in options_values.items():
                self.options._data[var] = value
        self.deps_cpp_info = MockDepsCppInfo()  # ("deps_cpp_info", "sysroot")("/path/to/sysroot")
        self.deps_cpp_info.sysroot = "/path/to/sysroot"
        self.output = TestBufferConanOutput()
        self.in_local_cache = False
        self.install_folder = "myinstallfolder"
        if shared is not None:
            self.options = namedtuple("options", "shared")(shared)
        self.should_configure = True
        self.should_build = True
        self.should_install = True
        self.should_test = True
        self.generators = []
        self.captured_env = {}
        self.deps_env_info = DepsEnvInfo()
        self.env_info = EnvInfo()
        self.deps_user_info = DepsUserInfo()
        self._conan_env_values = EnvValues()

    def run(self, command):
        self.command = command
        self.path = os.environ["PATH"]
        self.captured_env = {key: value for key, value in os.environ.items()}


MockOptions = MockSettings


class TestBufferConanOutput(ConanOutput):
    """ wraps the normal output of the application, captures it into an stream
    and gives it operators similar to string, so it can be compared in tests
    """

    def __init__(self):
        ConanOutput.__init__(self, StringIO(), color=False)

    def __repr__(self):
        # FIXME: I'm sure there is a better approach. Look at six docs.
        if six.PY2:
            return str(self._stream.getvalue().encode("ascii", "ignore"))
        else:
            return self._stream.getvalue()

    def __str__(self, *args, **kwargs):
        return self.__repr__()

    def __eq__(self, value):
        return self.__repr__() == value

    def __ne__(self, value):
        return not self.__eq__(value)

    def __contains__(self, value):
        return value in self.__repr__()


# cli2.0
class RedirectedTestOutput(StringIO):
    def __init__(self):
        super(RedirectedTestOutput, self).__init__()

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
