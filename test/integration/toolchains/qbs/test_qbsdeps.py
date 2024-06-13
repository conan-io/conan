import json
import os
import platform

import pytest
import textwrap

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient
from conans.util.files import load


def test_empty_package():
    # Checks default values generated by conan for cpp_info
    client = TestClient()
    client.save({'conanfile.py': GenConanfile("mylib", "0.1")})
    client.run('create .')
    client.run('install --requires=mylib/0.1@ -g QbsDeps')

    module_path = os.path.join(client.current_folder, 'conan-qbs-deps', 'mylib.json')
    module_content = json.loads(load(module_path))

    assert module_content.get('package_name') == 'mylib'
    assert module_content.get('version') == '0.1'

    package_dir = module_content['package_dir']
    cpp_info = module_content['cpp_info']
    package_dir = package_dir.replace("/", "\\") if platform.system() == "Windows" else package_dir
    assert cpp_info.get('includedirs') == [os.path.join(package_dir, 'include')]
    assert cpp_info.get('libdirs') == [os.path.join(package_dir, 'lib')]
    assert cpp_info.get('bindirs') == [os.path.join(package_dir, 'bin')]
    assert cpp_info.get('libs') == []
    assert cpp_info.get('frameworkdirs') == []
    assert cpp_info.get('frameworks') == []
    assert cpp_info.get('defines') == []
    assert cpp_info.get('cflags') == []
    assert cpp_info.get('cxxflags') == []

    assert module_content.get('settings') == {}
    assert module_content.get('options') == {}


def test_empty_dirs():
    # Checks that we can override default values with empty directories
    conanfile = textwrap.dedent('''
        from conan import ConanFile

        class Recipe(ConanFile):
            name = 'mylib'
            version = '0.1'

            def package_info(self):
                self.cpp_info.includedirs = []
                self.cpp_info.libdirs = []
                self.cpp_info.bindirs = []
                self.cpp_info.libs = []
                self.cpp_info.frameworkdirs = []
        ''')
    client = TestClient()
    client.save({'conanfile.py': conanfile})
    client.run('create .')
    client.run('install --requires=mylib/0.1@ -g QbsDeps')

    module_path = os.path.join(client.current_folder, 'conan-qbs-deps', 'mylib.json')
    assert os.path.exists(module_path)
    module_content = json.loads(load(module_path))

    assert module_content.get('package_name') == 'mylib'
    assert module_content.get('version') == '0.1'

    assert 'cpp_info' in module_content
    cpp_info = module_content['cpp_info']
    assert cpp_info.get('includedirs') == []
    assert cpp_info.get('libdirs') == []
    assert cpp_info.get('bindirs') == []
    assert cpp_info.get('libs') == []
    assert cpp_info.get('frameworkdirs') == []
    assert cpp_info.get('frameworks') == []
    assert cpp_info.get('defines') == []
    assert cpp_info.get('cflags') == []
    assert cpp_info.get('cxxflags') == []

    assert module_content.get('settings') == {}
    assert module_content.get('options') == {}


def test_pkg_config_name():
    # Checks we can override module name using the "pkg_config_name" property
    conanfile = textwrap.dedent('''
        from conan import ConanFile

        class Recipe(ConanFile):
            name = 'mylib'
            version = '0.1'
            def package_info(self):
                self.cpp_info.set_property("pkg_config_name", "myfirstlib")
        ''')
    client = TestClient()
    client.save({'conanfile.py': conanfile})
    client.run('create .')
    client.run('install --requires=mylib/0.1@ -g QbsDeps')

    module_path = os.path.join(client.current_folder, 'conan-qbs-deps', 'myfirstlib.json')
    assert os.path.exists(module_path)


@pytest.mark.parametrize('host_os, arch, build_type', [
    ('Linux', 'x86_64', 'Debug'),
    ('Linux', 'x86_64', 'Release'),
    ('Linux', 'armv8', 'Debug'),
    ('Windows', 'x86_64', 'Debug'),
    ('Macos', 'armv8', 'Release'),
])
def test_settings(host_os, arch, build_type):

    conanfile = textwrap.dedent('''
    from conan import ConanFile
    class Recipe(ConanFile):
        settings = "os", "arch", "build_type"
        name = "mylib"
        version = "0.1"
    ''')

    client = TestClient()
    client.save({'conanfile.py': conanfile})
    common_cmd = '-s:h os={os} -s:h arch={arch} -s:h build_type={build_type}'.format(
        os=host_os, arch=arch, build_type=build_type
    )
    client.run('create . ' + common_cmd)
    client.run('install --requires=mylib/0.1@ -g QbsDeps ' + common_cmd)

    module_path = os.path.join(client.current_folder, 'conan-qbs-deps', 'mylib.json')
    assert os.path.exists(module_path)
    module_content = json.loads(load(module_path))

    assert 'settings' in module_content
    # Qbs only cares about os and arch (and maybe build type)
    assert module_content['settings'].get('os') == host_os
    assert module_content['settings'].get('arch') == arch
    assert module_content['settings'].get('build_type') == build_type


