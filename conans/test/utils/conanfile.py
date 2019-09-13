import os
from collections import namedtuple

from conans import Options
from conans.model.conan_file import ConanFile
from conans.model.options import PackageOptions
from conans.test.utils.tools import TestBufferConanOutput


class MockSettings(object):

    def __init__(self, values):
        self.values = values

    def get_safe(self, value):
        return self.values.get(value, None)


MockOptions = MockSettings


class MockDepsCppInfo(object):

    def __init__(self):
        self.include_paths = []
        self.lib_paths = []
        self.libs = []
        self.defines = []
        self.cflags = []
        self.cxxflags = []
        self.sharedlinkflags = []
        self.exelinkflags = []
        self.sysroot = ""


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
        self.deps_cpp_info = namedtuple("deps_cpp_info", "sysroot")("/path/to/sysroot")
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

    def run(self, command):
        self.command = command
        self.path = os.environ["PATH"]
        self.captured_env = {key: value for key, value in os.environ.items()}
