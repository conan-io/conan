import json
import os
import textwrap
import unittest
from datetime import datetime

import pytest

from conans import __version__ as client_version
from conans.test.utils.tools import TestClient, GenConanfile, NO_SETTINGS_PACKAGE_ID
from conans.util.files import save, load


class InfoTest(unittest.TestCase):

    def _create(self, name, version, deps=None, export=True):
        conanfile = textwrap.dedent("""
            from conans import ConanFile
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
            self.client.run("export . lasote/stable")

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

        self.client.run("info . --graph", assert_error=True)

        # arbitrary case - file will be named according to argument
        arg_filename = "test.dot"
        self.client.run("info . --graph=%s" % arg_filename)
        dot_file = os.path.join(self.client.current_folder, arg_filename)
        contents = load(dot_file)
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
        arg_filename = "test.html"
        self.client.run("info . --graph=%s" % arg_filename)
        html = self.client.load(arg_filename)
        self.assertIn("<body>", html)
        self.assertIn("{ from: 0, to: 1 }", html)
        self.assertIn("id: 0,\n                        label: 'hello0/0.1',", html)
        self.assertIn("Conan <b>v{}</b> <script>document.write(new Date().getFullYear())</script>"
                      " JFrog LTD. <a>https://conan.io</a>"
                      .format(client_version, datetime.today().year), html)

    @pytest.mark.xfail(reason="Info command output changed")
    def test_only_names(self):
        self.client = TestClient()
        self._create("hello0", "0.1")
        self._create("hello1", "0.1", ["hello0/0.1@lasote/stable"])
        self._create("hello2", "0.1", ["hello1/0.1@lasote/stable"], export=False)

        self.client.run("info . --only None")
        self.assertEqual(["hello0/0.1@lasote/stable", "hello1/0.1@lasote/stable",
                          "conanfile.py (hello2/0.1)"],
                         str(self.client.out).splitlines()[-3:])
        self.client.run("info . --only=date")
        lines = [(line if "date" not in line else "Date")
                 for line in str(self.client.out).splitlines()]
        self.assertEqual(["hello0/0.1@lasote/stable", "Date",
                          "hello1/0.1@lasote/stable", "Date",
                          "conanfile.py (hello2/0.1)"], lines)

        self.client.run("info . --only=invalid", assert_error=True)
        self.assertIn("Invalid --only value", self.client.out)
        self.assertNotIn("with --path specified, allowed values:", self.client.out)

        self.client.run("info . --paths --only=bad", assert_error=True)
        self.assertIn("Invalid --only value", self.client.out)
        self.assertIn("with --path specified, allowed values:", self.client.out)

    @pytest.mark.xfail(reason="Info command output changed")
    def test_info_virtual(self):
        # Checking that "Required by: virtual" doesnt appear in the output
        self.client = TestClient()
        self._create("hello", "0.1")
        self.client.run("info hello/0.1@lasote/stable")
        self.assertNotIn("virtual", self.client.out)
        self.assertNotIn("Required", self.client.out)

    @pytest.mark.xfail(reason="cache2.0 revisit")
    def test_reuse(self):
        self.client = TestClient()
        self._create("hello0", "0.1")
        self._create("hello1", "0.1", ["hello0/0.1@lasote/stable"])
        self._create("hello2", "0.1", ["hello1/0.1@lasote/stable"], export=False)

        self.client.run("info . -u")

        self.assertIn("Creation date: ", self.client.out)
        self.assertIn("ID: ", self.client.out)
        self.assertIn("BuildID: ", self.client.out)

        expected_output = textwrap.dedent("""\
            hello0/0.1@lasote/stable
                Remote: None
                URL: myurl
                License: MIT
                Description: blah
                Provides: hello0
                Recipe: No remote%s
                Binary: Missing
                Binary remote: None
                Required by:
                    hello1/0.1@lasote/stable
            hello1/0.1@lasote/stable
                Remote: None
                URL: myurl
                License: MIT
                Description: blah
                Provides: hello1
                Recipe: No remote%s
                Binary: Missing
                Binary remote: None
                Required by:
                    conanfile.py (hello2/0.1)
                Requires:
                    hello0/0.1@lasote/stable
            conanfile.py (hello2/0.1)
                URL: myurl
                License: MIT
                Description: blah
                Provides: hello2
                Requires:
                    hello1/0.1@lasote/stable""")

        expected_output = expected_output % (
            "\n    Revision: d6727bc577b5c6bd8ac7261eff98be93"
            "\n    Package revision: None",
            "\n    Revision: 7c5e142433a3ee0acaeffb4454a6d42f"
            "\n    Package revision: None",)

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
            hello0/0.1@lasote/stable
                URL: myurl
            hello1/0.1@lasote/stable
                URL: myurl
            conanfile.py (hello2/0.1)
                URL: myurl""")

        self.assertIn(expected_output, clean_output(self.client.out))
        self.client.run("info . -u --only=url --only=license")
        expected_output = textwrap.dedent("""\
            hello0/0.1@lasote/stable
                URL: myurl
                License: MIT
            hello1/0.1@lasote/stable
                URL: myurl
                License: MIT
            conanfile.py (hello2/0.1)
                URL: myurl
                License: MIT""")

        self.assertIn(expected_output, clean_output(self.client.out))

        self.client.run("info . -u --only=url --only=license --only=description")
        expected_output = textwrap.dedent("""\
            hello0/0.1@lasote/stable
                URL: myurl
                License: MIT
                Description: blah
            hello1/0.1@lasote/stable
                URL: myurl
                License: MIT
                Description: blah
            conanfile.py (hello2/0.1)
                URL: myurl
                License: MIT
                Description: blah""")
        self.assertIn(expected_output, clean_output(self.client.out))

    def test_json_info_outputs(self):
        self.client = TestClient()
        self._create("liba", "0.1")
        self._create("libe", "0.1")
        self._create("libf", "0.1")

        self._create("libb", "0.1", ["liba/0.1@lasote/stable", "libe/0.1@lasote/stable"])
        self._create("libc", "0.1", ["liba/0.1@lasote/stable", "libf/0.1@lasote/stable"])

        self._create("libd", "0.1", ["libb/0.1@lasote/stable", "libc/0.1@lasote/stable"],
                     export=False)

        self.client.run("info . -u --json=output.json")

        # Check a couple of values in the generated JSON
        content = json.loads(self.client.load("output.json"))
        self.assertEqual(content[0]["reference"], "liba/0.1@lasote/stable")
        self.assertEqual(content[0]["license"][0], "MIT")
        self.assertEqual(content[0]["description"], "blah")
        self.assertEqual(content[0]["revision"], "6a53a80661c5369e15f23d918f5d2e95")
        self.assertEqual(content[0]["package_revision"], None)
        self.assertEqual(content[1]["url"], "myurl")
        self.assertEqual(content[1]["required_by"][0], "conanfile.py (libd/0.1)")


