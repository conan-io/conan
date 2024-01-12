config_yml = """\
versions:
  "{{version}}":
    folder: all
"""

conandata_yml = """\
sources:
  "{{version}}":
    url:
      {% if url is defined -%}
      - "{{url}}"
      {% else -%}
      - "http://put/here/the/url/to/release.1.2.3.zip"
      {% endif %}
    {% if sha256 is defined -%}
    sha256: "{{sha256}}"
    {%- else -%}
    sha256: "Put here your tarball sha256"
    {% endif -%}
"""


conanfile = """\
from conan import ConanFile
from conan.tools.cmake import CMakeToolchain, CMake, cmake_layout, CMakeDeps
from conan.tools.files import apply_conandata_patches, export_conandata_patches, get, load, replace_in_file, save


class {{package_name}}Recipe(ConanFile):
    name = "{{name}}"
    version = "{{version}}"
    package_type = "library"

    # Optional metadata
    license = "<Put the package license here>"
    author = "<Put your name here> <And your email here>"
    url = "<Package recipe repository url here, for issues about the package>"
    description = "<Description of {{ name }} package here>"
    topics = ("<Put some tag here>", "<here>", "<and here>")

    # Binary configuration
    settings = "os", "compiler", "build_type", "arch"
    options = {"shared": [True, False], "fPIC": [True, False]}
    default_options = {"shared": False, "fPIC": True}

    def config_options(self):
        if self.settings.os == "Windows":
            self.options.rm_safe("fPIC")

    def configure(self):
        if self.options.shared:
            self.options.rm_safe("fPIC")

    def export_sources(self):
        export_conandata_patches(self)

    def source(self):
        get(self, **self.conan_data["sources"][self.version], destination=self.source_folder)
        apply_conandata_patches(self)

    def layout(self):
        cmake_layout(self, src_folder="src")

    def generate(self):
        deps = CMakeDeps(self)
        deps.generate()
        tc = CMakeToolchain(self)
        tc.generate()

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.build()

    def package(self):
        cmake = CMake(self)
        cmake.install()

    def package_info(self):
        self.cpp_info.libs = ["{{name}}"]

    {% if requires is defined -%}
    def requirements(self):
        {% for require in requires -%}
        self.requires("{{ require }}")
        {% endfor %}
    {%- endif %}

    {% if tool_requires is defined -%}
    def build_requirements(self):
        {% for require in tool_requires -%}
        self.tool_requires("{{ require }}")
        {% endfor %}
    {%- endif %}
"""

oss_recipe_files = {"recipes/{{name}}/config.yml": config_yml,
                    "recipes/{{name}}/all/conandata.yml": conandata_yml,
                    "recipes/{{name}}/all/conanfile.py": conanfile}
