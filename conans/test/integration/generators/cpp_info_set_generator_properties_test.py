import os
import textwrap

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


@pytest.fixture(scope="module")
def setup_client():
    client = TestClient()
    custom_generator = textwrap.dedent("""
        from conans.model import Generator
        from conans import ConanFile
        from conans.model.conan_generator import GeneratorComponentsMixin
        import os


        class custom_generator(GeneratorComponentsMixin, Generator):
            name = "custom_generator"
            @property
            def filename(self):
                return "my-generator.txt"

            def _get_components_custom_names(self, cpp_info):
                ret = []
                for comp_name, comp in self.sorted_components(cpp_info).items():
                    comp_genname = comp.get_property("custom_name", generator=self.name)
                    ret.append("{}:{}".format(comp.name, comp_genname))
                return ret

            @property
            def content(self):
                info = []
                for pkg_name, cpp_info in self.deps_build_info.dependencies:
                    info.append("{}:{}".format(pkg_name, cpp_info.get_property("custom_name", self.name)))
                    info.extend(self._get_components_custom_names(cpp_info))
                return os.linesep.join(info)
        """)
    client.save({"custom_generator.py": custom_generator})
    client.run("config install custom_generator.py -tf generators")

    build_module = textwrap.dedent("""
        message("I am a build module")
        """)

    another_build_module = textwrap.dedent("""
        message("I am another build module")
        """)

    client.save({"consumer.py": GenConanfile("consumer", "1.0").with_requires("mypkg/1.0").
                with_generator("custom_generator").with_generator("cmake_find_package").
                with_generator("cmake_find_package_multi").with_generator("pkg_config").
                with_setting("build_type"),
                "mypkg_bm.cmake": build_module, "mypkg_anootherbm.cmake": another_build_module})
    return client


def get_files_contents(client, filenames):
    return [client.load(f) for f in filenames]


def test_same_results_components(setup_client):
    client = setup_client
    mypkg = textwrap.dedent("""
        import os
        from conans import ConanFile, CMake, tools
        class MyPkg(ConanFile):
            settings = "build_type"
            name = "mypkg"
            version = "1.0"
            exports_sources = ["mypkg_bm.cmake"]
            def package(self):
                self.copy("mypkg_bm.cmake", dst="lib")
            def package_info(self):
                self.cpp_info.set_property("cmake_file_name", "MyFileName")
                self.cpp_info.components["mycomponent"].libs = ["mycomponent-lib"]
                self.cpp_info.components["mycomponent"].set_property("cmake_target_name", "mycomponent-name")
                self.cpp_info.components["mycomponent"].set_property("cmake_build_modules", [os.path.join("lib", "mypkg_bm.cmake")])
                self.cpp_info.components["mycomponent"].set_property("custom_name", "mycomponent-name", "custom_generator")
        """)

    client.save({"mypkg.py": mypkg})
    client.run("export mypkg.py")
    client.run("install consumer.py --build missing -s build_type=Release")

    my_generator = client.load("my-generator.txt")
    assert "mycomponent:mycomponent-name" in my_generator

    files_to_compare = ["FindMyFileName.cmake", "MyFileNameConfig.cmake", "MyFileNameTargets.cmake",
                        "MyFileNameTarget-release.cmake", "MyFileNameConfigVersion.cmake", "mypkg.pc",
                        "mycomponent.pc"]
    new_approach_contents = get_files_contents(client, files_to_compare)

    mypkg = textwrap.dedent("""
        import os
        from conans import ConanFile
        class MyPkg(ConanFile):
            settings = "build_type"
            name = "mypkg"
            version = "1.0"
            exports_sources = ["mypkg_bm.cmake"]
            def package(self):
                self.copy("mypkg_bm.cmake", dst="lib")
            def package_info(self):
                self.cpp_info.components["mycomponent"].libs = ["mycomponent-lib"]
                self.cpp_info.filenames["cmake_find_package"] = "MyFileName"
                self.cpp_info.filenames["cmake_find_package_multi"] = "MyFileName"
                self.cpp_info.components["mycomponent"].names["cmake_find_package"] = "mycomponent-name"
                self.cpp_info.components["mycomponent"].names["cmake_find_package_multi"] = "mycomponent-name"
                self.cpp_info.components["mycomponent"].build_modules.append(os.path.join("lib", "mypkg_bm.cmake"))
        """)
    client.save({"mypkg.py": mypkg})
    client.run("export mypkg.py")
    client.run("install consumer.py --build=missing -s build_type=Release")

    old_approach_contents = get_files_contents(client, files_to_compare)

    assert new_approach_contents == old_approach_contents


