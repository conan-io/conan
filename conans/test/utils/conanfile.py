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


class TestConanFile(object):
    def __init__(self, name="Hello", version="0.1", settings=None, requires=None, options=None,
                 default_options=None, package_id=None, build_requires=None, info=None,
                 private_requires=None, private_first=False):
        self.name = name
        self.version = version
        self.settings = settings
        self.requires = requires
        self.private_requires = private_requires
        self.build_requires = build_requires
        self.options = options
        self.default_options = default_options
        self.package_id = package_id
        self.info = info
        self.private_first = private_first

    def __repr__(self):
        base = """from conans import ConanFile

class {name}Conan(ConanFile):
    name = "{name}"
    version = "{version}"
""".format(name=self.name, version=self.version)
        if self.settings:
            base += "    settings = %s\n" % self.settings
        if self.requires or self.private_requires:
            if self.private_first:
                reqs_list = ["('%s', 'private')" % r for r in self.private_requires or []]
                reqs_list.extend(['"%s"' % r for r in self.requires or []])
            else:
                reqs_list = ['"%s"' % r for r in self.requires or []]
                reqs_list.extend(["('%s', 'private')" % r for r in self.private_requires or []])
            reqs_list.append("")
            base += "    requires = %s\n" % (", ".join(reqs_list))
        if self.build_requires:
            base += "    build_requires = %s\n" % (", ".join('"%s"' % r
                                                             for r in self.build_requires))
        if self.options:
            base += "    options = %s\n" % str(self.options)
        if self.default_options:
            if isinstance(self.default_options, str):
                base += "    default_options = '%s'\n" % str(self.default_options)
            else:
                base += "    default_options = %s\n" % str(self.default_options)
        if self.package_id:
            base += "    def package_id(self):\n        %s\n" % self.package_id
        if self.info:
            base += """
    def package_info(self):
        self.cpp_info.libs = ["mylib{name}{version}lib"]
        self.env_info.MYENV = ["myenv{name}{version}env"]
""".format(name=self.name, version=self.version)
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
