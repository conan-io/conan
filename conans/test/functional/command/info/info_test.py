import json
import os
import re
import textwrap
import unittest
from datetime import datetime

from conans import __version__ as client_version
from conans.model.ref import ConanFileReference
from conans.paths import CONANFILE
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.test.utils.tools import TestClient, GenConanfile
from conans.util.files import save


class InfoTest(unittest.TestCase):

    def test_not_found_package_dirty_cache(self):
        # Conan does a lock on the cache, and even if the package doesn't exist
        # left a trailing folder with the filelocks. This test checks
        # it will be cleared
        client = TestClient()
        client.run("info nothing/0.1@user/testing", assert_error=True)
        self.assertEqual(os.listdir(client.cache.store), [])
        # This used to fail in Windows, because of the different case
        client.save({"conanfile.py": GenConanfile().with_name("Nothing").with_version("0.1")})
        client.run("export . user/testing")

    def test_failed_info(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_require("Pkg/1.0.x@user/testing")})
        client.run("info .", assert_error=True)
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
                [HOOK - attribute_checker.py] pre_export(): WARN: Conanfile doesn't have 'url'. It is recommended to add it as attribute
                [HOOK - attribute_checker.py] pre_export(): WARN: Conanfile doesn't have 'license'. It is recommended to add it as attribute
                [HOOK - attribute_checker.py] pre_export(): WARN: Conanfile doesn't have 'description'. It is recommended to add it as attribute
                """)
            self.assertIn(expected_output, self.client.out)

        if number != "Hello2":
            files[CONANFILE] = files[CONANFILE].replace('version = "0.1"',
                                                        'version = "0.1"\n'
                                                        '    url= "myurl"\n'
                                                        '    license = "MIT"\n'
                                                        '    description = "blah"')
        else:
            files[CONANFILE] = files[CONANFILE].replace('version = "0.1"',
                                                        'version = "0.1"\n'
                                                        '    url= "myurl"\n'
                                                        '    license = "MIT", "GPL"\n'
                                                        '    description = """Yo no creo en brujas,\n'
                                                        '                 pero que las hay,\n'
                                                        '                 las hay"""')

        self.client.save(files)
        if export:
            self.client.run("export . lasote/stable")
            self.assertNotIn("WARN: Conanfile doesn't have 'url'", self.client.out)

    def test_install_folder(self):
        conanfile = GenConanfile("Pkg", "0.1").with_setting("build_type")
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("info . -s build_type=Debug")
        self.assertNotIn("ID: 4024617540c4f240a6a5e8911b0de9ef38a11a72", client.out)
        self.assertIn("ID: 5a67a79dbc25fd0fa149a0eb7a20715189a0d988", client.out)

        client.run('install . -s build_type=Debug')
        client.run("info .")  # Re-uses debug from curdir
        self.assertNotIn("ID: 4024617540c4f240a6a5e8911b0de9ef38a11a72", client.out)
        self.assertIn("ID: 5a67a79dbc25fd0fa149a0eb7a20715189a0d988", client.out)

        client.run('install . -s build_type=Release --install-folder=MyInstall')
        client.run("info . --install-folder=MyInstall")  # Re-uses debug from MyInstall folder

        self.assertIn("ID: 4024617540c4f240a6a5e8911b0de9ef38a11a72", client.out)
        self.assertNotIn("ID: 5a67a79dbc25fd0fa149a0eb7a20715189a0d988", client.out)

        client.run('install . -s build_type=Debug --install-folder=MyInstall')
        client.run("info . --install-folder=MyInstall")  # Re-uses debug from MyInstall folder

        self.assertNotIn("ID: 4024617540c4f240a6a5e8911b0de9ef38a11a72", client.out)
        self.assertIn("ID: 5a67a79dbc25fd0fa149a0eb7a20715189a0d988", client.out)

        # Both should raise
        client.run("info . --install-folder=MyInstall -s build_type=Release",
                   assert_error=True)  # Re-uses debug from MyInstall folder

        self.assertIn("--install-folder cannot be used together with a"
                      " host profile (-s, -o, -e or -pr)", client.out)

    def test_graph(self):
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

        def check_ref(ref):
            self.assertEqual(ref.version, "0.1")
            self.assertEqual(ref.user, "lasote")
            self.assertEqual(ref.channel, "stable")

        def check_digraph_line(line):
            self.assertTrue(dot_regex.match(line))

            node_matches = node_regex.findall(line)

            parent_reference = node_matches[0]
            deps_ref = [ConanFileReference.loads(references) for references in node_matches[1:]]

            if parent_reference == "conanfile.py (Hello0/0.1)":
                parent_ref = ConanFileReference("Hello0", None, None, None, validate=False)
            else:
                parent_ref = ConanFileReference.loads(parent_reference)
                check_ref(parent_ref)
            for dep in deps_ref:
                check_ref(dep)
                self.assertIn(dep.name, test_deps[parent_ref.name])

        def check_file(filename):
            with open(filename) as dot_file_contents:
                lines = dot_file_contents.readlines()
                self.assertEqual(lines[0], "digraph {\n")
                for line in lines[1:-1]:
                    check_digraph_line(line)
                self.assertEqual(lines[-1], "}\n")

        create_export(test_deps, "Hello0")

        node_regex = re.compile(r'"([^"]+)"')
        dot_regex = re.compile(r'^\s+"[^"]+" -> "[^"]+"\s+$')

        self.client.run("info . --graph", assert_error=True)

        # arbitrary case - file will be named according to argument
        arg_filename = "test.dot"
        self.client.run("info . --graph=%s" % arg_filename)
        dot_file = os.path.join(self.client.current_folder, arg_filename)
        check_file(dot_file)

    def test_graph_html(self):
        self.client = TestClient()

        test_deps = {
            "Hello0": ["Hello1"],
            "Hello1": [],
        }

        def create_export(testdeps, name):
            deps = testdeps[name]
            for dep in deps:
                create_export(testdeps, dep)

            expanded_deps = ["%s/0.1@lasote/stable" % dep for dep in deps]
            export = False if name == "Hello0" else True
            self._create(name, "0.1", expanded_deps, export=export)

        create_export(test_deps, "Hello0")

        # arbitrary case - file will be named according to argument
        arg_filename = "test.html"
        self.client.run("info . --graph=%s" % arg_filename)
        html = self.client.load(arg_filename)
        self.assertIn("<body>", html)
        self.assertIn("{ from: 0, to: 1 }", html)
        self.assertIn("id: 0,\n                        label: 'Hello0/0.1',", html)
        self.assertIn("Conan <b>v{}</b> <script>document.write(new Date().getFullYear())</script>"
                      " JFrog LTD. <a>https://conan.io</a>"
                      .format(client_version, datetime.today().year), html)

    def test_graph_html_embedded_visj(self):
        client = TestClient()
        visjs_path = os.path.join(client.cache_folder, "vis.min.js")
        viscss_path = os.path.join(client.cache_folder, "vis.min.css")
        save(visjs_path, "")
        save(viscss_path, "")
        client.save({"conanfile.txt": ""})
        client.run("info . --graph=file.html")
        html = client.load("file.html")
        self.assertIn("<body>", html)
        self.assertNotIn("cloudflare", html)
        self.assertIn(visjs_path, html)
        self.assertIn(viscss_path, html)

    def test_info_build_requires(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . tool/0.1@user/channel")
        client.run("create . dep/0.1@user/channel")
        conanfile = GenConanfile().with_require("dep/0.1@user/channel")
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
        html = client.load("file.html")
        self.assertIn("html", html)
        # To check that this node is not duplicated
        self.assertEqual(1, html.count("label: 'dep/0.1'"))
        self.assertIn("label: 'Pkg2/0.1',\n                        "
                      "shape: 'box',\n                        "
                      "color: { background: 'Khaki'},", html)
        self.assertIn("label: 'Pkg/0.1',\n                        "
                      "shape: 'box',\n                        "
                      "color: { background: 'Khaki'},", html)
        self.assertIn("label: 'tool/0.1',\n                        "
                      "shape: 'ellipse',\n                        "
                      "color: { background: 'SkyBlue'},", html)

    def test_only_names(self):
        self.client = TestClient()
        self._create("Hello0", "0.1")
        self._create("Hello1", "0.1", ["Hello0/0.1@lasote/stable"])
        self._create("Hello2", "0.1", ["Hello1/0.1@lasote/stable"], export=False)

        self.client.run("info . --only None")
        self.assertEqual(["Hello0/0.1@lasote/stable", "Hello1/0.1@lasote/stable",
                          "conanfile.py (Hello2/0.1)"],
                         str(self.client.out).splitlines()[-3:])
        self.client.run("info . --only=date")
        lines = [(line if "date" not in line else "Date")
                 for line in str(self.client.out).splitlines()]
        self.assertEqual(["Hello0/0.1@lasote/stable", "Date",
                          "Hello1/0.1@lasote/stable", "Date",
                          "conanfile.py (Hello2/0.1)"], lines)

        self.client.run("info . --only=invalid", assert_error=True)
        self.assertIn("Invalid --only value", self.client.out)
        self.assertNotIn("with --path specified, allowed values:", self.client.out)

        self.client.run("info . --paths --only=bad", assert_error=True)
        self.assertIn("Invalid --only value", self.client.out)
        self.assertIn("with --path specified, allowed values:", self.client.out)

    def test_cwd(self):
        client = TestClient()
        conanfile = GenConanfile("Pkg", "0.1").with_setting("build_type")
        client.save({"subfolder/conanfile.py": conanfile})
        client.run("export ./subfolder lasote/testing")

        client.run("info ./subfolder")
        self.assertIn("conanfile.py (Pkg/0.1)", client.out)

        client.run("info ./subfolder --build-order Pkg/0.1@lasote/testing --json=jsonfile.txt")
        path = os.path.join(client.current_folder, "jsonfile.txt")
        self.assertTrue(os.path.exists(path))

    def test_info_virtual(self):
        # Checking that "Required by: virtual" doesnt appear in the output
        self.client = TestClient()
        self._create("Hello", "0.1")
        self.client.run("info Hello/0.1@lasote/stable")
        self.assertNotIn("virtual", self.client.out)
        self.assertNotIn("Required", self.client.out)

    def test_reuse(self):
        self.client = TestClient()
        self._create("Hello0", "0.1")
        self._create("Hello1", "0.1", ["Hello0/0.1@lasote/stable"])
        self._create("Hello2", "0.1", ["Hello1/0.1@lasote/stable"], export=False)

        self.client.run("info . -u")

        self.assertIn("Creation date: ", self.client.out)
        self.assertIn("ID: ", self.client.out)
        self.assertIn("BuildID: ", self.client.out)

        expected_output = textwrap.dedent("""\
            Hello0/0.1@lasote/stable
                Remote: None
                URL: myurl
                License: MIT
                Description: blah
                Provides: Hello0
                Recipe: No remote%s
                Binary: Missing
                Binary remote: None
                Required by:
                    Hello1/0.1@lasote/stable
            Hello1/0.1@lasote/stable
                Remote: None
                URL: myurl
                License: MIT
                Description: blah
                Provides: Hello1
                Recipe: No remote%s
                Binary: Missing
                Binary remote: None
                Required by:
                    conanfile.py (Hello2/0.1)
                Requires:
                    Hello0/0.1@lasote/stable
            conanfile.py (Hello2/0.1)
                URL: myurl
                Licenses: MIT, GPL
                Description: Yo no creo en brujas,
                             pero que las hay,
                             las hay
                Provides: Hello2
                Requires:
                    Hello1/0.1@lasote/stable""")

        expected_output = expected_output % (
            "\n    Revision: 63865a1afa3a2666b2f75cbc7745e8a4"
            "\n    Package revision: None",
            "\n    Revision: b2600f68000fa492234c0452214e0bbc"
            "\n    Package revision: None",) \
            if self.client.cache.config.revisions_enabled else expected_output % ("", "")

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
        expected_output = textwrap.dedent("""\
            Hello0/0.1@lasote/stable
                URL: myurl
            Hello1/0.1@lasote/stable
                URL: myurl
            conanfile.py (Hello2/0.1)
                URL: myurl""")

        self.assertIn(expected_output, clean_output(self.client.out))
        self.client.run("info . -u --only=url --only=license")
        expected_output = textwrap.dedent("""\
            Hello0/0.1@lasote/stable
                URL: myurl
                License: MIT
            Hello1/0.1@lasote/stable
                URL: myurl
                License: MIT
            conanfile.py (Hello2/0.1)
                URL: myurl
                Licenses: MIT, GPL""")

        self.assertIn(expected_output, clean_output(self.client.out))

        self.client.run("info . -u --only=url --only=license --only=description")
        expected_output = textwrap.dedent("""\
            Hello0/0.1@lasote/stable
                URL: myurl
                License: MIT
                Description: blah
            Hello1/0.1@lasote/stable
                URL: myurl
                License: MIT
                Description: blah
            conanfile.py (Hello2/0.1)
                URL: myurl
                Licenses: MIT, GPL
                Description: Yo no creo en brujas,
                             pero que las hay,
                             las hay""")
        self.assertIn(expected_output, clean_output(self.client.out))

    def test_json_info_outputs(self):
        self.client = TestClient()
        self._create("LibA", "0.1")
        self._create("LibE", "0.1")
        self._create("LibF", "0.1")

        self._create("LibB", "0.1", ["LibA/0.1@lasote/stable", "LibE/0.1@lasote/stable"])
        self._create("LibC", "0.1", ["LibA/0.1@lasote/stable", "LibF/0.1@lasote/stable"])

        self._create("LibD", "0.1", ["LibB/0.1@lasote/stable", "LibC/0.1@lasote/stable"],
                     export=False)

        self.client.run("info . -u --json=output.json")

        # Check a couple of values in the generated JSON
        content = json.loads(self.client.load("output.json"))
        self.assertEqual(content[0]["reference"], "LibA/0.1@lasote/stable")
        self.assertEqual(content[0]["license"][0], "MIT")
        self.assertEqual(content[0]["description"], "blah")
        self.assertEqual(content[0]["revision"], "22b1dc946e5566f5b2549e1b285d3fa7")
        self.assertEqual(content[0]["package_revision"], None)
        self.assertEqual(content[1]["url"], "myurl")
        self.assertEqual(content[1]["required_by"][0], "conanfile.py (LibD/0.1)")

    def test_build_order(self):
        self.client = TestClient()
        self._create("Hello0", "0.1")
        self._create("Hello1", "0.1", ["Hello0/0.1@lasote/stable"])
        self._create("Hello2", "0.1", ["Hello1/0.1@lasote/stable"], export=False)

        self.client.run("info ./conanfile.py -bo=Hello0/0.1@lasote/stable")
        self.assertIn("[Hello0/0.1@lasote/stable], [Hello1/0.1@lasote/stable]",
                      self.client.out)

        self.client.run("info conanfile.py -bo=Hello1/0.1@lasote/stable")
        self.assertIn("[Hello1/0.1@lasote/stable]", self.client.out)

        self.client.run("info ./ -bo=Hello1/0.1@lasote/stable -bo=Hello0/0.1@lasote/stable")
        self.assertIn("[Hello0/0.1@lasote/stable], [Hello1/0.1@lasote/stable]",
                      self.client.out)

        self.client.run("info Hello1/0.1@lasote/stable -bo=Hello0/0.1@lasote/stable")
        self.assertIn("[Hello0/0.1@lasote/stable], [Hello1/0.1@lasote/stable]\n", self.client.out)

        self.client.run("info Hello1/0.1@lasote/stable -bo=Hello0/0.1@lasote/stable "
                        "--json=file.json")
        self.assertEqual('{"groups": [["Hello0/0.1@lasote/stable"], ["Hello1/0.1@lasote/stable"]]}',
                         self.client.load("file.json"))

        self.client.run("info Hello1/0.1@lasote/stable -bo=Hello0/0.1@lasote/stable --json")
        self.assertIn('{"groups": [["Hello0/0.1@lasote/stable"], ["Hello1/0.1@lasote/stable"]]}',
                      self.client.out)

        self.client.run("info Hello1/0.1@lasote/stable --build-order=Hello0/0.1@lasote/stable "
                        "--graph=index.html", assert_error=True)
        self.assertIn("--build-order cannot be used together with --graph", self.client.out)

    def test_build_order_build_requires(self):
        # https://github.com/conan-io/conan/issues/3267
        client = TestClient()
        conanfile = str(GenConanfile())
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

    def test_build_order_privates(self):
        # https://github.com/conan-io/conan/issues/3267
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . tool/0.1@user/channel")
        client.save({"conanfile.py": GenConanfile().with_require("tool/0.1@user/channel")})
        client.run("create . dep/0.1@user/channel")
        client.save({"conanfile.py": GenConanfile().with_require("dep/0.1@user/channel",
                                                                 private=True)})
        client.run("export . Pkg/0.1@user/channel")
        client.run("export . Pkg2/0.1@user/channel")
        client.save({"conanfile.txt": "[requires]\nPkg/0.1@user/channel\nPkg2/0.1@user/channel"},
                    clean_first=True)
        client.run("info . -bo=tool/0.1@user/channel")
        self.assertIn("[tool/0.1@user/channel], [dep/0.1@user/channel], "
                      "[Pkg/0.1@user/channel, Pkg2/0.1@user/channel]",
                      client.out)

    def test_diamond_build_order(self):
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
                      self.client.out)
        self.client.run("info . -bo=LibB/0.1@lasote/stable")
        self.assertIn("[LibB/0.1@lasote/stable]", self.client.out)
        self.client.run("info . -bo=LibE/0.1@lasote/stable")
        self.assertIn("[LibE/0.1@lasote/stable], [LibB/0.1@lasote/stable]",
                      self.client.out)
        self.client.run("info . -bo=LibF/0.1@lasote/stable")
        self.assertIn("[LibF/0.1@lasote/stable], [LibC/0.1@lasote/stable]",
                      self.client.out)
        self.client.run("info . -bo=Dev1/0.1@lasote/stable")
        self.assertEqual("WARN: Usage of `--build-order` argument is deprecated and can return wrong"
                         " results. Use `conan lock build-order ...` instead.\n\n", self.client.out)
        self.client.run("info . -bo=LibG/0.1@lasote/stable")
        self.assertEqual("WARN: Usage of `--build-order` argument is deprecated and can return wrong"
                         " results. Use `conan lock build-order ...` instead.\n\n", self.client.out)

        self.client.run("info . --build-order=ALL")
        self.assertIn("[LibA/0.1@lasote/stable, LibE/0.1@lasote/stable, LibF/0.1@lasote/stable], "
                      "[LibB/0.1@lasote/stable, LibC/0.1@lasote/stable]",
                      self.client.out)

        self.client.run("info . --build-order=ALL")
        self.assertIn("[LibA/0.1@lasote/stable, LibE/0.1@lasote/stable, "
                      "LibF/0.1@lasote/stable], [LibB/0.1@lasote/stable, LibC/0.1@lasote/stable]",
                      self.client.out)

    def test_wrong_path_parameter(self):
        self.client = TestClient()

        self.client.run("info", assert_error=True)
        self.assertIn("ERROR: Exiting with code: 2", self.client.out)

        self.client.run("info not_real_path", assert_error=True)
        self.assertIn("ERROR: Conanfile not found", self.client.out)

        self.client.run("info conanfile.txt", assert_error=True)
        self.assertIn("ERROR: Conanfile not found", self.client.out)

    def test_common_attributes(self):
        client = TestClient()

        conanfile = GenConanfile("Pkg", "0.1").with_setting("build_type")
        client.save({"subfolder/conanfile.py": conanfile})
        client.run("export ./subfolder lasote/testing")

        client.run("info ./subfolder")

        self.assertIn("conanfile.py (Pkg/0.1)", client.out)
        self.assertNotIn("License:", client.out)
        self.assertNotIn("Author:", client.out)
        self.assertNotIn("Topics:", client.out)
        self.assertNotIn("Homepage:", client.out)
        self.assertNotIn("URL:", client.out)

    def test_full_attributes(self):
        client = TestClient()

        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class MyTest(ConanFile):
                name = "Pkg"
                version = "0.2"
                settings = "build_type"
                author = "John Doe"
                license = "MIT"
                url = "https://foo.bar.baz"
                homepage = "https://foo.bar.site"
                topics = ("foo", "bar", "qux")
                provides = ("libjpeg", "libjpg")
                deprecated = "other-pkg"
        """)

        client.save({"subfolder/conanfile.py": conanfile})
        client.run("export ./subfolder lasote/testing")
        client.run("info ./subfolder")

        self.assertIn("conanfile.py (Pkg/0.2)", client.out)
        self.assertIn("License: MIT", client.out)
        self.assertIn("Author: John Doe", client.out)
        self.assertIn("Topics: foo, bar, qux", client.out)
        self.assertIn("URL: https://foo.bar.baz", client.out)
        self.assertIn("Homepage: https://foo.bar.site", client.out)
        self.assertIn("Provides: libjpeg, libjpg", client.out)
        self.assertIn("Deprecated: other-pkg", client.out)

        client.run("info ./subfolder --json=output.json")
        output = json.loads(client.load('output.json'))[0]
        self.assertEquals(output['reference'], 'conanfile.py (Pkg/0.2)')
        self.assertListEqual(output['license'], ['MIT', ])
        self.assertEquals(output['author'], 'John Doe')
        self.assertListEqual(output['topics'], ['foo', 'bar', 'qux'])
        self.assertEquals(output['url'], 'https://foo.bar.baz')
        self.assertEquals(output['homepage'], 'https://foo.bar.site')
        self.assertListEqual(output['provides'], ['libjpeg', 'libjpg'])
        self.assertEquals(output['deprecated'], 'other-pkg')

    def test_topics_graph(self):

        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class MyTest(ConanFile):
                name = "Pkg"
                version = "0.2"
                topics = ("foo", "bar", "qux")
        """)

        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("export . lasote/testing")

        # Topics as tuple
        client.run("info Pkg/0.2@lasote/testing --graph file.html")
        html_content = client.load("file.html")
        self.assertIn("<h3>Pkg/0.2@lasote/testing</h3>", html_content)
        self.assertIn("<li><b>topics</b>: foo, bar, qux</li>", html_content)

        # Topics as a string
        conanfile = conanfile.replace("(\"foo\", \"bar\", \"qux\")", "\"foo\"")
        client.save({"conanfile.py": conanfile}, clean_first=True)
        client.run("export . lasote/testing")
        client.run("info Pkg/0.2@lasote/testing --graph file.html")
        html_content = client.load("file.html")
        self.assertIn("<h3>Pkg/0.2@lasote/testing</h3>", html_content)
        self.assertIn("<li><b>topics</b>: foo", html_content)

    def test_wrong_graph_info(self):
        # https://github.com/conan-io/conan/issues/4443
        conanfile = GenConanfile().with_name("Hello").with_version("0.1")
        client = TestClient()
        client.save({"conanfile.py": str(conanfile)})
        client.run("install .")
        path = os.path.join(client.current_folder, "graph_info.json")
        graph_info = client.load(path)
        graph_info = json.loads(graph_info)
        graph_info.pop("root")
        save(path, json.dumps(graph_info))
        client.run("info .")
        self.assertIn("conanfile.py (Hello/0.1)", client.out)
        save(path, "broken thing")
        client.run("info .", assert_error=True)
        self.assertIn("ERROR: Error parsing GraphInfo from file", client.out)

    def test_previous_lockfile_error(self):
        # https://github.com/conan-io/conan/issues/5479
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_name("pkg").with_version("0.1")})
        client.run("create . user/testing")
        client.save({"conanfile.py": GenConanfile().with_name("other").with_version("0.1")
                    .with_option("shared", [True, False])
                    .with_default_option("shared", False)})
        client.run("install . -o shared=True")
        client.run("info pkg/0.1@user/testing")
        self.assertIn("pkg/0.1@user/testing", client.out)
        self.assertNotIn("shared", client.out)