@pytest.mark.parametrize('shared', ['False', 'True'])
def test_options(shared):
    conanfile = textwrap.dedent('''
    from conan import ConanFile
    class Recipe(ConanFile):
        options = {"shared": [True, False]}
        default_options = {"shared": False}
        name = 'mylib'
        version = '0.1'
    ''')

    client = TestClient()
    client.save({'conanfile.py': conanfile})
    common_cmd = '-o:h shared={shared}'.format(shared=shared)
    client.run('create . ' + common_cmd)
    client.run('install --requires=mylib/0.1@ -g QbsDeps ' + common_cmd)

    module_path = os.path.join(client.current_folder, 'conan-qbs-deps', 'mylib.json')
    assert os.path.exists(module_path)
    module_content = json.loads(load(module_path))

    assert 'options' in module_content
    assert module_content['options'].get('shared') == shared


def test_components():
    """
        Checks a package with multiple components.
        Here we test component name and version override as well as the defaults.
    """
    conanfile = textwrap.dedent('''
    from conan import ConanFile

    class Recipe(ConanFile):

        name = 'mylib'
        version = '0.1'
        def package_info(self):
            self.cpp_info.components["mycomponent1"].set_property("pkg_config_name",
                                                                  "mycomponent")
            self.cpp_info.components["mycomponent2"].set_property("component_version",
                                                                  "19.8.199")
    ''')

    client = TestClient()
    client.save({'conanfile.py': conanfile})
    client.run('create .')
    client.run('install --requires=mylib/0.1@ -g QbsDeps')

    module1_path = os.path.join(client.current_folder, 'conan-qbs-deps', 'mycomponent.json')
    assert os.path.exists(module1_path)
    module1_content = json.loads(load(module1_path))

    assert module1_content.get('package_name') == 'mylib'
    assert module1_content.get('version') == '0.1'
    assert module1_content.get('dependencies') == []

    module2_path = os.path.join(client.current_folder, 'conan-qbs-deps', 'mycomponent2.json')
    assert os.path.exists(module2_path)
    module2_content = json.loads(load(module2_path))

    assert module2_content.get('package_name') == 'mylib'
    assert module2_content.get('version') == '19.8.199'
    assert module2_content.get('dependencies') == []

    main_module_path = os.path.join(client.current_folder, 'conan-qbs-deps', 'mylib.json')
    assert os.path.exists(main_module_path)
    main_module_content = json.loads(load(main_module_path))

    assert main_module_content.get('package_name') == 'mylib'
    assert main_module_content.get('version') == '0.1'
    assert main_module_content.get('dependencies') == [
        {"name": "mycomponent", "version": "0.1"},  # name overriden, version default
        {"name": "mycomponent2", "version": "19.8.199"}  # name default, version overriden
    ]


