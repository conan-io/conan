import unittest
import os
import re
from conans.test.utils.tools import TestClient
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.paths import CONANFILE
from conans.model.ref import ConanFileReference
import textwrap
from conans.util.files import load


class InfoTest(unittest.TestCase):

    def failed_info_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    requires = "Pkg/1.0.x@user/testing"
"""
        client.save({"conanfile.py": conanfile})
        error = client.run("info .", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Pkg/1.0.x@user/testing: Not found in local cache", client.out)
        client.run("search")
        self.assertIn("There are no packages", client.out)
        self.assertNotIn("Pkg/1.0.x@user/testing", client.out)

    def _create(self, number, version, deps=None, deps_dev=None, export=True):
        files = cpp_hello_conan_files(number, version, deps, build=False)
        files[CONANFILE] = files[CONANFILE].replace("config(", "configure(")
        if deps_dev:
            files[CONANFILE] = files[CONANFILE].replace("exports = '*'", """exports = '*'
    dev_requires=%s
""" % ",".join('"%s"' % d for d in deps_dev))

        self.client.save(files, clean_first=True)
        if export:
            self.client.run("export . lasote/stable")
            expected_output = textwrap.dedent(
                """\
                [PLUGIN - attribute_checker] pre_export(): WARN: Conanfile doesn't have 'url'. It is recommended to add it as attribute
                [PLUGIN - attribute_checker] pre_export(): WARN: Conanfile doesn't have 'license'. It is recommended to add it as attribute
                [PLUGIN - attribute_checker] pre_export(): WARN: Conanfile doesn't have 'description'. It is recommended to add it as attribute
                """)
            self.assertIn(expected_output, self.client.user_io.out)

        if number != "Hello2":
            files[CONANFILE] = files[CONANFILE].replace('version = "0.1"',
                                                        'version = "0.1"\n'
                                                        '    url= "myurl"\n'
                                                        '    license = "MIT"')
        else:
            files[CONANFILE] = files[CONANFILE].replace('version = "0.1"',
                                                        'version = "0.1"\n'
                                                        '    url= "myurl"\n'
                                                        '    license = "MIT", "GPL"')

        self.client.save(files)
        if export:
            self.client.run("export . lasote/stable")
            self.assertNotIn("WARN: Conanfile doesn't have 'url'", self.client.user_io.out)

    def install_folder_test(self):

        conanfile = """from conans import ConanFile
from conans.util.files import save

class MyTest(ConanFile):
    name = "Pkg"
    version = "0.1"
    settings = "build_type"

