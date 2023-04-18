import json
import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_basic_inspect():
    t = TestClient()
    t.save({"foo/conanfile.py": GenConanfile().with_name("foo").with_shared_option()})
    t.run("inspect foo/conanfile.py")
    lines = t.out.splitlines()
    assert lines == ["default_options:",
                     "    shared: False",

                     'generators: []',
                     'name: foo',
                     'no_copy_source: False',
                     "options:",
                     "    shared: [True, False]",
                     'revision_mode: hash',
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


def test_setname():
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
    assert tc.out == textwrap.dedent("""
    description: A basic recipe
    generators: []
    homepage: <Your project homepage goes here>
    license: <Your project license goes here>
    name: pkg
    no_copy_source: False
    revision_mode: hash
    version: 1.0""")


def test_normal_inspect2():
    tc = TestClient()
    tc.run("new basic -d name=pkg -d version=1.0")
    tc.run("inspect-proper .")
    assert tc.out == textwrap.dedent("""
    ('buildenv_info: OrderedDict()\n'
 'conf_info: Conf: OrderedDict()\n'
 'cpp: <conans.model.layout.Infos object at 0x106c0bb50>\n'
 "cpp_info: Component: 'None' Var: '_includedirs' Value: '['include']'\n"
 "Component: 'None' Var: '_srcdirs' Value: 'None'\n"
 "Component: 'None' Var: '_libdirs' Value: '['lib']'\n"
 "Component: 'None' Var: '_resdirs' Value: 'None'\n"
 "Component: 'None' Var: '_bindirs' Value: '['bin']'\n"
 "Component: 'None' Var: '_builddirs' Value: 'None'\n"
 "Component: 'None' Var: '_frameworkdirs' Value: 'None'\n"
 "Component: 'None' Var: '_objects' Value: 'None'\n"
 "Component: 'None' Var: '_system_libs' Value: 'None'\n"
 "Component: 'None' Var: '_frameworks' Value: 'None'\n"
 "Component: 'None' Var: '_libs' Value: 'None'\n"
 "Component: 'None' Var: '_defines' Value: 'None'\n"
 "Component: 'None' Var: '_cflags' Value: 'None'\n"
 "Component: 'None' Var: '_cxxflags' Value: 'None'\n"
 "Component: 'None' Var: '_sharedlinkflags' Value: 'None'\n"
 "Component: 'None' Var: '_exelinkflags' Value: 'None'\n"
 'description: A basic recipe\n'
 'display_name: \n'
 'env_info: <conans.model.build_info.MockInfoProperty object at 0x106c0b970>\n'
 'env_scripts:\n'
 "folders: {'_base_source': None, '_base_build': None, '_base_package': None, "
 "'_base_generators': None, '_base_export': None, '_base_export_sources': "
 "None, '_base_recipe_metadata': None, '_base_pkg_metadata': None, 'source': "
 "'', 'build': '', 'package': '', 'generators': '', 'root': None, "
 "'subproject': None, 'build_folder_vars': None}\n"
 'generators: []\n'
 'homepage: <Your project homepage goes here>\n'
 'layouts: <conans.model.layout.Layouts object at 0x106bffc40>\n'
 'license: <Your project license goes here>\n'
 'name: pkg\n'
 'no_copy_source: False\n'
 'options: \n'
 'output: <conan.api.output.ConanOutput object at 0x106be7c40>\n'
 'recipe_folder: '
 '/private/var/folders/lw/6bflvp3s3t5b56n2p_bj_vx80000gn/T/tmpph9zplaeconans/path '
 'with spaces\n'
 'recipe_path: '
 '/private/var/folders/lw/6bflvp3s3t5b56n2p_bj_vx80000gn/T/tmpph9zplaeconans/path '
 'with spaces\n'
 'requires: odict_values([])\n'
 'revision_mode: hash\n'
 'runenv_info: OrderedDict()\n'
 'system_requires:\n'
 'user_info: <conans.model.build_info.MockInfoProperty object at 0x106c0be20>\n'
 'version: 1.0\n'
 'virtualbuildenv: True\n'
 'virtualrunenv: True\n')""")


def test_normal_inspect3():
    tc = TestClient()
    tc.run("new basic -d name=pkg -d version=1.0")
    tc.run("inspect-serialize .")
    assert tc.out == textwrap.dedent("""
    ('license: <Your project license goes here>\n'
 'description: A basic recipe\n'
 'homepage: <Your project homepage goes here>\n'
 'revision_mode: hash\n'
 'package_type: None\n'
 'options:\n'
 'system_requires:\n'
 'recipe_folder: '
 '/private/var/folders/lw/6bflvp3s3t5b56n2p_bj_vx80000gn/T/tmpr4kn1qz8conans/path '
 'with spaces\n'
 'cpp_info:\n'
 "    root: {'includedirs': ['include'], 'srcdirs': None, 'libdirs': ['lib'], "
 "'resdirs': None, 'bindirs': ['bin'], 'builddirs': None, 'frameworkdirs': "
 "None, 'system_libs': None, 'frameworks': None, 'libs': None, 'defines': "
 "None, 'cflags': None, 'cxxflags': None, 'sharedlinkflags': None, "
 "'exelinkflags': None, 'objects': None, 'sysroot': None, 'requires': None, "
 "'properties': None}\n"
 'label: \n')""")
