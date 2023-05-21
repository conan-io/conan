import os
import platform
import re
import sys
import textwrap

import pytest

from conans.model.recipe_ref import RecipeReference
from conans.test.assets.sources import gen_function_cpp, gen_function_h
from conans.test.functional.toolchains.meson._base import TestMesonBase
from conans.test.utils.tools import TestClient


class MesonToolchainTest(TestMesonBase):
    _conanfile_py = textwrap.dedent("""
    from conan import ConanFile
    from conan.tools.meson import Meson, MesonToolchain


    class App(ConanFile):
        settings = "os", "arch", "compiler", "build_type"
        options = {"shared": [True, False], "fPIC": [True, False]}
        default_options = {"shared": False, "fPIC": True}

        def config_options(self):
            if self.settings.os == "Windows":
                self.options.rm_safe("fPIC")

        def configure(self):
            if self.options.shared:
                self.options.rm_safe("fPIC")

        def layout(self):
            self.folders.generators = 'build/gen_folder'
            self.folders.build = "build"

        def generate(self):
            tc = MesonToolchain(self)
            tc.project_options["STRING_DEFINITION"] = "Text"
            tc.project_options["TRUE_DEFINITION"] = True
            tc.project_options["FALSE_DEFINITION"] = False
            tc.project_options["INT_DEFINITION"] = 42
            tc.project_options["ARRAY_DEFINITION"] = ["Text1", "Text2"]
            tc.generate()

        def build(self):
            meson = Meson(self)
            meson.configure()
            meson.build(target='hello')
            meson.build(target='demo')
    """)

    _meson_options_txt = textwrap.dedent("""
    option('STRING_DEFINITION', type : 'string', description : 'a string option')
    option('INT_DEFINITION', type : 'integer', description : 'an integer option', value: 0)
    option('FALSE_DEFINITION', type : 'boolean', description : 'a boolean option (false)')
    option('TRUE_DEFINITION', type : 'boolean', description : 'a boolean option (true)')
    option('ARRAY_DEFINITION', type : 'array', description : 'an array option')
    option('HELLO_MSG', type : 'string', description : 'message to print')
    """)

    _meson_build = textwrap.dedent("""
    project('tutorial', 'cpp')
    add_global_arguments('-DSTRING_DEFINITION="' + get_option('STRING_DEFINITION') + '"',
                         language : 'cpp')
    add_global_arguments('-DHELLO_MSG="' + get_option('HELLO_MSG') + '"', language : 'cpp')
    hello = library('hello', 'hello.cpp')
    executable('demo', 'main.cpp', link_with: hello)
    """)

    def test_definition_of_global_options(self):
        hello_h = gen_function_h(name="hello")
        hello_cpp = gen_function_cpp(name="hello", preprocessor=["STRING_DEFINITION"])
        app = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])

        self.t.save({"conanfile.py": self._conanfile_py,
                     "meson.build": self._meson_build,
                     "meson_options.txt": self._meson_options_txt,
                     "hello.h": hello_h,
                     "hello.cpp": hello_cpp,
                     "main.cpp": app})

        self.t.run("install .")

        content = self.t.load(os.path.join("build", "gen_folder", "conan_meson_native.ini"))

        self.assertIn("[project options]", content)
        self.assertIn("STRING_DEFINITION = 'Text'", content)
        self.assertIn("TRUE_DEFINITION = true", content)
        self.assertIn("FALSE_DEFINITION = false", content)
        self.assertIn("INT_DEFINITION = 42", content)
        self.assertIn("ARRAY_DEFINITION = ['Text1', 'Text2']", content)

        self.assertIn("[built-in options]", content)
        self.assertIn("buildtype = 'release'", content)

        self.t.run("build .")
        self.t.run_command(os.path.join("build", "demo"))

        self.assertIn("hello: Release!", self.t.out)
        self.assertIn("STRING_DEFINITION: Text", self.t.out)

        self.assertIn("[properties]", content)
        self.assertNotIn("needs_exe_wrapper", content)

        self._check_binary()

    def test_meson_default_dirs(self):
        self.t.run("new meson_exe -d name=hello -d version=1.0")
        # self.t.run("new meson_exe -d name=hello -d version=1.0 -m meson_exe")

        meson_build = textwrap.dedent("""
        project('tutorial', 'cpp')
        # Creating specific library
        hello = library('hello', 'src/hello.cpp', install: true)
        # Creating specific executable
        executable('demo', 'src/main.cpp', link_with: hello, install: true)
        # Creating specific data in src/ (they're going to be exported)
        install_data(['src/file1.txt', 'src/file2.txt'])
        """)
        conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.meson import Meson
        class HelloConan(ConanFile):
            name = "hello"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"
            exports_sources = "meson.build", "src/*"
            generators = "MesonToolchain"
            package_type = "application"

            def layout(self):
                self.folders.build = "build"
                # Only adding "res" to resdirs
                self.cpp.package.resdirs = ["res"]

            def build(self):
                meson = Meson(self)
                meson.configure()
                meson.build()

            def package(self):
                meson = Meson(self)
                meson.install()
        """)
        test_conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.build import cross_building
        class HelloTestConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"

            def requirements(self):
                self.requires(self.tested_reference_str)

            def test(self):
                if not cross_building(self):
                    self.run("demo", env="conanrun")
        """)
        # Replace meson.build, conanfile.py and test_package/conanfile.py
        self.t.save({"meson.build": meson_build,
                     "conanfile.py": conanfile,
                     "test_package/conanfile.py": test_conanfile,
                     "src/file1.txt": "", "src/file2.txt": ""})
        self.t.run("create .")
        # Check if all the files are in the final directories
        ref = RecipeReference.loads("hello/1.0")
        pref = self.t.get_latest_package_reference(ref)
        package_folder = self.t.get_latest_pkg_layout(pref).package()
        if platform.system() == "Windows":
            assert os.path.exists(os.path.join(package_folder, "lib", "hello.lib"))
            assert os.path.exists(os.path.join(package_folder, "bin", "hello.dll"))
            assert os.path.exists(os.path.join(package_folder, "bin", "demo.exe"))
        else:
            ext = "dylib" if platform.system() == "Darwin" else "so"
            assert os.path.exists(os.path.join(package_folder, "bin", "demo"))
            assert os.path.exists(os.path.join(package_folder, "lib", "libhello." + ext))
        # res/tutorial -> tutorial is being added automatically by Meson
        assert os.path.exists(os.path.join(package_folder, "res", "tutorial", "file1.txt"))
        assert os.path.exists(os.path.join(package_folder, "res", "tutorial", "file2.txt"))


