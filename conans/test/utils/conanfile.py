import os
from collections import namedtuple, defaultdict

from conans import Options
from conans.model.conan_file import ConanFile
from conans.model.env_info import DepsEnvInfo, EnvInfo
from conans.model.env_info import EnvValues
from conans.model.options import PackageOptions
from conans.model.user_info import DepsUserInfo
from conans.test.utils.tools import TestBufferConanOutput


class MockSettings(object):

    def __init__(self, values):
        self.values = values

    def get_safe(self, value):
        return self.values.get(value, None)


MockOptions = MockSettings


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
