import json
import os
import textwrap
import unittest
from datetime import datetime

from conans import __version__ as client_version
from conans.test.utils.tools import TestClient, GenConanfile, NO_SETTINGS_PACKAGE_ID
from conans.util.files import save, load


class InfoTest(unittest.TestCase):

    def _create(self, name, version, deps=None, export=True):
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
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
            self.client.run("export . lasote/stable")

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

        def create_export(testdeps, name):
            deps = testdeps[name]
            for dep in deps:
                create_export(testdeps, dep)

            expanded_deps = ["%s/0.1@lasote/stable" % dep for dep in deps]
            export = False if name == "Hello0" else True
            self._create(name, "0.1", expanded_deps, export=export)

        create_export(test_deps, "Hello0")

        self.client.run("info . --graph", assert_error=True)

        # arbitrary case - file will be named according to argument
        arg_filename = "test.dot"
        self.client.run("info . --graph=%s" % arg_filename)
        dot_file = os.path.join(self.client.current_folder, arg_filename)
        contents = load(dot_file)
        expected = textwrap.dedent("""
            "Hello8/0.1@lasote/stable" -> "Hello9/0.1@lasote/stable"
            "Hello8/0.1@lasote/stable" -> "Hello10/0.1@lasote/stable"
            "Hello4/0.1@lasote/stable" -> "Hello5/0.1@lasote/stable"
            "Hello4/0.1@lasote/stable" -> "Hello6/0.1@lasote/stable"
            "Hello3/0.1@lasote/stable" -> "Hello7/0.1@lasote/stable"
            "Hello7/0.1@lasote/stable" -> "Hello8/0.1@lasote/stable"
            "conanfile.py (Hello0/0.1)" -> "Hello1/0.1@lasote/stable"
            "conanfile.py (Hello0/0.1)" -> "Hello2/0.1@lasote/stable"
            "conanfile.py (Hello0/0.1)" -> "Hello3/0.1@lasote/stable"
            "Hello1/0.1@lasote/stable" -> "Hello4/0.1@lasote/stable"
            """)
        for line in expected.splitlines():
            assert line in contents

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
                License: MIT
                Description: blah
                Provides: Hello2
                Requires:
                    Hello1/0.1@lasote/stable""")

        expected_output = expected_output % (
            "\n    Revision: d6727bc577b5c6bd8ac7261eff98be93"
            "\n    Package revision: None",
            "\n    Revision: 7c5e142433a3ee0acaeffb4454a6d42f"
            "\n    Package revision: None",) \
            if self.client.cache.config.revisions_enabled else expected_output % ("", "")

        def clean_output(output):
            return "\n".join([line for line in str(output).splitlines()
                              if not line.strip().startswith("Creation date") and
                              not line.strip().startswith("ID") and
                              not line.strip().startswith("Context") and
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
                License: MIT""")

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
                License: MIT
                Description: blah""")
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
        self.assertEqual(content[0]["revision"], "33574249dee63395e86d2caee3f6c638")
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


class InfoTest2(unittest.TestCase):

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
                      " host profile (-s, -o, -e, -pr or -c)", client.out)

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

    def test_wrong_path_parameter(self):
        client = TestClient()

        client.run("info", assert_error=True)
        self.assertIn("ERROR: Exiting with code: 2", client.out)

        client.run("info not_real_path", assert_error=True)
        self.assertIn("ERROR: Conanfile not found", client.out)

        client.run("info conanfile.txt", assert_error=True)
        self.assertIn("ERROR: Conanfile not found", client.out)

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
        self.assertEqual(output['reference'], 'conanfile.py (Pkg/0.2)')
        self.assertListEqual(output['license'], ['MIT', ])
        self.assertEqual(output['author'], 'John Doe')
        self.assertListEqual(output['topics'], ['foo', 'bar', 'qux'])
        self.assertEqual(output['url'], 'https://foo.bar.baz')
        self.assertEqual(output['homepage'], 'https://foo.bar.site')
        self.assertListEqual(output['provides'], ['libjpeg', 'libjpg'])
        self.assertEqual(output['deprecated'], 'other-pkg')

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


def test_scm_info():
    # https://github.com/conan-io/conan/issues/8377
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class Pkg(ConanFile):
            scm = {"type": "git",
                   "url": "some-url/path",
                   "revision": "some commit hash"}
        """)
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("export . pkg/0.1@")

    client.run("info .")
    assert "'revision': 'some commit hash'" in client.out
    assert "'url': 'some-url/path'" in client.out

    client.run("info pkg/0.1@")
    assert "'revision': 'some commit hash'" in client.out
    assert "'url': 'some-url/path'" in client.out

    client.run("info . --json=file.json")
    file_json = client.load("file.json")
    info_json = json.loads(file_json)
    node = info_json[0]
    assert node["scm"] == {"type": "git", "url": "some-url/path", "revision": "some commit hash"}


class TestInfoContext:
    # https://github.com/conan-io/conan/issues/9121

    def test_context_info(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})

        client.run("info .")
        assert "Context: host" in client.out

        client.run("info . --json=file.json")
        info = json.loads(client.load("file.json"))
        assert info[0]["context"] == "host"

    def test_context_build(self):
        client = TestClient()
        client.save({"cmake/conanfile.py": GenConanfile(),
                     "pkg/conanfile.py": GenConanfile().with_build_requires("cmake/1.0")})

        client.run("create cmake cmake/1.0@")
        client.run("export pkg pkg/1.0@")

        client.run("info pkg/1.0@ -pr:b=default -pr:h=default --dry-build")
        assert "cmake/1.0\n"\
               "    ID: {}\n"\
               "    BuildID: None\n"\
               "    Context: build".format(NO_SETTINGS_PACKAGE_ID) in client.out

        assert "pkg/1.0\n" \
               "    ID: {}\n" \
               "    BuildID: None\n" \
               "    Context: host".format(NO_SETTINGS_PACKAGE_ID) in client.out

        client.run("info pkg/1.0@ -pr:b=default -pr:h=default --dry-build --json=file.json")
        info = json.loads(client.load("file.json"))
        assert info[0]["reference"] == "cmake/1.0"
        assert info[0]["context"] == "build"
        assert info[1]["reference"] == "pkg/1.0"
        assert info[1]["context"] == "host"


class TestInfoPythonRequires:
    # https://github.com/conan-io/conan/issues/9277

    def test_python_requires(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("export . tool/0.1@")
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                python_requires = "tool/0.1"
            """)
        client.save({"conanfile.py": conanfile})

        client.run("info .")
        assert "Python-requires:" in client.out
        assert "tool/0.1#f3367e0e7d170aa12abccb175fee5f97" in client.out

        client.run("info . --json=file.json")
        info = json.loads(client.load("file.json"))
        assert info[0]["python_requires"] == ['tool/0.1#f3367e0e7d170aa12abccb175fee5f97']

class TestInfoTestPackage:
    # https://github.com/conan-io/conan/issues/10714

    def test_tested_reference_str(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("export . tool/0.1@")

        conanfile = textwrap.dedent("""
from conans import ConanFile
class HelloConan(ConanFile):

    def requirements(self):
        self.requires(self.tested_reference_str)

    def build_requirements(self):
        self.build_requires(self.tested_reference_str)

    test_type = 'explicit'
""")
        client.save({"conanfile.py": conanfile})

        for args in ["", " --build-order tool/0.1@", " --build"]:
            client.run("info . " + args)
            assert "AttributeError: 'HelloConan' object has no attribute 'tested_reference_str'"\
                   not in client.out
