import os
import textwrap
import unittest


from conan.test.utils.tools import TestClient, GenConanfile


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
        # Just make sure it doesn't crash
        self.assertIn("<body>", html)


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


def test_graph_info_html_error_reporting_output():
    tc = TestClient()
    tc.save({"lib/conanfile.py": GenConanfile("lib"),
             "ui/conanfile.py": GenConanfile("ui", "1.0").with_requirement("lib/1.0"),
             "math/conanfile.py": GenConanfile("math", "1.0").with_requirement("lib/2.0")})
    tc.run("export lib/ --version=1.0")
    tc.run("export lib/ --version=2.0")
    tc.run("export ui")
    tc.run("export math")

    tc.run("graph info --requires=math/1.0 --requires=ui/1.0 --format=html", assert_error=True,
           redirect_stdout="graph.html")
    assert "ERROR: Version conflict:" in tc.out  # check that it doesn't crash

    # change order,  just in case
    tc.run("graph info --requires=ui/1.0 --requires=math/1.0 --format=html", assert_error=True,
           redirect_stdout="graph.html")
    assert "ERROR: Version conflict:" in tc.out  # check that it doesn't crash

    # direct conflict also doesn't crash
    tc.run("graph info --requires=ui/1.0 --requires=lib/2.0 --format=html", assert_error=True,
           redirect_stdout="graph.html")
    assert "ERROR: Version conflict:" in tc.out  # check that it doesn't crash
    # Check manually
    # tc.run_command(f"{tc.current_folder}/graph.html")


def test_graph_conflict_diamond():
    c = TestClient()
    c.save({"math/conanfile.py": GenConanfile("math"),
            "engine/conanfile.py": GenConanfile("engine", "1.0").with_requires("math/1.0"),
            "ai/conanfile.py": GenConanfile("ai", "1.0").with_requires("math/1.0.1"),
            "game/conanfile.py": GenConanfile("game", "1.0").with_requires("engine/1.0", "ai/1.0"),
            })
    c.run("create math --version=1.0")
    c.run("create math --version=1.0.1")
    c.run("create math --version=1.0.2")
    c.run("create engine")
    c.run("create ai")
    c.run("graph info game --format=html", assert_error=True, redirect_stdout="graph.html")
    # check that it doesn't crash
    assert "ERROR: Version conflict: Conflict between math/1.0.1 and math/1.0 in the graph." in c.out
