import json
import textwrap

from conans.test.utils.tools import TestClient, GenConanfile


class TestBasicCliOutput:

    def test_info_settings(self):
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
                topics = "foo", "bar", "qux"
                provides = "libjpeg", "libjpg"
                deprecated = "other-pkg"
            """)
        client.save({"conanfile.py": conanfile})
        client.run("graph info . -s build_type=Debug")
        assert "build_type: Debug" in client.out
        assert "context: host"
        assert "license: MIT"
        assert "homepage: https://foo.bar.site"


class TestConanfilePath:
    def test_cwd(self):
        # Check the first positional argument is a relative path
        client = TestClient()
        conanfile = GenConanfile("pkg", "0.1").with_setting("build_type")
        client.save({"subfolder/conanfile.py": conanfile})
        client.run("graph info ./subfolder -s build_type=Debug")
        assert "build_type: Debug" in client.out

    def test_wrong_path_parameter(self):
        # check that the positional parameter must exist and file must be found
        client = TestClient()

        client.run("graph info", assert_error=True)
        assert "ERROR: Please specify at least a path" in client.out

        client.run("graph info not_real_path", assert_error=True)
        assert "ERROR: Conanfile not found" in client.out

        client.run("graph info conanfile.txt", assert_error=True)
        assert "ERROR: Conanfile not found" in client.out


class TestFilters:

    def test_filter_fields(self):
        # The --filter arg should work, specifying which fields to show only
        c = TestClient()
        c.save({"conanfile.py": GenConanfile()
               .with_class_attribute("author = 'myself'")
               .with_class_attribute("license = 'MIT'")
               .with_class_attribute("url = 'http://url.com'")})
        c.run("graph info . ")
        assert "license: MIT" in c.out
        assert "author: myself" in c.out
        c.run("graph info . --filter=license")
        assert "license: MIT" in c.out
        assert "author" not in c.out
        c.run("graph info . --filter=author")
        assert "license" not in c.out
        assert "author: myself" in c.out
        c.run("graph info . --filter=author --filter=license")
        assert "license" in c.out
        assert "author: myself" in c.out


class TestJsonOutput:
    def test_json_not_filtered(self):
        # Formatted output like json or html doesn't make sense to be filtered
        client = TestClient()
        conanfile = GenConanfile("pkg", "0.1").with_setting("build_type")
        client.save({"conanfile.py": conanfile})
        client.run("graph info . --filter=license --format=graph.json", assert_error=True)
        assert "Formatted outputs cannot be filtered" in client.out
        client.run("graph info . --package-filter=license --format=graph.html", assert_error=True)
        assert "Formatted outputs cannot be filtered" in client.out

    def test_json_info_outputs(self):
        client = TestClient()
        conanfile = GenConanfile("pkg", "0.1").with_setting("build_type")
        client.save({"conanfile.py": conanfile})
        client.run("graph info . -s build_type=Debug --format=graph.json")
        graph = json.loads(client.load("graph.json"))
        assert graph["nodes"][0]["settings"]["build_type"] == "Debug"


class TestAdvancedCliOutput:
    """ Testing more advanced fields output, like SCM or PYTHON-REQUIRES
    """
    def test_scm_info(self):
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

        client.run("graph info .")
        assert "revision: some commit hash" in client.out
        assert "url: some-url/path" in client.out

        client.run("export . --name=pkg --version=0.1")
        client.run("graph info --reference=pkg/0.1@")
        assert "revision: some commit hash" in client.out
        assert "url: some-url/path" in client.out

        client.run("graph info . --format=file.json")
        file_json = client.load("file.json")
        info_json = json.loads(file_json)
        assert info_json["nodes"][0]["scm"]["type"] == "git"

    def test_python_requires(self):
        # https://github.com/conan-io/conan/issues/9277
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("export . --name=tool --version=0.1")
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class pkg(ConanFile):
                python_requires = "tool/0.1"
            """)
        client.save({"conanfile.py": conanfile})

        client.run("graph info .")
        assert "python_requires: ['tool/0.1#f3367e0e7d170aa12abccb175fee5f97']" in client.out

        client.run("graph info . --format=file.json")
        info = json.loads(client.load("file.json"))
        assert info["nodes"][0]["python_requires"] == ['tool/0.1#f3367e0e7d170aa12abccb175fee5f97']
