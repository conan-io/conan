import json
import textwrap

from conans.model.recipe_ref import RecipeReference
from conans.test.utils.tools import TestClient, GenConanfile, TurboTestClient


class TestBasicCliOutput:

    def test_info_settings(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class MyTest(ConanFile):
                name = "pkg"
                version = "0.2"
                settings = "build_type", "compiler"
                author = "John Doe"
                license = "MIT"
                url = "https://foo.bar.baz"
                homepage = "https://foo.bar.site"
                topics = "foo", "bar", "qux"
                provides = "libjpeg", "libjpg"
                deprecated = "other-pkg"
                options = {"shared": [True, False], "fPIC": [True, False]}
                default_options = {"shared": False, "fPIC": True}
            """)
        client.save({"conanfile.py": conanfile})
        client.run("graph info . -s build_type=Debug -s compiler=gcc -s compiler.version=11")
        assert "build_type: Debug" in client.out
        assert "context: host" in client.out
        assert "license: MIT" in client.out
        assert "homepage: https://foo.bar.site" in client.out
        assert "compiler: gcc" in client.out
        assert "compiler.version: 11" in client.out
        assert "prev: None" in client.out
        assert "fPIC: True" in client.out
        assert "shared: False" in client.out
        # Create the package
        client.run("create .")
        pref = client.get_latest_package_reference("pkg/0.2")
        client.run("graph info .")
        # It's a consumer so we can not get the prev because it's not even a package yet
        assert "prev: None" in client.out
        # Now, let's create another consumer requiring the previous package
        client.save({"conanfile.txt": "[requires]\npkg/0.2"}, clean_first=True)
        client.run("graph info .")
        assert textwrap.dedent(f"""
            {repr(pref.ref)}:
              ref: {repr(pref.ref)}
              id: 1
              recipe: Cache
              package_id: {pref.package_id}
              prev: {pref.revision}""") in client.out


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
        client.run("graph info . --filter=license --format=json", assert_error=True)
        assert "Formatted outputs cannot be filtered" in client.out
        client.run("graph info . --package-filter=license --format=html", assert_error=True)
        assert "Formatted outputs cannot be filtered" in client.out

    def test_json_info_outputs(self):
        client = TestClient()
        conanfile = GenConanfile("pkg", "0.1").with_setting("build_type")
        client.save({"conanfile.py": conanfile})
        client.run("graph info . -s build_type=Debug --format=json")
        graph = json.loads(client.stdout)
        assert graph["nodes"][0]["settings"]["build_type"] == "Debug"


class TestAdvancedCliOutput:
    """ Testing more advanced fields output, like SCM or PYTHON-REQUIRES
    """

    def test_python_requires(self):
        # https://github.com/conan-io/conan/issues/9277
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("export . --name=tool --version=0.1")
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class pkg(ConanFile):
                python_requires = "tool/0.1"
            """)
        client.save({"conanfile.py": conanfile})

        client.run("graph info .")
        assert "python_requires: ['tool/0.1#4d670581ccb765839f2239cc8dff8fbd']" in client.out

        client.run("graph info . --format=json")
        info = json.loads(client.stdout)
        assert info["nodes"][0]["python_requires"] == ['tool/0.1#4d670581ccb765839f2239cc8dff8fbd']

    def test_build_id_info(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Pkg(ConanFile):
                name = "pkg"
                version = "0.1"
                settings = "build_type"

                def build_id(self):
                    self.info_build.settings.build_type = "Any"
            """)
        client.save({"conanfile.py": conanfile})
        client.run("export .")
        client.save({"conanfile.py": GenConanfile().with_requires("pkg/0.1")}, clean_first=True)
        client.run("graph info . -s build_type=Release")
        assert "build_id: ec0cd314abe055f7de86cd6493e31977d2b87884" in client.out
        assert "package_id: efa83b160a55b033c4ea706ddb980cd708e3ba1b" in client.out

        client.run("graph info . -s build_type=Debug")
        assert "build_id: ec0cd314abe055f7de86cd6493e31977d2b87884" in client.out
        assert "package_id: 9e186f6d94c008b544af1569d1a6368d8339efc5" in client.out


class TestEditables:
    def test_info_paths(self):
        # https://github.com/conan-io/conan/issues/7054
        c = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                def layout(self):
                    self.folders.source = "."
                    self.folders.build = "."
            """)
        c.save({"pkg/conanfile.py": conanfile,
                "consumer/conanfile.py": GenConanfile().with_require("pkg/0.1")})
        c.run("editable add pkg pkg/0.1@")
        # TODO: Check this --package-filter with *
        c.run("graph info consumer --package-filter=pkg*")
        # FIXME: Paths are not diplayed yet
        assert "source_folder: None" in c.out


class TestInfoRevisions:

    def test_info_command_showing_revision(self):
        """If I run 'conan info ref' I get information about the revision only in a v2 client"""
        client = TurboTestClient()
        ref = RecipeReference.loads("lib/1.0@conan/testing")

        client.create(ref)
        client.run("graph info --requires={}".format(ref))
        revision = client.recipe_revision(ref)
        assert f"ref: lib/1.0@conan/testing#{revision}" in client.out


class TestInfoTestPackage:
    # https://github.com/conan-io/conan/issues/10714

    def test_tested_reference_str(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("tool", "0.1")})
        client.run("export .")

        conanfile = textwrap.dedent("""
            from conan import ConanFile
            class HelloConan(ConanFile):

                def requirements(self):
                    self.requires(self.tested_reference_str)

                def build_requirements(self):
                    self.build_requires(self.tested_reference_str)
            """)
        client.save({"conanfile.py": conanfile})

        for args in ["", " --build=*"]:
            client.run("graph info . " + args)
            assert "AttributeError: 'HelloConan' object has no attribute 'tested_reference_str'"\
                   not in client.out


class TestDeployers:

    def test_custom_deploy(self):
        c = TestClient()
        conanfile = GenConanfile("pkg", "0.1").with_class_attribute("license = 'MIT'")
        c.save({"conanfile.py": conanfile})
        c.run("create .")
        collectlicenses = textwrap.dedent(r"""
            from conan.tools.files import save

            def deploy(conanfile, output_folder, **kwargs):
                contents = []
                for r, d in conanfile.dependencies.items():
                    contents.append("LICENSE {}: {}!".format(d.ref, d.license))
                contents = "\n".join(contents)
                conanfile.output.info(contents)
                save(conanfile, "licenses.txt", contents)
            """)
        c.save({"conanfile.py": GenConanfile().with_requires("pkg/0.1"),
                "collectlicenses.py": collectlicenses})
        c.run("graph info . --deploy=collectlicenses")
        assert "conanfile.py: LICENSE pkg/0.1: MIT!" in c.out
        contents = c.load("licenses.txt")
        assert "LICENSE pkg/0.1: MIT!" in contents
