import json
import os
import textwrap

from conan.cli.exit_codes import ERROR_GENERAL
from conans.model.recipe_ref import RecipeReference
from conan.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, GenConanfile, TurboTestClient


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

    def test_nontuple_topics(self):
        client = TestClient()
        # This is the representation that should always happen,
        # we wouldn't expect topics not to be a tuple here
        conanfile = textwrap.dedent("""
                            from conan import ConanFile

                            class MyTest(ConanFile):
                                name = "pkg"
                                version = "0.2"
                                provides = ("bar",)
                                topics = ("foo",)
                            """)
        client.save({"conanfile.py": conanfile})
        client.run("graph info . --format=json")
        recipe = json.loads(client.stdout)["graph"]["nodes"]["0"]
        assert type(recipe["topics"]) == list
        assert recipe["topics"] == ["foo"]
        assert type(recipe["provides"]) == list
        assert recipe["provides"] == ["bar"]

        # But this used to fail,
        # topics were not converted to a list internally if one was not provided
        client2 = TestClient()
        conanfile2 = textwrap.dedent("""
                    from conan import ConanFile

                    class MyTest(ConanFile):
                        name = "pkg"
                        version = "0.2"
                        provides = "bar"
                        topics = "foo"
                    """)
        client2.save({"conanfile.py": conanfile2})
        client2.run("graph info . --format=json")
        recipe = json.loads(client2.stdout)["graph"]["nodes"]["0"]
        assert type(recipe["topics"]) == list
        assert recipe["topics"] == ["foo"]
        assert type(recipe["provides"]) == list
        assert recipe["provides"] == ["bar"]


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
        assert "ERROR: Please specify a path" in client.out

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

    def test_filter_fields_json(self):
        # The --filter arg should work, specifying which fields to show only
        c = TestClient()
        c.save({"conanfile.py": GenConanfile()
               .with_class_attribute("author = 'myself'")
               .with_class_attribute("license = 'MIT'")
               .with_class_attribute("url = 'http://url.com'")})
        c.run("graph info . --filter=license --format=json")
        assert "author" not in c.out
        assert '"license": "MIT"' in c.out
        c.run("graph info . --filter=license --format=html", assert_error=True)
        assert "Formatted output 'html' cannot filter fields" in c.out


class TestJsonOutput:
    def test_json_package_filter(self):
        # Formatted output like json or html doesn't make sense to be filtered
        client = TestClient()
        conanfile = GenConanfile("pkg", "0.1").with_setting("build_type")
        client.save({"conanfile.py": conanfile})
        client.run("graph info . --package-filter=nothing --format=json")
        assert '"nodes": {}' in client.out
        client.run("graph info . --package-filter=pkg* --format=json")
        graph = json.loads(client.stdout)
        assert graph["graph"]["nodes"]["0"]["ref"] == "pkg/0.1"

    def test_json_info_outputs(self):
        client = TestClient()
        conanfile = GenConanfile("pkg", "0.1").with_setting("build_type")
        client.save({"conanfile.py": conanfile})
        client.run("graph info . -s build_type=Debug --format=json")
        graph = json.loads(client.stdout)
        assert graph["graph"]["nodes"]["0"]["settings"]["build_type"] == "Debug"


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
        assert "python_requires:\n    tool/0.1#4d670581ccb765839f2239cc8dff8fbd" in client.out

        client.run("graph info . --format=json")
        info = json.loads(client.stdout)
        pyrequires = info["graph"]["nodes"]["0"]["python_requires"]
        tool = pyrequires["tool/0.1#4d670581ccb765839f2239cc8dff8fbd"]
        info = info["graph"]["nodes"]["0"]["info"]
        assert info["python_requires"] == ["tool/0.1.Z"]
        # lets make sure the path exists
        assert tool["recipe"] == "Cache"
        assert tool["remote"] is None
        assert os.path.exists(tool["path"])

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
        c.run("editable add pkg --name=pkg --version=0.1")
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

            def deploy(graph, output_folder, **kwargs):
                contents = []
                conanfile = graph.root.conanfile
                for pkg in graph.nodes:
                    d = pkg.conanfile
                    contents.append("LICENSE {}: {}!".format(d.ref, d.license))
                contents = "\n".join(contents)
                conanfile.output.info(contents)
                save(conanfile, "licenses.txt", contents)
            """)
        c.save({"conanfile.py": GenConanfile().with_requires("pkg/0.1")
                                              .with_class_attribute("license='GPL'"),
                "collectlicenses.py": collectlicenses})
        c.run("graph info . --deployer=collectlicenses")
        assert "conanfile.py: LICENSE : GPL!" in c.out
        assert "LICENSE pkg/0.1: MIT!" in c.out
        contents = c.load("licenses.txt")
        assert "LICENSE pkg/0.1: MIT!" in contents
        assert "LICENSE : GPL!" in contents


class TestErrorsInGraph:
    # https://github.com/conan-io/conan/issues/12735

    def test_error_in_recipe(self):
        c = TestClient()
        dep = textwrap.dedent("""
            from conan import ConanFile
            class Pkg(ConanFile):
                name = "dep"
                version = "0.1"
                def package_id(self):
                    a = b
            """)
        c.save({"dep/conanfile.py": dep,
                "consumer/conanfile.py": GenConanfile().with_requires("dep/0.1")})
        c.run("export dep")
        exit_code = c.run("graph info consumer", assert_error=True)
        assert "name 'b' is not defined" in c.out
        assert exit_code == ERROR_GENERAL

    def test_error_exports(self):
        c = TestClient()
        dep = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.files import replace_in_file
            class Pkg(ConanFile):
                name = "dep"
                version = "0.1"
                def export(self):
                    replace_in_file(self, "conanfile.py", "from conan", "from conans")
            """)
        c.save({"dep/conanfile.py": dep,
                "consumer/conanfile.py": GenConanfile().with_requires("dep/0.1")})
        c.run("export dep")
        exit_code = c.run("graph info consumer", assert_error=True)
        assert "ERROR: Package 'dep/0.1' not resolved: dep/0.1: Cannot load" in c.out
        assert exit_code == ERROR_GENERAL


