_conanfile = '''from conan import ConanFile

class {{package_name}}Recipe(ConanFile):
    settings = "os", "compiler", "build_type", "arch"
    name = "{{name}}"
    version = "{{version}}"

    {% if requires is defined %}
    def requirements(self):
        {% for require in requires -%}
        self.requires("{{ require }}")
        {% endfor %}
    {%- endif %}
    {%- if tool_requires is defined %}
    def build_requirements(self):
        {% for require in tool_requires -%}
        self.tool_requires("{{ require }}")
        {% endfor %}
    {%- endif %}
'''

demo_files = {"conanfile.py": _conanfile}
