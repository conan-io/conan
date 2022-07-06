import os
import platform
import textwrap

from conan.tools.files import load
from conans.test.assets.sources import gen_function_cpp
from conans.test.functional.toolchains.meson._base import TestMesonBase
from conans.test.utils.tools import TestClient


class TestMesonToolchainAndGnuFlags(TestMesonBase):

    def test_mesondeps(self):
        client = TestClient(path_with_spaces=False)
        client.run("new hello/0.1 -s")
        client.run("create . hello/0.1@ %s" % self._settings_str)
        app = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])

        conanfile_py = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.meson import Meson

        class App(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            requires = "hello/0.1"
            generators = "MesonDeps", "MesonToolchain"

            def layout(self):
                self.folders.build = "build"

            def build(self):
                meson = Meson(self)
                meson.configure()
                meson.build()
        """)

        meson_build = textwrap.dedent("""
        project('tutorial', 'cpp')
        cxx = meson.get_compiler('cpp')
        hello = cxx.find_library('hello', required: true)
        executable('demo', 'main.cpp', dependencies: hello)
        """)

        client.save({"conanfile.py": conanfile_py,
                     "meson.build": meson_build,
                     "main.cpp": app},
                    clean_first=True)

        client.run("install . %s" % self._settings_str)
        client.run("build .")
        assert "[2/2] Linking target demo" in client.out

    def test_mesondeps_flags_are_being_appended_and_not_replacing_toolchain_ones(self):
        """
        Test MesonDeps and MesonToolchain are keeping all the flags/definitions defined
        from both generators and nothing is being messed up.
        """
        client = TestClient(path_with_spaces=False)
        if platform.system() == "Windows":
            deps_flags = '"/GA", "/analyze:quiet"'
            flags = '"/Wall", "/W4"'
        else:
            deps_flags = '"-Wpedantic", "-Werror"'
            flags = '"-Wall", "-finline-functions"'
        # Dependency - hello/0.1
        conanfile_py = textwrap.dedent("""
        from conan import ConanFile

        class HelloConan(ConanFile):
            name = "hello"
            version = "0.1"

            def package_info(self):
                self.cpp_info.libs = ["hello"]
                self.cpp_info.cxxflags = [{}]
                self.cpp_info.defines = ['DEF1=one_string', 'DEF2=other_string']
        """.format(deps_flags))
        client.save({"conanfile.py": conanfile_py})
        client.run("create . %s" % self._settings_str)
        # Dependency - other/0.1
        conanfile_py = textwrap.dedent("""
        from conan import ConanFile

        class OtherConan(ConanFile):
            name = "other"
            version = "0.1"

            def package_info(self):
                self.cpp_info.libs = ["other"]
                self.cpp_info.defines = ['DEF3=simple_string']
        """)
        client.save({"conanfile.py": conanfile_py}, clean_first=True)
        client.run("create . %s" % self._settings_str)

        # Consumer using MesonDeps and MesonToolchain
        conanfile_py = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.meson import Meson, MesonDeps, MesonToolchain

        class App(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            requires = "hello/0.1", "other/0.1"

            def layout(self):
                self.folders.build = "build"

            def generate(self):
                tc = MesonDeps(self)
                tc.generate()
                tc = MesonToolchain(self)
                tc.preprocessor_definitions["VAR"] = "VALUE"
                tc.preprocessor_definitions["VAR2"] = "VALUE2"
                tc.generate()

            def build(self):
                meson = Meson(self)
                meson.configure()
                meson.build()
        """)

        meson_build = textwrap.dedent("""
            project('tutorial', 'cpp')
            cxx = meson.get_compiler('cpp')
            # It's not needed to declare "hello/0.1" as a dependency, only interested in flags
            executable('demo', 'main.cpp')
        """)
        client.save({"conanfile.py": conanfile_py,
                     "meson.build": meson_build,
                     "main.cpp": "int main()\n{return 0;}\n"},
                    clean_first=True)

        client.run("install . %s -c 'tools.build:cxxflags=[%s]'" % (self._settings_str, flags))
        client.run("build .")
        deps_flags = deps_flags.replace('"', "").replace(",", "")
        flags = flags.replace('"', "").replace(",", "")
        meson_log_path = os.path.join(client.current_folder, "build", "meson-logs", "meson-log.txt")
        meson_log = load(None, meson_log_path)
        meson_log = meson_log.replace("\\", "/")
        assert "Build Options: " \
               "'--native-file {folder}/conan_meson_native.ini' " \
               "'--native-file {folder}/conan_meson_deps_flags.ini'" \
               "".format(folder=client.current_folder.replace("\\", "/")) in meson_log
        # Flags/Defines from deps and consumer are appearing in meson-log.txt as part
        # of the command-line
        assert '%s -DVAR="VALUE" -DVAR2="VALUE2" %s' % (flags, deps_flags) in meson_log
        assert '-DDEF3=simple_string -DDEF1=one_string -DDEF2=other_string' in meson_log
