import pytest

from conan.tools.build import check_min_compiler_version
from conan.errors import ConanException, ConanInvalidConfiguration
from conan.test.utils.mocks import MockSettings, ConanFileMock


@pytest.mark.parametrize("compiler,compiler_version,restrictions,should_raise", [
    ("clang", "14", (("clang", "14", "coroutines"), ("gcc", "13", "alignas")), False),
    ("gcc", "13", (("clang", "14", "coroutines"), ("gcc", "13", "alignas")), False),
    ("gcc", "14", (("clang", "14", "coroutines"), ("gcc", "13", "alignas")), False),
    ("Visual Studio", "16", (("Visual Studio", "16", "reason"), ("clang", "14", "coroutines")), False),

    ("clang", "13", (("clang", "14", "coroutines"), ("gcc", "13", "alignas")), True),
    ("gcc", "12", (("clang", "14", "coroutines"), ("gcc", "13", "alignas")), True),
    ("Visual Studio", "15", (("Visual Studio", "16", "reason"), ("clang", "14", "coroutines")), True),

    ("emcc", "1.0", (("gcc", "13", "alignas"),), False),
    (None, "12", (("gcc", "13", "alignas"),), True),
    ("gcc", None, (("gcc", "13", "alignas"),), True),
])
def test_check_min_compiler_version(compiler, compiler_version, restrictions, should_raise):
    settings = MockSettings({"compiler": compiler, "compiler.version": compiler_version})
    conanfile = ConanFileMock(settings)

    if should_raise:
        if compiler is None or compiler_version is None:
            with pytest.raises(ConanException):
                check_min_compiler_version(conanfile, restrictions)
        else:
            with pytest.raises(ConanInvalidConfiguration):
                check_min_compiler_version(conanfile, restrictions)
    else:
        check_min_compiler_version(conanfile, restrictions)
