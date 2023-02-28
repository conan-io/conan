def inject_get_or_else(variable, default):
    return variable + ' = "{% if ' + variable + " is defined %}{{ " + variable + " }}{% else %}" + default + '{% endif %}"'

_conanfile_header = f'''\
    {inject_get_or_else("name", "pkg")}
    {inject_get_or_else("version", "1.0")}
    {inject_get_or_else("description", "A basic recipe")}
    {inject_get_or_else("license", "<Your project license goes here>")}
    {inject_get_or_else("homepage", "<Your project homepage goes here>")}
'''

_conanfile = '''\
from conan import ConanFile

class BasicConanfile(ConanFile):
''' + _conanfile_header + '''\

    # The requirements method allows you to define the dependencies of your recipe
    def requirements(self):
        # Each call to self.requires() will add the corresponding requirement
        # to the current list of requirements
        {% if requires is defined -%}
        {% for require in requires -%}
        self.requires("{{ require }}")
        {% endfor %}
        {% else -%}
        # Uncommenting this line will add the zlib/1.2.13 dependency to your project
        # self.requires("zlib/1.2.13")
        pass
        {%- endif %}

    # The purpose of generate() is to prepare the build, generating the necessary files, such as
    # Files containing information to locate the dependencies, environment activation scripts,
    # and specific build system files among others
    def generate(self):
        pass

    # This method is used to build the source code of the recipe using the desired commands.
    def build(self):
        # You can use your command line tools to invoke your build system
        # or any of the build helpers provided with Conan in conan.tools
        # self.run("g++ ...")
        pass

    # The actual creation of the package, once it's built, is done in the package() method.
    # Using the copy() method from tools.files, artifacts are copied
    # from the build folder to the package folder
    def package(self):
        # copy(self, "*.h", self.source_folder, join(self.package_folder, "include"), keep_path=False)
        pass
'''


basic_file = {"conanfile.py": _conanfile}