@pytest.mark.tool("meson")
@pytest.mark.skipif(sys.version_info.minor < 8, reason="Latest Meson versions needs Python >= 3.8")
def test_meson_and_additional_machine_files_composition():
    """
    Testing when users wants to append their own meson machine files and override/complement some
    sections from Conan file ones.

    See more information in Meson web page: https://mesonbuild.com/Machine-files.html

    In this test, we're overriding only the Meson section ``[binaries]`` for instance.
    """
    profile = textwrap.dedent("""
        [settings]
        os=Windows
        arch=x86_64
        compiler=gcc
        compiler.version=9
        compiler.cppstd=17
        compiler.libcxx=libstdc++11
        build_type=Release

        [conf]
        tools.meson.mesontoolchain:extra_machine_files=["myfilename.ini"]
   """)
    myfilename = textwrap.dedent("""
    [project options]
    my_option = 'fake-option'
    """)
    conanfile = textwrap.dedent("""
    from conan import ConanFile
    from conan.tools.meson import Meson
    class Pkg(ConanFile):
        settings = "os", "compiler", "build_type", "arch"
        generators = "MesonToolchain"
        def build(self):
            meson = Meson(self)
            meson.configure()
            meson.build()
    """)
    client = TestClient()
    client.save({"conanfile.py": conanfile,
                 "build/myfilename.ini": myfilename,
                 "meson.build": "project('tutorial', 'cpp')",  # dummy one
                 "profile": profile})

    client.run("install . -pr:h=profile -pr:b=profile")
    client.run("build . -pr:h=profile -pr:b=profile", assert_error=True)
    # Checking the order of the appended user file (the order matters)
    match = re.search(r"meson setup --native-file .* --native-file \"myfilename\.ini\"", client.out)
    assert match
