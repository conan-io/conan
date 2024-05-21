import os
import platform

import pytest

from conan.test.assets.genconanfile import GenConanfile


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires MSBuild")
def test_transitive_headers_not_public(transitive_libraries):
    c = transitive_libraries
    c.save({"conanfile.py": GenConanfile().with_settings("build_type", "arch")
                                          .with_generator("MSBuildDeps").with_requires("engine/1.0")},
           clean_first=True)

    c.run("install .")
    matrix_data = c.load("conan_matrix_vars_release_x64.props")
    assert "<ConanmatrixIncludeDirectories></ConanmatrixIncludeDirectories>" in matrix_data
    assert "<ConanmatrixLibraryDirectories>$(ConanmatrixRootFolder)/lib;" \
           "</ConanmatrixLibraryDirectories>" in matrix_data
    assert "<ConanmatrixLibraries>matrix.lib;</ConanmatrixLibraries>" in matrix_data


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires MSBuild")
def test_shared_requires_static(transitive_libraries):
    c = transitive_libraries
    c.save({"conanfile.py": GenConanfile().with_settings("build_type", "arch")
           .with_generator("MSBuildDeps").with_requires("engine/1.0")},
           clean_first=True)

    c.run("install . -o engine*:shared=True")
    assert not os.path.exists(os.path.join(c.current_folder, "conan_matrix_vars_release_x64.props"))
    engine_data = c.load("conan_engine_release_x64.props")
    # No dependency to matrix, it has been skipped as unnecessary
    assert "conan_matrix.props" not in engine_data
