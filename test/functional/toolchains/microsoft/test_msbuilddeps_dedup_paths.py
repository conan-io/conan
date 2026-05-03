import os
import platform
import re
import textwrap

import pytest

from conan.test.assets.visual_project_files import get_vs_project_files
from conan.test.utils.tools import TestClient


@pytest.mark.tool("visual_studio")
@pytest.mark.skipif(platform.system() != "Windows", reason="Requires MSBuild")
def test_msbuilddeps_dedup_paths_functional():
    """Real MSBuild build with multi-component package sharing the same
    include/lib dirs — verifies no duplicate /I flags in cl.exe invocation.
    """

    # 3 components, all pointing to the same include/ and lib/
    mypkg = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import save

        class MultiCompPkg(ConanFile):
            name = "mypkg"
            version = "1.0"
            package_type = "static-library"

            def package(self):
                save(self, os.path.join(self.package_folder, "include", "mypkg.h"),
                     '#pragma once\\n')
                save(self, os.path.join(self.package_folder, "lib", "core.lib"), "")
                save(self, os.path.join(self.package_folder, "lib", "client.lib"), "")
                save(self, os.path.join(self.package_folder, "lib", "server.lib"), "")

            def package_info(self):
                self.cpp_info.components["core"].libs = ["core"]
                self.cpp_info.components["core"].includedirs = ["include"]
                self.cpp_info.components["core"].libdirs = ["lib"]

                self.cpp_info.components["client"].libs = ["client"]
                self.cpp_info.components["client"].includedirs = ["include"]
                self.cpp_info.components["client"].libdirs = ["lib"]
                self.cpp_info.components["client"].requires = ["core"]

                self.cpp_info.components["server"].libs = ["server"]
                self.cpp_info.components["server"].includedirs = ["include"]
                self.cpp_info.components["server"].libdirs = ["lib"]
                self.cpp_info.components["server"].requires = ["core"]
        """)

    consumer = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.microsoft import MSBuild
        class Consumer(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            requires = "mypkg/1.0"
            generators = "MSBuildDeps", "MSBuildToolchain"
            def build(self):
                msbuild = MSBuild(self)
                msbuild.build("MyProject.sln")
        """)

    main_cpp = textwrap.dedent("""\
        #include <iostream>
        int main() {
            std::cout << "Hello" << std::endl;
            return 0;
        }
        """)

    client = TestClient(path_with_spaces=False)

    client.save({"pkg/conanfile.py": mypkg})
    client.run("create pkg")

    files = get_vs_project_files()
    files["MyProject/main.cpp"] = main_cpp
    files["conanfile.py"] = consumer

    # Inject conan props into the vcxproj
    props_path = os.path.join(client.current_folder, "conandeps.props")
    toolchain_path = os.path.join(client.current_folder, "conantoolchain.props")
    old = r'<Import Project="$(VCTargetsPath)\Microsoft.Cpp.Default.props" />'
    new = old + '<Import Project="{}" />'.format(props_path)
    files["MyProject/MyProject.vcxproj"] = files["MyProject/MyProject.vcxproj"].replace(old, new)
    old = r'<Import Project="$(VCTargetsPath)\Microsoft.Cpp.props" />'
    new = '<Import Project="{}" />'.format(toolchain_path) + old
    files["MyProject/MyProject.vcxproj"] = files["MyProject/MyProject.vcxproj"].replace(old, new)

    client.save(files, clean_first=True)

    # Verbose build so we can inspect cl.exe flags
    client.run("build . -c tools.build:verbosity=verbose")

    assert "Build succeeded." in client.out

    # Extract /I paths from cl.exe command line
    include_paths = re.findall(r'/I"([^"]+)"', client.out)

    assert len(include_paths) > 0, \
        "Expected /I flags in verbose MSBuild output"

    # No duplicates
    assert len(include_paths) == len(set(include_paths)), \
        ("Duplicate include paths found in compiler invocation!\n"
         "Paths: {}\n"
         "Unique: {}".format(include_paths, list(set(include_paths))))


@pytest.mark.tool("visual_studio")
@pytest.mark.skipif(platform.system() != "Windows", reason="Requires MSBuild")
def test_msbuilddeps_dedup_conandeps_structure():
    """Verify dedup target is present in conandeps.props and component .props."""
    mypkg = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import save

        class MultiCompPkg(ConanFile):
            name = "mypkg"
            version = "1.0"
            package_type = "static-library"

            def package(self):
                save(self, os.path.join(self.package_folder, "include", "mypkg.h"), "")
                save(self, os.path.join(self.package_folder, "lib", "core.lib"), "")

            def package_info(self):
                self.cpp_info.components["core"].libs = ["core"]
                self.cpp_info.components["core"].includedirs = ["include"]
                self.cpp_info.components["core"].libdirs = ["lib"]

                self.cpp_info.components["client"].includedirs = ["include"]
                self.cpp_info.components["client"].libdirs = ["lib"]
                self.cpp_info.components["client"].requires = ["core"]
        """)

    consumer = textwrap.dedent("""
        from conan import ConanFile
        class Consumer(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            requires = "mypkg/1.0"
            generators = "MSBuildDeps"
        """)

    client = TestClient()
    client.save({"pkg/conanfile.py": mypkg,
                 "app/conanfile.py": consumer})
    client.run("create pkg")
    client.run("install app")

    conandeps = client.load("app/conandeps.props")
    assert "ConanDeduplicatePaths" in conandeps
    assert "RemoveDuplicates" in conandeps
    assert "ConanDedupTargetDefined" in conandeps

    # Also present in component-level .props
    pkg_props = client.load("app/conan_mypkg.props")
    assert "ConanDeduplicatePaths" in pkg_props

    comp_props = client.load("app/conan_mypkg_core.props")
    assert "ConanDeduplicatePaths" in comp_props