"""
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("info . -s build_type=Debug")
        self.assertNotIn("ID: 4024617540c4f240a6a5e8911b0de9ef38a11a72", client.user_io.out)
        self.assertIn("ID: 5a67a79dbc25fd0fa149a0eb7a20715189a0d988", client.user_io.out)

        client.run('install . -s build_type=Debug')
        client.run("info .")  # Re-uses debug from curdir
        self.assertNotIn("ID: 4024617540c4f240a6a5e8911b0de9ef38a11a72", client.user_io.out)
        self.assertIn("ID: 5a67a79dbc25fd0fa149a0eb7a20715189a0d988", client.user_io.out)

        client.run('install . -s build_type=Release --install-folder=MyInstall')
        client.run("info . --install-folder=MyInstall")  # Re-uses debug from MyInstall folder

        self.assertIn("ID: 4024617540c4f240a6a5e8911b0de9ef38a11a72", client.user_io.out)
        self.assertNotIn("ID: 5a67a79dbc25fd0fa149a0eb7a20715189a0d988", client.user_io.out)

        client.run('install . -s build_type=Debug --install-folder=MyInstall')
        client.run("info . --install-folder=MyInstall")  # Re-uses debug from MyInstall folder

        self.assertNotIn("ID: 4024617540c4f240a6a5e8911b0de9ef38a11a72", client.user_io.out)
        self.assertIn("ID: 5a67a79dbc25fd0fa149a0eb7a20715189a0d988", client.user_io.out)

        # Both should raise
        error = client.run("info . --install-folder=MyInstall -s build_type=Release",
                           ignore_error=True)  # Re-uses debug from MyInstall folder
        self.assertTrue(error)
        self.assertIn("--install-folder cannot be used together with -s, -o, -e or -pr", client.out)

    def graph_test(self):
        self.client = TestClient()

        test_deps = {
            "Hello0": ["Hello1", "Hello2", "Hello3"],
            "Hello1": ["Hello4"],
            "Hello2": [],
            "Hello3": ["Hello7"],
            "Hello4": ["Hello5", "Hello6"],
            "Hello5": [],
            "Hello6": [],
            "Hello7": ["Hello8"],
            "Hello8": ["Hello9", "Hello10"],
            "Hello9": [],
            "Hello10": [],
        }

        def create_export(test_deps, name):
            deps = test_deps[name]
            for dep in deps:
                create_export(test_deps, dep)

            expanded_deps = ["%s/0.1@lasote/stable" % dep for dep in deps]
            export = False if name == "Hello0" else True
            self._create(name, "0.1", expanded_deps, export=export)

        def check_conan_ref(ref):
            self.assertEqual(ref.version, "0.1")
            self.assertEqual(ref.user, "lasote")
            self.assertEqual(ref.channel, "stable")

        def check_digraph_line(line):
            self.assertTrue(dot_regex.match(line))

            # root node (current project) is special case
            line = line.replace("@PROJECT", "@lasote/stable")

            node_matches = node_regex.findall(line)

            parent = ConanFileReference.loads(node_matches[0])
            deps = [ConanFileReference.loads(ref) for ref in node_matches[1:]]

            check_conan_ref(parent)
            for dep in deps:
                check_conan_ref(dep)
                self.assertIn(dep.name, test_deps[parent.name])

        def check_file(dot_file):
            with open(dot_file) as dot_file_contents:
                lines = dot_file_contents.readlines()
                self.assertEqual(lines[0], "digraph {\n")
                for line in lines[1:-1]:
                    check_digraph_line(line)
                self.assertEqual(lines[-1], "}\n")

        create_export(test_deps, "Hello0")

        node_regex = re.compile(r'"([^"]+)"')
        dot_regex = re.compile(r'^\s+"[^"]+" -> {"[^"]+"( "[^"]+")*}$')

        # default case - file will be named graph.dot
        error = self.client.run("info . --graph", ignore_error=True)
        self.assertTrue(error)

        # arbitrary case - file will be named according to argument
        arg_filename = "test.dot"
        self.client.run("info . --graph=%s" % arg_filename)
        dot_file = os.path.join(self.client.current_folder, arg_filename)
        check_file(dot_file)

    def graph_html_test(self):
        self.client = TestClient()

        test_deps = {
            "Hello0": ["Hello1"],
            "Hello1": [],
        }

        def create_export(test_deps, name):
            deps = test_deps[name]
            for dep in deps:
                create_export(test_deps, dep)

            expanded_deps = ["%s/0.1@lasote/stable" % dep for dep in deps]
            export = False if name == "Hello0" else True
            self._create(name, "0.1", expanded_deps, export=export)

        create_export(test_deps, "Hello0")

        # arbitrary case - file will be named according to argument
        arg_filename = "test.html"
        self.client.run("info . --graph=%s" % arg_filename)
        arg_filename = os.path.join(self.client.current_folder, arg_filename)
        html = load(arg_filename)
        self.assertIn("<body>", html)
        self.assertIn("{ from: 0, to: 1 }", html)
        self.assertIn("id: 0, label: 'Hello0/0.1@PROJECT'", html)

    def info_build_requires_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class AConan(ConanFile):
    pass
    """
        client.save({"conanfile.py": conanfile})
        client.run("create . tool/0.1@user/channel")
        client.run("create . dep/0.1@user/channel")
        conanfile = conanfile + 'requires = "dep/0.1@user/channel"'
        client.save({"conanfile.py": conanfile})
        client.run("export . Pkg/0.1@user/channel")
        client.run("export . Pkg2/0.1@user/channel")
        client.save({"conanfile.txt": "[requires]\nPkg/0.1@user/channel\nPkg2/0.1@user/channel",
                     "myprofile": "[build_requires]\ntool/0.1@user/channel"}, clean_first=True)
        client.run("info . -pr=myprofile --dry-build=missing")
        # Check that there is only 1 output for tool, not repeated many times
        pkgs = [line for line in str(client.out).splitlines() if line.startswith("tool")]
        self.assertEqual(len(pkgs), 1)

        client.run("info . -pr=myprofile --dry-build=missing --graph=file.html")
        html_path = os.path.join(client.current_folder, "file.html")
        html = load(html_path)
        self.assertIn("html", html)
        # To check that this node is not duplicated
        self.assertEqual(1, html.count("label: 'dep/0.1'"))
        self.assertIn("label: 'Pkg2/0.1', shape: 'box', color: {background: 'Khaki'}", html)
        self.assertIn("label: 'Pkg/0.1', shape: 'box', color: {background: 'Khaki'}", html)
        self.assertIn("label: 'tool/0.1', shape: 'ellipse', color: {background: 'SkyBlue'}", html)

    def only_names_test(self):
        self.client = TestClient()
        self._create("Hello0", "0.1")
        self._create("Hello1", "0.1", ["Hello0/0.1@lasote/stable"])
        self._create("Hello2", "0.1", ["Hello1/0.1@lasote/stable"], export=False)

        self.client.run("info . --only None")
        self.assertEqual(["Hello2/0.1@PROJECT", "Hello0/0.1@lasote/stable",
                          "Hello1/0.1@lasote/stable"], str(self.client.user_io.out).splitlines())
        self.client.run("info . --only=date")
        lines = [(line if "date" not in line else "Date")
                 for line in str(self.client.user_io.out).splitlines()]
        self.assertEqual(["Hello2/0.1@PROJECT", "Hello0/0.1@lasote/stable", "Date",
                          "Hello1/0.1@lasote/stable", "Date"], lines)

        self.client.run("info . --only=invalid", ignore_error=True)
        self.assertIn("Invalid --only value", self.client.user_io.out)
        self.assertNotIn("with --path specified, allowed values:", self.client.user_io.out)

        self.client.run("info . --paths --only=bad", ignore_error=True)
        self.assertIn("Invalid --only value", self.client.user_io.out)
        self.assertIn("with --path specified, allowed values:", self.client.user_io.out)

    def test_cwd(self):
        self.client = TestClient()
        conanfile = """from conans import ConanFile
from conans.util.files import load, save

class MyTest(ConanFile):
    name = "Pkg"
    version = "0.1"
    settings = "build_type"

"""
        self.client.save({"subfolder/conanfile.py": conanfile})
        self.client.run("export ./subfolder lasote/testing")

        self.client.run("info ./subfolder")
        self.assertIn("Pkg/0.1@PROJECT", self.client.user_io.out)

        self.client.run("info ./subfolder --build-order "
                        "Pkg/0.1@lasote/testing --json=jsonfile.txt")
        path = os.path.join(self.client.current_folder, "jsonfile.txt")
        self.assertTrue(os.path.exists(path))

    def reuse_test(self):
        self.client = TestClient()
        self._create("Hello0", "0.1")
        self._create("Hello1", "0.1", ["Hello0/0.1@lasote/stable"])
        self._create("Hello2", "0.1", ["Hello1/0.1@lasote/stable"], export=False)

        self.client.run("info . -u")

        self.assertIn("Creation date: ", self.client.user_io.out)
        self.assertIn("ID: ", self.client.user_io.out)
        self.assertIn("BuildID: ", self.client.user_io.out)

        expected_output = textwrap.dedent(
            """\
            Hello2/0.1@PROJECT
                URL: myurl
                Licenses: MIT, GPL
                Requires:
                    Hello1/0.1@lasote/stable
            Hello0/0.1@lasote/stable
                Remote: None
                URL: myurl
                License: MIT
                Recipe: No remote
                Binary: Missing
                Binary remote: None
                Required by:
                    Hello1/0.1@lasote/stable
            Hello1/0.1@lasote/stable
                Remote: None
                URL: myurl
                License: MIT
                Recipe: No remote
                Binary: Missing
                Binary remote: None
                Required by:
                    Hello2/0.1@PROJECT
                Requires:
                    Hello0/0.1@lasote/stable""")

        def clean_output(output):
            return "\n".join([line for line in str(output).splitlines()
                              if not line.strip().startswith("Creation date") and
                              not line.strip().startswith("ID") and
                              not line.strip().startswith("BuildID") and
                              not line.strip().startswith("export_folder") and
                              not line.strip().startswith("build_folder") and
                              not line.strip().startswith("source_folder") and
                              not line.strip().startswith("package_folder")])

        # The timestamp is variable so we can't check the equality
        self.assertIn(expected_output, clean_output(self.client.out))

        self.client.run("info . -u --only=url")
        expected_output = textwrap.dedent(
            """\
            Hello2/0.1@PROJECT
                URL: myurl
            Hello0/0.1@lasote/stable
                URL: myurl
            Hello1/0.1@lasote/stable
                URL: myurl""")

        self.assertIn(expected_output, clean_output(self.client.user_io.out))
        self.client.run("info . -u --only=url --only=license")
        expected_output = textwrap.dedent(
            """\
            Hello2/0.1@PROJECT
                URL: myurl
                Licenses: MIT, GPL
            Hello0/0.1@lasote/stable
                URL: myurl
                License: MIT
            Hello1/0.1@lasote/stable
                URL: myurl
                License: MIT""")
        self.assertIn(expected_output, clean_output(self.client.user_io.out))

    def build_order_test(self):
        self.client = TestClient()
        self._create("Hello0", "0.1")
        self._create("Hello1", "0.1", ["Hello0/0.1@lasote/stable"])
        self._create("Hello2", "0.1", ["Hello1/0.1@lasote/stable"], export=False)

        self.client.run("info ./conanfile.py -bo=Hello0/0.1@lasote/stable")
        self.assertIn("[Hello0/0.1@lasote/stable], [Hello1/0.1@lasote/stable]",
                      self.client.user_io.out)

        self.client.run("info conanfile.py -bo=Hello1/0.1@lasote/stable")
        self.assertIn("[Hello1/0.1@lasote/stable]", self.client.user_io.out)

        self.client.run("info ./ -bo=Hello1/0.1@lasote/stable -bo=Hello0/0.1@lasote/stable")
        self.assertIn("[Hello0/0.1@lasote/stable], [Hello1/0.1@lasote/stable]",
                      self.client.user_io.out)

        self.client.run("info Hello1/0.1@lasote/stable -bo=Hello0/0.1@lasote/stable")
        self.assertEqual("[Hello0/0.1@lasote/stable], [Hello1/0.1@lasote/stable]\n",
                         self.client.user_io.out)

        self.client.run("info Hello1/0.1@lasote/stable -bo=Hello0/0.1@lasote/stable --json=file.json")
        self.assertEqual('{"groups": [["Hello0/0.1@lasote/stable"], ["Hello1/0.1@lasote/stable"]]}',
                         load(os.path.join(self.client.current_folder, "file.json")))

        self.client.run("info Hello1/0.1@lasote/stable -bo=Hello0/0.1@lasote/stable --json")
        self.assertIn('{"groups": [["Hello0/0.1@lasote/stable"], ["Hello1/0.1@lasote/stable"]]}',
                      self.client.out)

    def build_order_build_requires_test(self):
        # https://github.com/conan-io/conan/issues/3267
        client = TestClient()
        conanfile = """from conans import ConanFile
class AConan(ConanFile):
    pass
    """
        client.save({"conanfile.py": conanfile})
        client.run("create . tool/0.1@user/channel")
        client.run("create . dep/0.1@user/channel")
        conanfile = conanfile + 'requires = "dep/0.1@user/channel"'
        client.save({"conanfile.py": conanfile})
        client.run("export . Pkg/0.1@user/channel")
        client.run("export . Pkg2/0.1@user/channel")
        client.save({"conanfile.txt": "[requires]\nPkg/0.1@user/channel\nPkg2/0.1@user/channel",
                     "myprofile": "[build_requires]\ntool/0.1@user/channel"}, clean_first=True)
        client.run("info . -pr=myprofile -bo=tool/0.1@user/channel")
        self.assertIn("[tool/0.1@user/channel], [Pkg/0.1@user/channel, Pkg2/0.1@user/channel]",
                      client.out)

    def build_order_privates_test(self):
        # https://github.com/conan-io/conan/issues/3267
        client = TestClient()
        conanfile = """from conans import ConanFile
class AConan(ConanFile):
    pass
    """
        client.save({"conanfile.py": conanfile})
        client.run("create . tool/0.1@user/channel")
        conanfile_dep = conanfile + 'requires = "tool/0.1@user/channel"'
        client.save({"conanfile.py": conanfile_dep})
        client.run("create . dep/0.1@user/channel")
        conanfile_pkg = conanfile + 'requires = ("dep/0.1@user/channel", "private"),'
        client.save({"conanfile.py": conanfile_pkg})
        client.run("export . Pkg/0.1@user/channel")
        client.run("export . Pkg2/0.1@user/channel")
        client.save({"conanfile.txt": "[requires]\nPkg/0.1@user/channel\nPkg2/0.1@user/channel"},
                    clean_first=True)
        client.run("info . -bo=tool/0.1@user/channel")
        self.assertIn("[tool/0.1@user/channel], [dep/0.1@user/channel], "
                      "[Pkg/0.1@user/channel, Pkg2/0.1@user/channel]",
                      client.out)

    def diamond_build_order_test(self):
        self.client = TestClient()
        self._create("LibA", "0.1")
        self._create("LibE", "0.1")
        self._create("LibF", "0.1")

        self._create("LibB", "0.1", ["LibA/0.1@lasote/stable", "LibE/0.1@lasote/stable"])
        self._create("LibC", "0.1", ["LibA/0.1@lasote/stable", "LibF/0.1@lasote/stable"])

        self._create("LibD", "0.1", ["LibB/0.1@lasote/stable", "LibC/0.1@lasote/stable"],
                     export=False)

        self.client.run("info . -bo=LibA/0.1@lasote/stable")
        self.assertIn("[LibA/0.1@lasote/stable], "
                      "[LibB/0.1@lasote/stable, LibC/0.1@lasote/stable]",
                      self.client.user_io.out)
        self.client.run("info . -bo=LibB/0.1@lasote/stable")
        self.assertIn("[LibB/0.1@lasote/stable]", self.client.user_io.out)
        self.client.run("info . -bo=LibE/0.1@lasote/stable")
        self.assertIn("[LibE/0.1@lasote/stable], [LibB/0.1@lasote/stable]",
                      self.client.user_io.out)
        self.client.run("info . -bo=LibF/0.1@lasote/stable")
        self.assertIn("[LibF/0.1@lasote/stable], [LibC/0.1@lasote/stable]",
                      self.client.user_io.out)
        self.client.run("info . -bo=Dev1/0.1@lasote/stable")
        self.assertEqual("\n", self.client.user_io.out)
        self.client.run("info . -bo=LibG/0.1@lasote/stable")
        self.assertEqual("\n", self.client.user_io.out)

        self.client.run("info . --build-order=ALL")
        self.assertIn("[LibA/0.1@lasote/stable, LibE/0.1@lasote/stable, LibF/0.1@lasote/stable], "
                      "[LibB/0.1@lasote/stable, LibC/0.1@lasote/stable]",
                      self.client.user_io.out)

        self.client.run("info . --build-order=ALL")
        self.assertIn("[LibA/0.1@lasote/stable, LibE/0.1@lasote/stable, "
                      "LibF/0.1@lasote/stable], [LibB/0.1@lasote/stable, LibC/0.1@lasote/stable]",
                      self.client.user_io.out)

    def wrong_path_parameter_test(self):
        self.client = TestClient()

        self.client.run("info", ignore_error=True)
        self.assertIn("ERROR: Exiting with code: 2", self.client.out)

        self.client.run("info not_real_path", ignore_error=True)
        self.assertIn("ERROR: Conanfile not found", self.client.out)

        self.client.run("info conanfile.txt", ignore_error=True)
        self.assertIn("ERROR: Conanfile not found", self.client.out)