def test_cpp_info_requires():
    """
    Testing a complex structure like:

    * first/0.1
        - Global pkg_config_name == "myfirstlib"
        - Components: "cmp1"
    * other/0.1
    * second/0.2
        - Requires: "first/0.1"
        - Components: "mycomponent", "myfirstcomp"
            + "mycomponent" requires "first::cmp1"
            + "myfirstcomp" requires "mycomponent"
    * third/0.4
        - Requires: "second/0.2", "other/0.1"

    Expected file structure after running QbsDeps as generator:
        - other.json
        - myfirstlib-cmp1.json
        - myfirstlib.json
        - second-mycomponent.json
        - second-myfirstcomp.json
        - second.json
        - third.json
    """

    client = TestClient()
    # first
    conanfile = textwrap.dedent('''
        from conan import ConanFile

        class Recipe(ConanFile):
            name = "first"
            version = "0.1"
            def package_info(self):
                self.cpp_info.set_property("pkg_config_name", "myfirstlib")
                self.cpp_info.components["cmp1"].libs = ["libcmp1"]
    ''')
    client.save({"conanfile.py": conanfile})
    client.run("create .")
    # other
    client.save({"conanfile.py": GenConanfile("other", "0.1")}, clean_first=True)
    client.run("create .")

    # second
    conanfile = textwrap.dedent('''
    from conan import ConanFile

    class PkgConfigConan(ConanFile):
        name = "second"
        version = "0.2"
        requires = "first/0.1"

        def package_info(self):
            self.cpp_info.components["mycomponent"].requires.append("first::cmp1")
            self.cpp_info.components["myfirstcomp"].requires.append("mycomponent")
    ''')
    client.save({"conanfile.py": conanfile}, clean_first=True)
    client.run("create .")

    # third
    client.save({"conanfile.py": GenConanfile("third", "0.3").with_require("second/0.2")
                                                             .with_require("other/0.1")},
                clean_first=True)
    client.run("create .")

    client2 = TestClient(cache_folder=client.cache_folder)
    conanfile = textwrap.dedent("""
        [requires]
        third/0.3
        other/0.1

        [generators]
        QbsDeps
    """)
    client2.save({"conanfile.txt": conanfile})
    client2.run("install .")

    # first
    module_path = os.path.join(client2.current_folder, 'conan-qbs-deps', 'cmp1.json')
    assert os.path.exists(module_path)
    module_content = json.loads(load(module_path))

    assert module_content.get('package_name') == 'first'
    assert module_content.get('version') == '0.1'
    assert module_content.get('dependencies') == []

    module_path = os.path.join(client2.current_folder, 'conan-qbs-deps', 'myfirstlib.json')
    assert os.path.exists(module_path)
    module_content = json.loads(load(module_path))

    assert module_content.get('package_name') == 'first'
    assert module_content.get('version') == '0.1'
    assert module_content.get('dependencies') == [{'name': 'cmp1', 'version': '0.1'}]

    # other
    module_path = os.path.join(client2.current_folder, 'conan-qbs-deps', 'other.json')
    assert os.path.exists(module_path)
    module_content = json.loads(load(module_path))

    assert module_content.get('package_name') == 'other'
    assert module_content.get('version') == '0.1'
    assert module_content.get('dependencies') == []

    # second.mycomponent
    module_path = os.path.join(client2.current_folder, 'conan-qbs-deps', 'mycomponent.json')
    assert os.path.exists(module_path)
    module_content = json.loads(load(module_path))

    assert module_content.get('package_name') == 'second'
    assert module_content.get('version') == '0.2'
    assert module_content.get('dependencies') == [{'name': 'cmp1', 'version': '0.1'}]

    # second.myfirstcomp
    module_path = os.path.join(client2.current_folder, 'conan-qbs-deps', 'myfirstcomp.json')
    assert os.path.exists(module_path)
    module_content = json.loads(load(module_path))

    assert module_content.get('package_name') == 'second'
    assert module_content.get('version') == '0.2'
    assert module_content.get('dependencies') == [{'name': 'mycomponent', 'version': '0.2'}]

    # second
    module_path = os.path.join(client2.current_folder, 'conan-qbs-deps', 'second.json')
    assert os.path.exists(module_path)
    module_content = json.loads(load(module_path))

    assert module_content.get('package_name') == 'second'
    assert module_content.get('version') == '0.2'
    assert module_content.get('dependencies') == [
        {'name': 'mycomponent', 'version': '0.2'},
        {'name': 'myfirstcomp', 'version': '0.2'}
    ]

    # third
    module_path = os.path.join(client2.current_folder, 'conan-qbs-deps', 'third.json')
    assert os.path.exists(module_path)
    module_content = json.loads(load(module_path))

    assert module_content.get('package_name') == 'third'
    assert module_content.get('version') == '0.3'
    assert module_content.get('dependencies') == [
        {'name': 'second', 'version': '0.2'},
        {'name': 'other', 'version': '0.1'}
    ]


# see https://github.com/conan-io/conan/issues/10341
def test_components_conflict():
    """ If component has the same name as the root package, skip root package
    """
    conanfile = textwrap.dedent('''
    from conan import ConanFile

    class Recipe(ConanFile):

        name = 'mylib'
        version = '0.1'
        def package_info(self):
            self.cpp_info.set_property("pkg_config_name", "mycoollib")
            self.cpp_info.components["_mycoollib"].defines = ["MAGIC_DEFINE"]
            self.cpp_info.components["_mycoollib"].set_property("pkg_config_name",
                                                               "mycoollib")
    ''')

    client = TestClient()
    client.save({'conanfile.py': conanfile})
    client.run('create .')
    client.run('install --requires=mylib/0.1@ -g QbsDeps')

    module_path = os.path.join(client.current_folder, 'conan-qbs-deps', 'mycoollib.json')
    assert os.path.exists(module_path)
    module_content = json.loads(load(module_path))

    assert module_content.get('package_name') == 'mylib'
    assert module_content.get('version') == '0.1'
    assert 'cpp_info' in module_content
    cpp_info = module_content['cpp_info']
    assert cpp_info.get('defines') == ["MAGIC_DEFINE"]
