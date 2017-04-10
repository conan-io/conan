
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
