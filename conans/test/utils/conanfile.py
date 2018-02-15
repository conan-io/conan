
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
