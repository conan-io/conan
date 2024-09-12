import json
import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_basic_inspect():
    t = TestClient()
    t.save({"foo/conanfile.py": GenConanfile().with_name("foo").with_shared_option()})
    t.run("inspect foo/conanfile.py")
    lines = t.out.splitlines()
    assert lines == ['default_options:',
                     '    shared: False',
                     'generators: []',
                     'label: ',
                     'languages: []',
                     'name: foo',
                     'options:',
                     '    shared: False',
                     'options_definitions:',
                     "    shared: ['True', 'False']",
                     'package_type: None',
                     'requires: []',
                     'revision_mode: hash',
                     'vendor: False'
                     ]


def test_options_description():
    t = TestClient()
    conanfile = textwrap.dedent("""\
        from conan import ConanFile
        class Pkg(ConanFile):
            options = {"shared": [True, False, None], "fpic": [True, False, None]}
            options_description = {"shared": "Some long explanation about shared option",
                                   "fpic": "Yet another long explanation of fpic"}
            """)
    t.save({"foo/conanfile.py": conanfile})
    t.run("inspect foo/conanfile.py")
    assert "shared: Some long explanation about shared option" in t.out
    assert "fpic: Yet another long explanation of fpic" in t.out


def test_missing_conanfile():
    t = TestClient()
    t.run("inspect missing/conanfile.py", assert_error=True)
    assert "Conanfile not found at" in t.out


def test_dot_and_folder_conanfile():
    t = TestClient()
    t.save({"conanfile.py": GenConanfile().with_name("foo")})
    t.run("inspect .")
    assert 'name: foo' in t.out
    t.save({"foo/conanfile.py": GenConanfile().with_name("foo")}, clean_first=True)
    t.run("inspect foo")
    assert 'name: foo' in t.out


def test_inspect_understands_setname():
    tc = TestClient()
    conanfile = textwrap.dedent("""
    from conan import ConanFile

    class Pkg(ConanFile):
        settings = "os", "arch"
        def set_name(self):
            self.name = "foo"

        def set_version(self):
            self.version = "1.0"
    """)

    tc.save({"conanfile.py": conanfile})
    tc.run("inspect .")
    assert "foo" in tc.out
    assert "1.0" in tc.out


def test_normal_inspect():
    tc = TestClient()
    tc.run("new basic -d name=pkg -d version=1.0")
    tc.run("inspect .")
    assert tc.out.splitlines() == ['description: A basic recipe',
                                   'generators: []',
                                   'homepage: <Your project homepage goes here>',
                                   'label: ',
                                   'languages: []',
                                   'license: <Your project license goes here>',
                                   'name: pkg',
                                   'options:',
                                   'options_definitions:',
                                   'package_type: None',
                                   'requires: []',
                                   'revision_mode: hash',
                                   'vendor: False',
                                   'version: 1.0']


def test_empty_inspect():
    conanfile = textwrap.dedent("""
    from conan import ConanFile

    class Pkg(ConanFile):
        pass""")
    tc = TestClient()
    tc.save({"conanfile.py": conanfile})
    tc.run("inspect . -f json")


def test_basic_new_inspect():
    tc = TestClient()
    tc.run("new basic")
    tc.run("inspect . -f json")

    tc.run("new cmake_lib -d name=pkg -d version=1.0 -f")
    tc.run("inspect . -f json")


def test_requiremens_inspect():
    tc = TestClient()
    conanfile = textwrap.dedent("""
    from conan import ConanFile

    class Pkg(ConanFile):
        requires = "zlib/1.2.13"
        license = "MIT", "Apache"
    """)
    tc.save({"conanfile.py": conanfile})
    tc.run("inspect .")
    assert ['generators: []',
            'label: ',
            'languages: []',
            "license: ['MIT', 'Apache']",
            'options:',
            'options_definitions:',
            'package_type: None',
            "requires: [{'ref': 'zlib/1.2.13', 'run': False, 'libs': True, 'skip': "
            "False, 'test': False, 'force': False, 'direct': True, 'build': "
            "False, 'transitive_headers': None, 'transitive_libs': None, 'headers': "
            "True, 'package_id_mode': None, 'visible': True}]",
            'revision_mode: hash',
            'vendor: False'] == tc.out.splitlines()


def test_pythonrequires_remote():
    tc = TestClient(default_server_user=True)
    pyrequires = textwrap.dedent("""
    from conan import ConanFile

    class MyBase:
        def set_name(self):
            self.name = "my_company_package"

    class PyReq(ConanFile):
        name = "pyreq"
        version = "1.0"
        package_type = "python-require"
    """)
    tc.save({"pyreq/conanfile.py": pyrequires})
    tc.run("create pyreq/")
    tc.run("upload pyreq/1.0 -r default")
    tc.run("search * -r default")
    assert "pyreq/1.0" in tc.out
    tc.run("remove * -c")
    conanfile = textwrap.dedent("""
    from conan import ConanFile

    class Pkg(ConanFile):
        python_requires = "pyreq/1.0"
        python_requires_extend = "pyreq.MyBase"

        def set_version(self):
            self.version = "1.0"
    """)
    tc.save({"conanfile.py": conanfile})
    # Not specifying the remote also works
    tc.run("inspect .")
    assert "pyreq/1.0: Downloaded recipe revision 0ca726ab0febe1100901fffb27dc421f" in tc.out
    assert "name: my_company_package" in tc.out
    assert "version: 1.0" in tc.out
    # It now finds it on the cache, because it was downloaded
    tc.run("inspect . -nr")
    assert "name: my_company_package" in tc.out
    assert "version: 1.0" in tc.out
    assert "'recipe': 'Cache'" in tc.out
    tc.run("remove pyreq/* -c")
    # And now no remotes fails
    tc.run("inspect . -nr", assert_error=True)
    assert "Cannot resolve python_requires 'pyreq/1.0': No remote defined" in tc.out


def test_serializable_inspect():
    tc = TestClient()
    tc.save({"conanfile.py": GenConanfile("a", "1.0")
            .with_requires("b/2.0")
            .with_setting("os")
            .with_option("shared", [True, False])
            .with_generator("CMakeDeps")})
    tc.run("inspect . --format=json")
    assert json.loads(tc.out)["name"] == "a"
