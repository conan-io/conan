import os
import platform
import textwrap

import pytest

from conan.tools.env.environment import environment_wrap_command
from conans.test.assets.cmake import gen_cmakelists
from conans.test.assets.genconanfile import GenConanfile
from conans.test.assets.sources import gen_function_cpp


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires MSBuild")
def test_transitive_headers_not_public(transitive_libraries):
    c = transitive_libraries
    c.save({"conanfile.py": GenConanfile().with_settings("build_type", "arch")
                                          .with_generator("MSBuildDeps").with_requires("libb/0.1")},
           clean_first=True)

    c.run("install .")
    liba_data = c.load("conan_liba_vars_release_x64.props")
    assert "<ConanlibaIncludeDirectories></ConanlibaIncludeDirectories>" in liba_data
    assert "<ConanlibaLibraryDirectories>$(ConanlibaRootFolder)/lib;</ConanlibaLibraryDirectories>" \
           in liba_data
    assert "<ConanlibaLibraries>liba.lib;</ConanlibaLibraries>" in liba_data


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires MSBuild")
def test_shared_requires_static(transitive_libraries):
    c = transitive_libraries
    c.save({"conanfile.py": GenConanfile().with_settings("build_type", "arch")
           .with_generator("MSBuildDeps").with_requires("libb/0.1")},
           clean_first=True)

    c.run("install . -o libb*:shared=True")
    assert not os.path.exists(os.path.join(c.current_folder, "conan_liba_vars_release_x64.props"))
    libb_data = c.load("conan_libb_release_x64.props")
    # No dependency to liba, it has been skipped as unnecessary
    assert "conan_liba.props" not in libb_data