def test_same_results_without_components(setup_client):
    client = setup_client
    mypkg = textwrap.dedent("""
        import os
        from conans import ConanFile
        class MyPkg(ConanFile):
            settings = "build_type"
            name = "mypkg"
            version = "1.0"
            exports_sources = ["mypkg_bm.cmake"]
            def package(self):
                self.copy("mypkg_bm.cmake", dst="lib")
            def package_info(self):
                self.cpp_info.set_property("cmake_file_name", "MyFileName")
                self.cpp_info.set_property("cmake_target_name", "mypkg-name")
                self.cpp_info.set_property("cmake_build_modules",[os.path.join("lib",
                                                                 "mypkg_bm.cmake")])
                self.cpp_info.set_property("custom_name", "mypkg-name", "custom_generator")
        """)

    client.save({"mypkg.py": mypkg})
    client.run("export mypkg.py")

    client.run("install consumer.py --build missing -s build_type=Release")

    with open(os.path.join(client.current_folder, "my-generator.txt")) as custom_gen_file:
        assert "mypkg:mypkg-name" in custom_gen_file.read()

    files_to_compare = ["FindMyFileName.cmake", "MyFileNameConfig.cmake", "MyFileNameTargets.cmake",
                        "MyFileNameTarget-release.cmake", "MyFileNameConfigVersion.cmake", "mypkg.pc"]
    new_approach_contents = get_files_contents(client, files_to_compare)

    mypkg = textwrap.dedent("""
        import os
        from conans import ConanFile
        class MyPkg(ConanFile):
            settings = "build_type"
            name = "mypkg"
            version = "1.0"
            exports_sources = ["mypkg_bm.cmake"]
            def package(self):
                self.copy("mypkg_bm.cmake", dst="lib")
            def package_info(self):
                self.cpp_info.filenames["cmake_find_package"] = "MyFileName"
                self.cpp_info.filenames["cmake_find_package_multi"] = "MyFileName"
                self.cpp_info.names["cmake_find_package"] = "mypkg-name"
                self.cpp_info.names["cmake_find_package_multi"] = "mypkg-name"
                self.cpp_info.names["custom_generator"] = "mypkg-name"
                self.cpp_info.build_modules.append(os.path.join("lib", "mypkg_bm.cmake"))
        """)
    client.save({"mypkg.py": mypkg})
    client.run("create mypkg.py")
    client.run("install consumer.py -s build_type=Release")

    old_approach_contents = get_files_contents(client, files_to_compare)

    assert new_approach_contents == old_approach_contents