class InfoTest2(unittest.TestCase):

    @pytest.mark.xfail(reason="cache2.0 revisit")
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

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_failed_info(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_require("pkg/1.0.x@user/testing")})
        client.run("info .", assert_error=True)
        self.assertIn("pkg/1.0.x@user/testing: Not found in local cache", client.out)
        client.run("search")
        self.assertIn("There are no packages", client.out)
        self.assertNotIn("pkg/1.0.x@user/testing", client.out)

    def test_info_settings(self):
        conanfile = GenConanfile("pkg", "0.1").with_setting("build_type")
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("info . -s build_type=Debug")
        self.assertNotIn("ID: 4024617540c4f240a6a5e8911b0de9ef38a11a72", client.out)
        self.assertIn("ID: 040ce2bd0189e377b2d15eb7246a4274d1c63317", client.out)

        client.run("info . -s build_type=Release")
        self.assertIn("ID: e53d55fd33066c49eb97a4ede6cb50cd8036fe8b", client.out)
        self.assertNotIn("ID: 5a67a79dbc25fd0fa149a0eb7a20715189a0d988", client.out)

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
        client.run("export . pkg/0.1@user/channel")
        client.run("export . pkg2/0.1@user/channel")
        client.save({"conanfile.txt": "[requires]\npkg/0.1@user/channel\npkg2/0.1@user/channel",
                     "myprofile": "[build_tool_requires]\ntool/0.1@user/channel"}, clean_first=True)
        client.run("info . -pr=myprofile --build=missing")
        # Check that there is only 1 output for tool, not repeated many times
        pkgs = [line for line in str(client.out).splitlines() if line.startswith("tool")]
        self.assertEqual(len(pkgs), 1)

        client.run("info . -pr=myprofile --build=missing --graph=file.html")
        html = client.load("file.html")
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

    def test_cwd(self):
        client = TestClient()
        conanfile = GenConanfile("pkg", "0.1").with_setting("build_type")
        client.save({"subfolder/conanfile.py": conanfile})
        client.run("export ./subfolder lasote/testing")

        client.run("info ./subfolder")
        self.assertIn("conanfile.py (pkg/0.1)", client.out)

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

        conanfile = GenConanfile("pkg", "0.1").with_setting("build_type")
        client.save({"subfolder/conanfile.py": conanfile})
        client.run("export ./subfolder lasote/testing")

        client.run("info ./subfolder")

        self.assertIn("conanfile.py (pkg/0.1)", client.out)
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
                name = "pkg"
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

        self.assertIn("conanfile.py (pkg/0.2)", client.out)
        self.assertIn("License: MIT", client.out)
        self.assertIn("Author: John Doe", client.out)
        self.assertIn("Topics: foo, bar, qux", client.out)
        self.assertIn("URL: https://foo.bar.baz", client.out)
        self.assertIn("Homepage: https://foo.bar.site", client.out)
        self.assertIn("Provides: libjpeg, libjpg", client.out)
        self.assertIn("Deprecated: other-pkg", client.out)

        client.run("info ./subfolder --json=output.json")
        output = json.loads(client.load('output.json'))[0]
        self.assertEqual(output['reference'], 'conanfile.py (pkg/0.2)')
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
                name = "pkg"
                version = "0.2"
                topics = ("foo", "bar", "qux")
        """)

        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("export . lasote/testing")

        # Topics as tuple
        client.run("info pkg/0.2@lasote/testing --graph file.html")
        html_content = client.load("file.html")
        self.assertIn("<h3>pkg/0.2@lasote/testing</h3>", html_content)
        self.assertIn("<li><b>topics</b>: foo, bar, qux</li>", html_content)

        # Topics as a string
        conanfile = conanfile.replace("(\"foo\", \"bar\", \"qux\")", "\"foo\"")
        client.save({"conanfile.py": conanfile}, clean_first=True)
        client.run("export . lasote/testing")
        client.run("info pkg/0.2@lasote/testing --graph file.html")
        html_content = client.load("file.html")
        self.assertIn("<h3>pkg/0.2@lasote/testing</h3>", html_content)
        self.assertIn("<li><b>topics</b>: foo", html_content)

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
        class pkg(ConanFile):
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
                     "pkg/conanfile.py": GenConanfile().with_build_tool_requires("cmake/1.0")})

        client.run("create cmake cmake/1.0@")
        client.run("export pkg pkg/1.0@")

        client.run("info pkg/1.0@ -pr:b=default -pr:h=default --build")
        assert "cmake/1.0\n"\
               "    ID: {}\n"\
               "    BuildID: None\n"\
               "    Context: build".format(NO_SETTINGS_PACKAGE_ID) in client.out

        assert "pkg/1.0\n" \
               "    ID: {}\n" \
               "    BuildID: None\n" \
               "    Context: host".format(NO_SETTINGS_PACKAGE_ID) in client.out

        client.run("info pkg/1.0@ -pr:b=default -pr:h=default --build --json=file.json")
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
            class pkg(ConanFile):
                python_requires = "tool/0.1"
            """)
        client.save({"conanfile.py": conanfile})

        client.run("info .")
        assert "Python-requires:" in client.out
        assert "tool/0.1#f3367e0e7d170aa12abccb175fee5f97" in client.out

        client.run("info . --json=file.json")
        info = json.loads(client.load("file.json"))
        assert info[0]["python_requires"] == ['tool/0.1#f3367e0e7d170aa12abccb175fee5f97']
