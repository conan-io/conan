import os
import platform
import textwrap

import pytest

from conan.api.model import PkgReference
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
            package_type = "header-library"

            def package(self):
                save(self, os.path.join(self.package_folder, "include", "mypkg.h"),
                     '#pragma once\\n')

            def package_info(self):
                self.cpp_info.components["core"].includedirs = ["include"]

                self.cpp_info.components["client"].includedirs = ["include"]
                self.cpp_info.components["client"].requires = ["core"]

                self.cpp_info.components["server"].includedirs = ["include"]
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

    client.run("build .")
    pref = PkgReference.loads("mypkg/1.0#f7eaa1b37facb8e95254e77269bcaa5c:"
                              "da39a3ee5e6b4b0d3255bfef95601890afd80709")
    pkg_path = client.get_latest_pkg_layout(pref).package()
    assert str(client.out).count(f"/I{pkg_path}") == 1

    conandeps = client.load("conandeps.props")
    assert "conan_dedup.props" in conandeps
    conanmypkg = client.load("conan_mypkg.props")
    assert "conan_dedup.props" in conanmypkg

    conanmypkg = client.load("conan_mypkg_server.props")
    # FIXME: Why?? Why component files need to dedup paths? they are not expected to be duplicated
    assert "conan_dedup.props" in conanmypkg

    # repeat install with other config
    client.run("build . -s build_type=Debug")
    assert str(client.out).count(f"/I{pkg_path}") == 1

    # It didn't duplicate entries
    conandeps = client.load("conandeps.props")
    assert conandeps.count("conan_dedup.props") == 1
    conanmypkg = client.load("conan_mypkg.props")
    assert conanmypkg.count("conan_dedup.props") == 1


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
            package_type = "header-library"

            def package(self):
                save(self, os.path.join(self.package_folder, "include", "mypkg.h"), "")

            def package_info(self):
                self.cpp_info.components["core"].includedirs = ["include"]

                self.cpp_info.components["client"].includedirs = ["include"]
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

    conan_dedup = client.load("app/conan_dedup.props")
    assert "ConanDeduplicatePaths" in conan_dedup
    assert "RemoveDuplicates" in conan_dedup
    assert "ConanDedupTargetDefined" in conan_dedup
    assert "ConanDedupPropsImported" in conan_dedup

    conandeps = client.load("app/conandeps.props")
    assert "conan_dedup.props" in conandeps
    assert "ConanDedupPropsImported" in conandeps

    # Also imported in component-level .props
    pkg_props = client.load("app/conan_mypkg.props")
    assert "conan_dedup.props" in pkg_props
    assert "ConanDedupPropsImported" in pkg_props

    comp_props = client.load("app/conan_mypkg_core.props")
    assert "conan_dedup.props" in comp_props
    assert "ConanDedupPropsImported" in comp_props
