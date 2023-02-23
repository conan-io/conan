import textwrap

from conans.test.utils.tools import TestClient


convert = textwrap.dedent("""\
    import os, textwrap
    from jinja2 import Template

    from conan.cli.command import conan_command
    from conan.api.output import cli_out_write
    from conans.client.loader_txt import ConanFileTextLoader

    @conan_command(group="custom commands", formatters={"text": cli_out_write})
    def convert_txt(conan_api, parser, *args, **kwargs):
       \"""
       convert a conanfile.txt to a conanfile.py
       \"""
       parser.add_argument("path", help="Path to a folder containing a conanfile.txt")
       args = parser.parse_args(*args)

       path = conan_api.local.get_conanfile_path(args.path, os.getcwd(), py=False)
       txt = ConanFileTextLoader(open(path, "r").read())
       template = textwrap.dedent('''\\
            from conan import ConanFile

            class Pkg(ConanFile):
                {% if generators %}
                generators ={% for g in generators %} "{{g}}",{%endfor%}

                {% endif %}
                {% if options %}
                default_options = {{options}}
                {% endif %}

                def requirements(self):
                    {% for r in requires %}
                    self.requires("{{r}}")
                    {% endfor %}
                    {% if not requires %}
                    pass
                    {% endif %}

                def build_requirements(self):
                    {% for r in test_requires %}
                    self.test_requires("{{r}}")
                    {% endfor %}
                    {% for r in tool_requires %}
                    self.tool_requires("{{r}}")
                    {% endfor %}
                    {% if not tool_requires and not test_requires%}
                    pass
                    {% endif %}

                {% if layout %}
                def layout(self):
                    {{layout}}(self)
                {% endif %}
                ''')
       conanfile = Template(template, trim_blocks=True, lstrip_blocks=True)
       options = {}
       for o in txt.options.splitlines():
           k, v = o.split("=")
           options[k] = v
       conanfile = conanfile.render({"requires": txt.requirements,
                                     "tool_requires": txt.tool_requirements,
                                     "test_requires": txt.test_requirements,
                                     "generators": txt.generators,
                                     "options": options,
                                     "layout": txt.layout})
       return conanfile
    """)


def test_convert_txt():
    c = TestClient()
    txt = textwrap.dedent("""
        [requires]
        hello/0.1

        [test_requires]
        gtest/1.0

        [tool_requires]
        cmake/3.15
        ninja/1.0

        [generators]
        CMakeToolchain
        CMakeDeps

        [layout]
        cmake_layout

        [options]
        hello*:shared=True
        """)
    c.save({"conanfile.txt": txt,
            "cmd/extensions/commands/cmd_convert_txt.py": convert})
    c.run("config install cmd")
    c.run("convert-txt .", redirect_stdout="conanfile.py")
    expected = textwrap.dedent("""\
        from conan import ConanFile

        class Pkg(ConanFile):
            generators = "CMakeToolchain", "CMakeDeps",
            default_options = {'hello*:shared': 'True'}

            def requirements(self):
                self.requires("hello/0.1")

            def build_requirements(self):
                self.test_requires("gtest/1.0")
                self.tool_requires("cmake/3.15")
                self.tool_requires("ninja/1.0")

            def layout(self):
                cmake_layout(self)

        """)
    assert expected == c.load("conanfile.py")


def test_convert_txt_empty():
    c = TestClient()
    c.save({"conanfile.txt": "",
            "cmd/extensions/commands/cmd_convert_txt.py": convert})
    c.run("config install cmd")
    c.run("convert-txt .", redirect_stdout="conanfile.py")
    expected = textwrap.dedent("""\
        from conan import ConanFile

        class Pkg(ConanFile):

            def requirements(self):
                pass

            def build_requirements(self):
                pass


        """)
    assert expected == c.load("conanfile.py")