def test_same_results_specific_generators(setup_client):
    client = setup_client
    mypkg = textwrap.dedent("""
        import os
        from conans import ConanFile
        class MyPkg(ConanFile):
            settings = "build_type"
            name = "mypkg"
            version = "1.0"
            exports_sources = ["mypkg_bm.cmake", "mypkg_anootherbm.cmake"]
            def package(self):
                self.copy("mypkg_bm.cmake", dst="lib")
                self.copy("mypkg_anootherbm.cmake", dst="lib")
            def package_info(self):
                self.cpp_info.set_property("cmake_file_name", "MyFileName", "cmake_find_package")
                self.cpp_info.set_property("cmake_file_name", "MyFileNameMulti", "cmake_find_package_multi")
                self.cpp_info.set_property("cmake_target_name", "mypkg-name", "cmake_find_package")
                self.cpp_info.set_property("cmake_target_name", "mypkg-name-multi", "cmake_find_package_multi")
                self.cpp_info.set_property("cmake_build_modules",[os.path.join("lib",
                                                                 "mypkg_bm.cmake")], "cmake_find_package")
                self.cpp_info.set_property("cmake_build_modules",[os.path.join("lib",
                                                                 "mypkg_anootherbm.cmake")], "cmake_find_package_multi")
        """)

    client.save({"mypkg.py": mypkg})
    client.run("export mypkg.py")

    client.run("install consumer.py --build missing -s build_type=Release")

    files_to_compare = ["FindMyFileName.cmake", "MyFileNameMultiConfig.cmake", "MyFileNameMultiTargets.cmake",
                        "MyFileNameMultiTarget-release.cmake", "MyFileNameMultiConfigVersion.cmake"]
    new_approach_contents = get_files_contents(client, files_to_compare)

    mypkg = textwrap.dedent("""
        import os
        from conans import ConanFile
        class MyPkg(ConanFile):
            settings = "build_type"
            name = "mypkg"
            version = "1.0"
            exports_sources = ["mypkg_bm.cmake", "mypkg_anootherbm.cmake"]
            def package(self):
                self.copy("mypkg_bm.cmake", dst="lib")
                self.copy("mypkg_anootherbm.cmake", dst="lib")
            def package_info(self):
                self.cpp_info.filenames["cmake_find_package"] = "MyFileName"
                self.cpp_info.filenames["cmake_find_package_multi"] = "MyFileNameMulti"
                self.cpp_info.names["cmake_find_package"] = "mypkg-name"
                self.cpp_info.names["cmake_find_package_multi"] = "mypkg-name-multi"
                self.cpp_info.build_modules["cmake_find_package"].append(os.path.join("lib", "mypkg_bm.cmake"))
                self.cpp_info.build_modules["cmake_find_package_multi"].append(os.path.join("lib", "mypkg_anootherbm.cmake"))
        """)
    client.save({"mypkg.py": mypkg})
    client.run("create mypkg.py")
    client.run("install consumer.py -s build_type=Release")

    old_approach_contents = get_files_contents(client, files_to_compare)

    assert new_approach_contents == old_approach_contents


def test_cmake_find_package_new_properties():
    # test new properties support for cmake_find_package, necessary for migration in cci
    # cmake_target_name --> cmake_module_target_name
    # cmake_file_name --> cmake_module_file_name
    # https://github.com/conan-io/conan/issues/9825

    client = TestClient()

    greetings = textwrap.dedent("""
        import os
        from conans import ConanFile
        class MyPkg(ConanFile):
            settings = "build_type"
            name = "greetings"
            version = "1.0"
            def package_info(self):
                self.cpp_info.set_property("cmake_module_target_name", "MyChat")
                self.cpp_info.set_property("cmake_module_file_name", "MyChat")
                self.cpp_info.components["sayhello"].set_property("cmake_module_target_name", "MySay")
                self.cpp_info.components["sayhellobye"].set_property("cmake_module_target_name", "MySayBye")
        """)
    client.save({"greetings.py": greetings})
    client.run("create greetings.py greetings/1.0@")
    client.run("install greetings/1.0@ -g cmake_find_package")
    find_package_contents = client.load("FindMyChat.cmake")
    assert "add_library(MyChat::MyChat" in find_package_contents
    assert "set(MyChat_COMPONENTS MyChat::MySay MyChat::MySayBye)" in find_package_contents

    # check the generated files are the same with cmake_target_name and cmake_file_name
    greetings = textwrap.dedent("""
        import os
        from conans import ConanFile
        class MyPkg(ConanFile):
            settings = "build_type"
            name = "greetings"
            version = "1.0"
            def package_info(self):
                self.cpp_info.set_property("cmake_target_name", "MyChat")
                self.cpp_info.set_property("cmake_file_name", "MyChat")
                self.cpp_info.components["sayhello"].set_property("cmake_target_name", "MySay")
                self.cpp_info.components["sayhellobye"].set_property("cmake_target_name", "MySayBye")
        """)
    client.save({"greetings.py": greetings})
    client.run("create greetings.py greetings/1.0@")
    client.run("install greetings/1.0@ -g cmake_find_package")
    find_package_contents_old = client.load("FindMyChat.cmake")
    assert find_package_contents_old == find_package_contents


