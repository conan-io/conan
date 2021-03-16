# -*- coding: utf-8 -*-
import textwrap
import unittest

from jinja2 import Template

from conans.test.utils.tools import TestClient


class WorkspaceTest(unittest.TestCase):
    conanfile = Template(textwrap.dedent("""
        from conans import ConanFile

        class Library(ConanFile):
            name = "{{ name }}"
            version = "{{ version }}"
            {% if br %}build_requires = "{{ br }}"{% endif %}
            {% if req %}requires = "{{ req }}"{% endif %}
    """))

    def test_graph_failure(self):
        # https://github.com/conan-io/conan/issues/5612
        client = TestClient()

        client.save({"fmt/conanfile.py": self.conanfile.render(name="fmt", version="version")})

        client.save({"libA/conanfile.py": self.conanfile.render(name="libA", version="version",
                                                                req="fmt/version@user/channel")})
        client.save({"libB/conanfile.py": self.conanfile.render(name="libB", version="version",
                                                                req="fmt/version@user/channel",
                                                                br="libA/version@user/channel")})
        client.save({"libC/conanfile.py": self.conanfile.render(name="libC", version="version",
                                                                req="fmt/version@user/channel",
                                                                br="libB/version@user/channel")})

        client.run("create fmt fmt/version@user/channel")

        client.run("create libA libA/version@user/channel")
        client.run("create libB libB/version@user/channel")
        client.run("create libC libC/version@user/channel")

        conanws = textwrap.dedent("""
                    editables:
                      libA/version@user/channel:
                        path: libA
                      libB/version@user/channel:
                        path: libB
                      libC/version@user/channel:
                        path: libC
        
                    workspace_generator: cmake
                    root: libC/version@user/channel
                """)
        client.save({"conanws.yml": conanws})
        client.run("workspace install .")
