import pytest
from unittest.mock import MagicMock

from conan.tools.build import check_min_compiler_version
from conan.tools.build.compiler import get_compiler_executables
from conan.errors import ConanException, ConanInvalidConfiguration
from conan.test.utils.mocks import MockSettings, ConanFileMock


class TestGetCompilerExecutables:
    """Test priority order: conf > buildenv > defaults"""

    @staticmethod
    def _mock_conanfile(conf_compilers=None, buildenv_cc=None, buildenv_cxx=None,
                        compiler=None, compiler_mode=None):
        conanfile = ConanFileMock()
        if conf_compilers:
            conanfile.conf["tools.build:compiler_executables"] = conf_compilers
        if compiler:
            conanfile.settings = MockSettings({
                "compiler": compiler,
                "compiler.mode": compiler_mode
            })
        # Mock buildenv_build
        buildenv_vars = {}
        if buildenv_cc:
            buildenv_vars["CC"] = buildenv_cc
        if buildenv_cxx:
            buildenv_vars["CXX"] = buildenv_cxx
        conanfile.buildenv_build = MagicMock()
        conanfile.buildenv_build.vars.return_value = buildenv_vars
        return conanfile

    @pytest.mark.parametrize("conf,buildenv_cc,buildenv_cxx,compiler,mode,expected_c,expected_cpp", [
        # Only conf defined
        ({"c": "conf-cc", "cpp": "conf-cxx"}, None, None, None, None, "conf-cc", "conf-cxx"),
        # Only buildenv defined
        (None, "env-cc", "env-cxx", None, None, "env-cc", "env-cxx"),
        # Only defaults (intel-cc icx mode)
        (None, None, None, "intel-cc", "icx", "icx", "icpx"),
        # Only defaults (intel-cc classic mode)
        (None, None, None, "intel-cc", "classic", "icc", "icpc"),
        # Only defaults (intel-cc dpcpp mode)
        (None, None, None, "intel-cc", "dpcpp", "icx", "dpcpp"),
        # Only defaults (emcc)
        (None, None, None, "emcc", None, "emcc", "em++"),
        # Conf has priority over buildenv
        ({"c": "conf-cc", "cpp": "conf-cxx"}, "env-cc", "env-cxx", None, None, "conf-cc", "conf-cxx"),
        # Conf has priority over defaults
        ({"c": "conf-cc", "cpp": "conf-cxx"}, None, None, "intel-cc", "icx", "conf-cc", "conf-cxx"),
        # Buildenv has priority over defaults
        (None, "env-cc", "env-cxx", "intel-cc", "icx", "env-cc", "env-cxx"),
        # Partial conf: cpp from conf, c from buildenv
        ({"cpp": "conf-cxx"}, "env-cc", "env-cxx", None, None, "env-cc", "conf-cxx"),
        # Partial conf: c from conf, cpp from buildenv
        ({"c": "conf-cc"}, "env-cc", "env-cxx", None, None, "conf-cc", "env-cxx"),
        # No compilers defined, no defaults applicable
        (None, None, None, "gcc", None, None, None),
    ])
    def test_compiler_executables_priority(self, conf, buildenv_cc, buildenv_cxx,
                                           compiler, mode, expected_c, expected_cpp):
        conanfile = self._mock_conanfile(conf, buildenv_cc, buildenv_cxx, compiler, mode)
        result = get_compiler_executables(conanfile)
        if expected_c is None:
            assert "c" not in result
        else:
            assert result.get("c") == expected_c
        if expected_cpp is None:
            assert "cpp" not in result
        else:
            assert result.get("cpp") == expected_cpp


@pytest.mark.parametrize("compiler,compiler_version,restrictions,should_raise", [
    ("clang", "14", (("clang", "14", "coroutines"), ("gcc", "13", "alignas")), False),
    ("gcc", "13", (("clang", "14", "coroutines"), ("gcc", "13", "alignas")), False),
    ("gcc", "14", (("clang", "14", "coroutines"), ("gcc", "13", "alignas")), False),
    ("msvc", "192", (("msvc", "192", "reason"), ("clang", "14", "coroutines")), False),

    ("clang", "13", (("clang", "14", "coroutines"), ("gcc", "13", "alignas")), True),
    ("gcc", "12", (("clang", "14", "coroutines"), ("gcc", "13", "alignas")), True),
    ("msvc", "191", (("msvc", "192", "reason"), ("clang", "14", "coroutines")), True),

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
