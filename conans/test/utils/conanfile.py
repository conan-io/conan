
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
        self.cppflags = []
        self.sharedlinkflags = []
        self.exelinkflags = []
        self.sysroot = ""


class MockConanfile(object):

    def __init__(self, settings, options=None, runner=None):
        self.deps_cpp_info = MockDepsCppInfo()
        self.settings = settings
        self.runner = runner
        self.options = options or MockOptions({})
        self.generators = []

    def run(self, *args):
        if self.runner:
            self.runner(*args, output=None)


class TestConanFile(object):
    def __init__(self, name="Hello", version="0.1", settings=None, requires=None, options=None,
                 default_options=None, package_id=None, add_stdcpp=False):
        self.name = name
        self.version = version
        self.settings = settings
        self.requires = requires
        self.options = options
        self.default_options = default_options
        self.package_id = package_id
        self.add_stdcpp = add_stdcpp

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
        if self.options and not self.add_stdcpp:
            base += "    options = %s\n" % str(self.options)
        if self.default_options and not self.add_stdcpp:
            if isinstance(self.default_options, str):
                base += "    default_options = '%s'\n" % str(self.default_options)
            else:
                base += "    default_options = %s\n" % str(self.default_options)
        if self.package_id:
            base += "    def package_id(self):\n        %s\n" % self.package_id
        if self.add_stdcpp:
            base += "\n    def config_options(self):\n        self.add_cppstd()\n"
        return base
