import os
from collections import namedtuple
from io import StringIO


from conan import ConanFile
from conan.internal.conan_app import ConanFileHelpers
from conans.model.conf import Conf
from conans.model.layout import Folders, Infos
from conans.model.options import Options
from conans.errors import ConanException
from conans.model.conf import ConfDefinition


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


class RedirectedInputStream:
    """
    Mock for testing. If get_username or get_password is requested will raise
    an exception except we have a value to return.
    """

    def __init__(self, answers: list):
        self.answers = answers

    def readline(self):
        if not self.answers:
            raise Exception("\n\n**********\n\nClass MockedInputStream: "
                            "There are no more inputs to be returned.\n"
                            "CHECK THE 'inputs=[]' ARGUMENT OF THE TESTCLIENT\n**********+*\n\n\n")
        ret = self.answers.pop(0)
        return ret


class MockSettings(object):

    def __init__(self, values):
        self.values = values

    def get_safe(self, value, default=None):
        return self.values.get(value, default)

    def __getattr__(self, name):
        try:
            return self.values[name]
        except KeyError:
            raise ConanException("'%s' value not defined" % name)


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
        self.conf = Conf()

        class MockConanInfo:
            pass
        self.info = MockConanInfo()
        self.info.settings = settings  # Incomplete, only settings for Cppstd Min/Max tests

    def run(self, *args, **kwargs):
        if self.runner:
            kwargs["output"] = None
            self.runner(*args, **kwargs)


class ConanFileMock(ConanFile):

    def __init__(self, shared=None):
        self.display_name = ""
        self._conan_node = None
        self.command = None
        self._commands = []
        self.path = None
        self.settings = None
        self.settings_build = MockSettings({"os": "Linux", "arch": "x86_64"})
        self.settings_target = None
        self.options = Options()
        if shared is not None:
            self.options = namedtuple("options", "shared")(shared)
        self.generators = []
        self.captured_env = {}
        self.folders = Folders()
        self.folders.set_base_source(".")
        self.folders.set_base_export_sources(".")
        self.folders.set_base_build(".")
        self.folders.set_base_generators(".")
        self.cpp = Infos()
        self._conan_user = None
        self._conan_channel = None
        self.env_scripts = {}
        self.win_bash = None
        self.conf = ConfDefinition().get_conanfile_conf(None)
        self._conan_helpers = ConanFileHelpers(None, None)
        self.cpp = Infos()

    def run(self, command, win_bash=False, subsystem=None, env=None, ignore_errors=False):
        assert win_bash is False
        assert subsystem is None
        self.command = command
        self._commands.append(command)
        self.path = os.environ["PATH"]
        self.captured_env = {key: value for key, value in os.environ.items()}
        return 0

    @property
    def commands(self):
        result = self._commands
        self._commands = []
        return result


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

    def __contains__(self, value):
        return value in self.__repr__()
