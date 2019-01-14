import os
from collections import namedtuple, defaultdict

from conans import ConanFile, Options
from conans.model.build_info import DepsCppInfo
from conans.model.env_info import DepsEnvInfo, EnvInfo, EnvValues
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


class MockDepsCppInfo(defaultdict):
    def __init__(self):
        super(MockDepsCppInfo, self).__init__(MockCppInfo)
        self.include_paths = []
        self.lib_paths = []
        self.libs = []
        self.defines = []
        self.cflags = []
        self.cppflags = []
        self.sharedlinkflags = []
        self.exelinkflags = []
        self.sysroot = ""

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


class TestConanFile(object):
    def __init__(self, name="Hello", version="0.1", settings=None, requires=None, options=None,
                 default_options=None, package_id=None):
        self.name = name
        self.version = version
        self.settings = settings
        self.requires = requires
        self.options = options
        self.default_options = default_options
        self.package_id = package_id

    def __repr__(self):
        base = """from conans import ConanFile

class %sConan(ConanFile):
    name = "%s"
    version = "%s"
""" % (self.name, self.name, self.version)
        if self.settings:
            base += "    settings = %s\n" % self.settings
        if self.requires:
            base += "    requires = %s\n" % (", ".join('"%s"' % r for r in self.requires))
        if self.options:
            base += "    options = %s\n" % str(self.options)
        if self.default_options:
            if isinstance(self.default_options, str):
                base += "    default_options = '%s'\n" % str(self.default_options)
            else:
                base += "    default_options = %s\n" % str(self.default_options)
        if self.package_id:
            base += "    def package_id(self):\n        %s\n" % self.package_id
        return base


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
        self.deps_user_info = DepsUserInfo()
        self.deps_cpp_info = MockDepsCppInfo()
        self.env_info = EnvInfo()
        self._env = {}

    def run(self, command):
        self.command = command
        self.path = os.environ["PATH"]
        self.captured_env = {key: value for key, value in os.environ.items()}

    @property
    def env(self):
        return self._env
