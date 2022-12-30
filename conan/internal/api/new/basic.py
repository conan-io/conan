_conanfile = '''\
from conan import ConanFile

class BasicConanfile(ConanFile):
    name = "{% if name is defined %}{{ name }}{% else %}pkg{% endif %}"
    version = "{% if version is defined %}{{ version }}{% else %}1.0{% endif %}"
    description = "{% if description is defined %}{{ description }}{% else %}A bare-bones recipe{% endif %}"

    # Text about the requirements() method
    def requirements(self):
        {% if requires is defined -%}
        {% for require in as_iterable(requires) -%}
        self.requires("{{ require }}")
        {% endfor %}
        {% else -%}
        # Uncommenting this line will add the zlib/1.2.13 dependency to your project
        # self.requires("zlib/1.2.13")
        pass
        {%- endif %}

    # Text about the build() method
    def build(self):
        pass

    # Text about the package() method
    def package(self):
        pass
'''


basic_file = {"conanfile.py": _conanfile}
