import os
import textwrap
import unittest
from datetime import datetime

from conans import __version__ as client_version
from conans.test.utils.tools import TestClient, GenConanfile


class InfoTest(unittest.TestCase):

    def _create(self, name, version, deps=None, export=True):
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class pkg(ConanFile):
                name = "{name}"
                version = "{version}"
                license = {license}
                description = "blah"
                url = "myurl"
                {requires}
            """)
        requires = ""
        if deps:
            requires = "requires = {}".format(", ".join('"{}"'.format(d) for d in deps))

        conanfile = conanfile.format(name=name, version=version, requires=requires,
                                     license='"MIT"')

        self.client.save({"conanfile.py": conanfile}, clean_first=True)
        if export:
            self.client.run("export . --user=lasote --channel=stable")

    def test_graph(self):
        self.client = TestClient()

        test_deps = {
            "hello0": ["hello1", "hello2", "hello3"],
            "hello1": ["hello4"],
            "hello2": [],
            "hello3": ["hello7"],
            "hello4": ["hello5", "hello6"],
            "hello5": [],
            "hello6": [],
            "hello7": ["hello8"],
            "hello8": ["hello9", "hello10"],
            "hello9": [],
            "hello10": [],
        }

        def create_export(testdeps, name):
            deps = testdeps[name]
            for dep in deps:
                create_export(testdeps, dep)

            expanded_deps = ["%s/0.1@lasote/stable" % dep for dep in deps]
            export = False if name == "hello0" else True
            self._create(name, "0.1", expanded_deps, export=export)

        create_export(test_deps, "hello0")

        # arbitrary case - file will be named according to argument
        self.client.run("graph info . --format=dot")
        contents = self.client.stdout

        expected = textwrap.dedent("""
            "hello8/0.1@lasote/stable" -> "hello9/0.1@lasote/stable"
            "hello8/0.1@lasote/stable" -> "hello10/0.1@lasote/stable"
            "hello4/0.1@lasote/stable" -> "hello5/0.1@lasote/stable"
            "hello4/0.1@lasote/stable" -> "hello6/0.1@lasote/stable"
            "hello3/0.1@lasote/stable" -> "hello7/0.1@lasote/stable"
            "hello7/0.1@lasote/stable" -> "hello8/0.1@lasote/stable"
            "conanfile.py (hello0/0.1)" -> "hello1/0.1@lasote/stable"
            "conanfile.py (hello0/0.1)" -> "hello2/0.1@lasote/stable"
            "conanfile.py (hello0/0.1)" -> "hello3/0.1@lasote/stable"
            "hello1/0.1@lasote/stable" -> "hello4/0.1@lasote/stable"
            """)
        for line in expected.splitlines():
            assert line in contents

    def test_graph_html(self):
        self.client = TestClient()

        test_deps = {
            "hello0": ["hello1"],
            "hello1": [],
        }

        def create_export(testdeps, name):
            deps = testdeps[name]
            for dep in deps:
                create_export(testdeps, dep)

            expanded_deps = ["%s/0.1@lasote/stable" % dep for dep in deps]
            export = False if name == "hello0" else True
            self._create(name, "0.1", expanded_deps, export=export)

        create_export(test_deps, "hello0")

        # arbitrary case - file will be named according to argument
        self.client.run("graph info . --format=html")
        html = self.client.stdout
        self.assertIn("<body>", html)
        self.assertIn("{ from: 0, to: 1 }", html)
        self.assertIn("id: 0,\n                        label: 'hello0/0.1',", html)
        self.assertIn("Conan <b>v{}</b> <script>document.write(new Date().getFullYear())</script>"
                      " JFrog LTD. <a>https://conan.io</a>"
                      .format(client_version, datetime.today().year), html)

    def test_info_build_requires(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . --name=tool --version=0.1 --user=user --channel=channel")
        client.run("create . --name=dep --version=0.1 --user=user --channel=channel")
        conanfile = GenConanfile().with_require("dep/0.1@user/channel")
        client.save({"conanfile.py": conanfile})
        client.run("export . --name=pkg --version=0.1 --user=user --channel=channel")
        client.run("export . --name=pkg2 --version=0.1 --user=user --channel=channel")
        client.save({"conanfile.txt": "[requires]\npkg/0.1@user/channel\npkg2/0.1@user/channel",
                     "myprofile": "[tool_requires]\ntool/0.1@user/channel"}, clean_first=True)
        client.run("graph info . -pr=myprofile --build=missing --format=html")
        html = client.stdout
        self.assertIn("html", html)
        # To check that this node is not duplicated
        self.assertEqual(1, html.count("label: 'dep/0.1'"))
        self.assertIn("label: 'pkg2/0.1',\n                        "
                      "shape: 'box',\n                        "
                      "color: { background: 'Khaki'},", html)
        self.assertIn("label: 'pkg/0.1',\n                        "
                      "shape: 'box',\n                        "
                      "color: { background: 'Khaki'},", html)
        self.assertIn("label: 'tool/0.1',\n                        "
                      "shape: 'ellipse',\n                        "
                      "color: { background: 'SkyBlue'},", html)

    def test_topics_graph(self):
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class MyTest(ConanFile):
                name = "pkg"
                version = "0.2"
                topics = ("foo", "bar", "qux")
            """)

        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("export . --user=lasote --channel=testing")

        # Topics as tuple
        client.run("graph info --requires=pkg/0.2@lasote/testing --format=html")
        html_content = client.stdout
        self.assertIn("<h3>pkg/0.2@lasote/testing</h3>", html_content)
        self.assertIn("<li><b>topics</b>: foo, bar, qux</li>", html_content)

        # Topics as a string
        conanfile = conanfile.replace("(\"foo\", \"bar\", \"qux\")", "\"foo\"")
        client.save({"conanfile.py": conanfile}, clean_first=True)
        client.run("export . --user=lasote --channel=testing")
        client.run("graph info --requires=pkg/0.2@lasote/testing --format=html")
        html_content = client.stdout
        self.assertIn("<h3>pkg/0.2@lasote/testing</h3>", html_content)
        self.assertIn("<li><b>topics</b>: foo", html_content)


def test_user_templates():
    """ Test that a user can override the builtin templates putting templates/graph.html and
    templates/graph.dot in the home
    """
    c = TestClient()
    c.save({'lib.py': GenConanfile("lib", "0.1")})
    c.run("create lib.py")
    template_folder = os.path.join(c.cache_folder, 'templates')
    c.save({"graph.html": '{{ base_template_path }}',
            "graph.dot": '{{ base_template_path }}'}, path=template_folder)
    c.run("graph info --requires=lib/0.1 --format=html")
    assert template_folder in c.stdout
    c.run("graph info --requires=lib/0.1 --format=dot")
    assert template_folder in c.stdout
