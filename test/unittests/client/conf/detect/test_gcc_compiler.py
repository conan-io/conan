
import mock
import pytest

from conan.internal.api.detect.detect_api import detect_gcc_compiler

@pytest.mark.parametrize("version", ["10", "4.2", '7', "8.12"])
def test_detect_gcc_10(version):
    with mock.patch("platform.system", return_value="Linux"):
        with mock.patch("conan.internal.api.detect.detect_api.detect_runner", return_value=(0, version)):
            compiler, installed_version, compiler_exe = detect_gcc_compiler()
    assert compiler == 'gcc'
    assert installed_version == version
    assert compiler_exe == 'gcc'