class TestInfoUpdate:

    def test_update(self):
        c = TestClient(default_server_user=True)
        c.save({"conanfile.py": GenConanfile("tool")})
        c.run("create . --version=1.0")
        c.run("create . --version=1.1")
        c.run("upload tool/1.1 -r=default -c")
        c.run("remove tool/1.1 -c")
        c.save({"conanfile.py": GenConanfile().with_requires("tool/[*]")})
        c.run("graph info . --filter=recipe")
        assert "tool/1.0#7fbd52996f34447f4a4c362edb5b4af5 - Cache" in c.out
        c.run("graph info . --update --filter=recipe")
        assert "tool/1.1#7fbd52996f34447f4a4c362edb5b4af5 - Downloaded (default)" in c.out


def test_info_not_hit_server():
    """
    the command graph info shouldn't be hitting the server if packages are in the Conan cache
    :return:
    """
    c = TestClient(default_server_user=True)
    c.save({"pkg/conanfile.py": GenConanfile("pkg", "0.1"),
            "consumer/conanfile.py": GenConanfile("consumer", "0.1").with_require("pkg/0.1")})
    c.run("create pkg")
    c.run("create consumer")
    c.run("upload * -r=default -c")
    c.run("remove * -c")
    c.run("install --requires=consumer/0.1@")
    assert "Downloaded" in c.out
    # break the server to make sure it is not being contacted at all
    c.servers["default"] = None
    c.run("graph info --requires=consumer/0.1@")
    assert "Downloaded" not in c.out
    # Now we remove the local, so it will raise errors
    c.run("remove pkg* -c")
    c.run("graph info --requires=consumer/0.1@", assert_error=True)
    assert "'NoneType' object " in c.out
    c.run("remote disable *")
    c.run("graph info --requires=consumer/0.1@", assert_error=True)
    assert "'NoneType' object " not in c.out
    assert "No remote defined" in c.out


def test_graph_info_user():
    """
    https://github.com/conan-io/conan/issues/15791
    """
    c = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "pkg"
            version = "0.1"
            user = "user"
        """)

    c.save({"conanfile.py": conanfile})
    c.run("graph info .")
    assert "pkg/0.1@user" in c.out
    c.run("graph info . --channel=channel")
    assert "pkg/0.1@user/channel" in c.out


def test_graph_info_bundle():
    c = TestClient(light=True)
    c.save({"subfolder/conanfile.py": GenConanfile("liba", "1.0")})
    c.run("create ./subfolder")
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class RepackageRecipe(ConanFile):
            name = "lib"
            version = "1.0"
            def requirements(self):
                self.requires("liba/1.0")
            vendor = True
        """)
    c.save({"conanfile.py": conanfile})
    c.run("create .")
    c.save({"conanfile.py": GenConanfile("consumer", "1.0").with_requires("lib/1.0")})

    c.run("graph info . --build='lib*'")
    c.assert_listed_binary({"lib/1.0": (NO_SETTINGS_PACKAGE_ID, "Invalid")})

    c.run("graph info . -c tools.graph:vendor=build --build='lib*'")
    c.assert_listed_binary({"lib/1.0": (NO_SETTINGS_PACKAGE_ID, "Build")})
