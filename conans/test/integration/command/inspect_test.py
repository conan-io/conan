import json
import os
import textwrap
import unittest

from conans.test.utils.tools import TestClient, TestServer, GenConanfile


class ConanInspectTest(unittest.TestCase):

    def test_inspect_quiet(self):
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": GenConanfile().with_name("name")})
        client.run("export . --name=name --version=version --user=user --channel=channel")
        client.run("upload name/version@user/channel -r default")
        client.run("remove * -f")

        # If the recipe exists, it doesn't show extra output
        client.run("inspect name/version@user/channel --raw name")
        self.assertEqual(client.out, "name")

        # If the recipe doesn't exist, the output is shown
        client.run("inspect non-existing/version@user/channel --raw name", assert_error=True)
        self.assertIn("ERROR: Unable to find 'non-existing/version@user/channel' in remotes",
                      client.out)

    def test_inspect_remote(self):
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": GenConanfile("pkg", "0.1").with_settings("os")})
        client.run("export . --user=user --channel=channel")
        client.run("upload pkg/0.1@user/channel -r default --only-recipe")
        client.save({"conanfile.py": GenConanfile("pkg", "0.1").with_settings("os", "arch")})
        client.run("export . --user=user --channel=channel")

        client.run("inspect pkg/0.1@user/channel -a settings")
        self.assertIn("settings: ('os', 'arch')", client.out)
        client.run("inspect pkg/0.1@user/channel -r=default -a settings")
        self.assertIn("settings: ['os']", client.out)
        client.run("inspect pkg/0.1@user/channel -a settings")
        # we got in cache the revision from the remote but still the latest
        # revision in cache is the last we created
        self.assertIn("settings: ('os', 'arch')", client.out)
        client.run("remove * -f")
        client.run("inspect pkg/0.1@user/channel -a settings")
        self.assertIn("settings: ['os']", client.out)

    def test_inspect_not_in_remote(self):
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": GenConanfile("pkg", "0.1").with_settings("os")})
        client.run("export . --user=user --channel=channel")

        client.run("inspect pkg/0.1@user/channel -a settings")
        self.assertIn("settings: ['os']", client.out)

        client.run("inspect pkg/0.1@user/channel -a settings -r default", assert_error=True)
        self.assertIn("ERROR: Recipe not found: 'pkg/0.1@user/channel'", client.out)

        client.run("inspect pkg/0.1@user/channel -a settings")
        self.assertIn("settings: ['os']", client.out)

    def test_name_version(self):
        server = TestServer()
        client = TestClient(servers={"default": server}, inputs=["admin", "password"])
        client.save({"conanfile.py": GenConanfile().with_name("mypkg").with_version("1.2.3")})
        client.run("inspect . -a=name")
        self.assertIn("name: mypkg", client.out)
        client.run("inspect . -a=version")
        self.assertIn("version: 1.2.3", client.out)
        client.run("inspect . -a=version -a=name")
        self.assertIn("name: mypkg", client.out)
        self.assertIn("version: 1.2.3", client.out)
        client.run("inspect . -a=version -a=name --json=file.json")
        contents = client.load("file.json")
        self.assertIn('"version": "1.2.3"', contents)
        self.assertIn('"name": "mypkg"', contents)

        client.run("export . --user=lasote --channel=testing")
        client.run("inspect mypkg/1.2.3@lasote/testing -a=name")
        self.assertIn("name: mypkg", client.out)
        client.run("inspect mypkg/1.2.3@lasote/testing -a=version")
        self.assertIn("version: 1.2.3", client.out)

        client.run("upload mypkg* --confirm -r default --only-recipe")
        client.run('remove "*" -f')
        client.run("inspect mypkg/1.2.3@lasote/testing -a=name -r=default")
        self.assertIn("name: mypkg", client.out)
        client.run("inspect mypkg/1.2.3@lasote/testing -a=version -r=default")
        self.assertIn("version: 1.2.3", client.out)

    def test_set_name_version(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile, load
            import os
            class Pkg(ConanFile):
                def set_name(self):
                    self.name = "mypkg"
                def set_version(self):
                    self.version = load(os.path.join(self.recipe_folder, "version.txt"))
            """)
        client.save({"conanfile.py": conanfile,
                     "version.txt": "1.2.3"})
        client.run("inspect . -a=name")
        self.assertIn("name: mypkg", client.out)
        client.run("inspect . -a=version")
        self.assertIn("version: 1.2.3", client.out)

        client.run("export .")
        client.save({}, clean_first=True)
        client.run("inspect mypkg/1.2.3@ -a=name")
        self.assertIn("name: mypkg", client.out)
        client.run("inspect mypkg/1.2.3@ -a=version")
        self.assertIn("version: 1.2.3", client.out)

    def test_attributes_display(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    settings = "os", "compiler", "arch"
    pass
"""
        client.save({"conanfile.py": conanfile})
        client.run("inspect . -a=short_paths")
        self.assertIn("short_paths: False", client.out)
        client.run("inspect . -a=name")
        self.assertIn("name: None", client.out)
        client.run("inspect . -a=version")
        self.assertIn("version: None", client.out)
        client.run("inspect . -a=settings")
        self.assertIn("settings: ('os', 'compiler', 'arch')", client.out)
        client.run("inspect . -a=revision_mode")
        self.assertIn("revision_mode: hash", client.out)

        client.run("inspect . -a=unexisting_attr")
        self.assertIn("unexisting_attr:", client.out)

    def test_inspect_all(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    name = "mypkg"
    version = "1.2.3"
    _private = "Nothing"
    def build(self):
        pass
"""
        client.save({"conanfile.py": conanfile})
        client.run("inspect .")
        self.assertEqual("""name: mypkg
version: 1.2.3
url: None
homepage: None
license: None
author: None
description: None
topics: None
generators: []
exports: None
exports_sources: None
short_paths: False
build_policy: None
revision_mode: hash
settings: None
options:
default_options: None
deprecated: None
""", client.out)

    def test_inspect_filled_attributes(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    name = "mypkg"
    version = "1.2.3"
    author = "John Doe"
    url = "https://john.doe.com"
    homepage = "https://john.company.site"
    license = "MIT"
    description = "Yet Another Test"
    generators = "cmake"
    topics = ("foo", "bar", "qux")
    settings = "os", "arch", "build_type", "compiler"
    options = {"foo": [True, False], "bar": [True, False]}
    default_options = {"foo": True, "bar": False}
    _private = "Nothing"
    revision_mode = "scm"
    deprecated = "suggestion"
    def build(self):
        pass
"""
        client.save({"conanfile.py": conanfile})
        client.run("inspect .")
        self.assertEqual("""name: mypkg
version: 1.2.3
url: https://john.doe.com
homepage: https://john.company.site
license: MIT
author: John Doe
description: Yet Another Test
topics: ('foo', 'bar', 'qux')
generators: ['cmake']
exports: None
exports_sources: None
short_paths: False
build_policy: None
revision_mode: scm
settings: ('os', 'arch', 'build_type', 'compiler')
options:
    bar: ['True', 'False']
    foo: ['True', 'False']
default_options:
    bar: False
    foo: True
deprecated: suggestion
""", client.out)


class InspectRawTest(unittest.TestCase):
    conanfile = textwrap.dedent("""
        from conans import ConanFile

        class Pkg(ConanFile):
            name = "mypkg"
            version = "1.2.3"
            author = "John Doe"
            url = "https://john.doe.com"
            settings = "os", "arch", "build_type", "compiler"
            options = {"foo": [True, False], "bar": [True, False]}
            default_options = {"foo": "True", "bar": "True"}

            _private = "Nothing"

            def build(self):
                pass
        """)

    def test_no_field_or_multiple(self):
        client = TestClient()
        client.save({"conanfile.py": self.conanfile})
        client.run("inspect . --raw", assert_error=True)
        client.run("inspect . --raw=name --raw=version", assert_error=True)

    def test_incompatible_commands(self):
        client = TestClient()
        client.save({"conanfile.py": self.conanfile})

        client.run("inspect . --raw=name -a=version", assert_error=True)
        self.assertIn("ERROR: Argument '--raw' is incompatible with '-a'", client.out)

        client.run("inspect . --raw=name --json=tmp.json", assert_error=True)
        self.assertIn("ERROR: Argument '--raw' is incompatible with '--json'", client.out)

    def test_invalid_field(self):
        client = TestClient()
        client.save({"conanfile.py": self.conanfile})
        client.run("inspect . --raw=not_exists")
        self.assertEqual("", client.out)

    def test_private_field(self):
        client = TestClient()
        client.save({"conanfile.py": self.conanfile})
        client.run("inspect . --raw=_private")
        self.assertEqual("Nothing", client.out)

    def test_settings(self):
        client = TestClient()
        client.save({"conanfile.py": self.conanfile})
        client.run("inspect . --raw=settings")
        self.assertEqual("('os', 'arch', 'build_type', 'compiler')", client.out)

    def test_options_dict(self):
        client = TestClient()
        client.save({"conanfile.py": self.conanfile})
        client.run("inspect . --raw=options")
        # The output is a dictionary, no order guaranteed, we need to compare as dict
        import ast
        output = ast.literal_eval(str(client.out))
        self.assertDictEqual(output, {'bar': ['True', 'False'], 'foo': ['True', 'False']})

    def test_default_options_list(self):
        client = TestClient()
        client.save({"conanfile.py": self.conanfile})
        client.run("inspect . --raw=default_options")
        self.assertEqual("{'foo': 'True', 'bar': 'True'}", client.out)

    def test_default_options_dict(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Lib(ConanFile):
                options = {"dict": [True, False], "list": [True, False]}
                default_options = {"dict": True, "list": False}
            """)
        client.save({"conanfile.py": conanfile})
        client.run("inspect . --raw=default_options")
        self.assertEqual("{'dict': True, 'list': False}", client.out)

    def test_initial_inspect_without_registry(self):
        client = TestClient()
        client.save({"conanfile.py": self.conanfile})
        client.run("export . --user=user --channel=channel")
        os.remove(client.cache.remotes_path)
        client.run("inspect mypkg/1.2.3@user/channel --raw=version")
        self.assertEqual("1.2.3", client.out)

    def test_inspect_settings_set(self):
        client = TestClient()
        client.save({"conanfile.py": textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                settings = {"os", "compiler"}
        """)})
        client.run("inspect . --json=file.json")
        contents = client.load("file.json")
        self.assertIn('"settings": ["compiler", "os"]', contents)

    def test_inspect_alias(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("export . --name=pkg --version=0.1")
        client.alias("pkg/latest@",  "pkg/0.1")
        client.run("inspect pkg/latest@ -a alias")
        assert "alias: pkg/0.1" in client.out

        client.run("inspect pkg/latest@ -a alias --json=myinspect")
        myinspect = json.loads(client.load("myinspect"))
        assert myinspect["alias"] == "pkg/0.1"