def test_legacy_cmake_is_not_affected_by_set_property_usage():
    """
    "set_property" will have no effect on "cmake" legacy generator

    Originally posted: https://github.com/conan-io/conan-center-index/issues/7925
    """

    client = TestClient()

    greetings = textwrap.dedent("""
        import os
        from conans import ConanFile
        class MyPkg(ConanFile):
            settings = "build_type"
            name = "greetings"
            version = "1.0"

            def package_info(self):
                self.cpp_info.set_property("cmake_file_name", "MyChat")
                self.cpp_info.set_property("cmake_target_name", "MyChat")
                self.cpp_info.components["sayhello"].set_property("cmake_target_name", "MySay")
        """)
    client.save({"greetings.py": greetings})
    client.run("create greetings.py greetings/1.0@")
    client.run("install greetings/1.0@ -g cmake")
    conanbuildinfo = client.load("conanbuildinfo.cmake")
    # Let's check our final target is the pkg name instead of "MyChat"
    assert "set_property(TARGET CONAN_PKG::greetings" in conanbuildinfo
    assert "add_library(CONAN_PKG::greetings" in conanbuildinfo
    assert "set(CONAN_TARGETS CONAN_PKG::greetings)" in conanbuildinfo


def test_legacy_cmake_multi_is_not_affected_by_set_property_usage():
    """
    "set_property" will have no effect on "cmake_multi" legacy generator

    Originally posted: https://github.com/conan-io/conan/issues/10061
    """

    client = TestClient()

    greetings = textwrap.dedent("""
        import os
        from conans import ConanFile
        class MyPkg(ConanFile):
            settings = "build_type"
            name = "greetings"
            version = "1.0"

            def package_info(self):
                self.cpp_info.set_property("cmake_file_name", "MyChat")
                self.cpp_info.set_property("cmake_target_name", "MyChat")
                self.cpp_info.components["sayhello"].set_property("cmake_target_name", "MySay")
        """)
    client.save({"greetings.py": greetings})
    client.run("create greetings.py greetings/1.0@")
    client.run("install greetings/1.0@ -g cmake_multi")
    conanbuildinfo = client.load("conanbuildinfo_multi.cmake")
    # Let's check our final target is the pkg name instead of "MyChat"
    assert "set_property(TARGET CONAN_PKG::greetings" in conanbuildinfo
    assert "add_library(CONAN_PKG::greetings" in conanbuildinfo
    assert "set(CONAN_TARGETS CONAN_PKG::greetings)" in conanbuildinfo


def test_pkg_config_names(setup_client):
    client = setup_client
    mypkg = textwrap.dedent("""
        import os
        from conans import ConanFile
        class MyPkg(ConanFile):
            settings = "build_type"
            name = "mypkg"
            version = "1.0"
            def package_info(self):
                self.cpp_info.components["mycomponent"].libs = ["mycomponent-lib"]
                self.cpp_info.components["mycomponent"].set_property("pkg_config_name", "mypkg-config-name")
        """)

    client.save({"mypkg.py": mypkg})
    client.run("export mypkg.py")
    client.run("install consumer.py --build missing")

    with open(os.path.join(client.current_folder, "mypkg-config-name.pc")) as gen_file:
        assert "mypkg-config-name" in gen_file.read()
