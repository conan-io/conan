import os

import patch_ng
import pytest

from conan.tools.files import patch, apply_conandata_patches
from conans.errors import ConanException
from conan.test.utils.mocks import ConanFileMock, RedirectedTestOutput
from conan.test.utils.tools import redirect_output


class MockPatchset:
    filename = None
    string = None
    apply_args = None

    def apply(self, root, strip, fuzz):
        self.apply_args = (root, strip, fuzz)
        return True


@pytest.fixture
def mock_patch_ng(monkeypatch):
    mock = MockPatchset()

    def mock_fromfile(filename):
        mock.filename = filename
        return mock

    def mock_fromstring(string):
        mock.string = string
        return mock

    monkeypatch.setattr(patch_ng, "fromfile", mock_fromfile)
    monkeypatch.setattr(patch_ng, "fromstring", mock_fromstring)
    return mock


def test_single_patch_file(mock_patch_ng):
    conanfile = ConanFileMock()
    conanfile.folders.set_base_source("/my_source")
    conanfile.folders.set_base_export_sources("/my_source")
    conanfile.display_name = 'mocked/ref'
    patch(conanfile, patch_file='patch-file')
    assert mock_patch_ng.filename.replace('\\', '/') == '/my_source/patch-file'
    assert mock_patch_ng.string is None
    assert mock_patch_ng.apply_args[0].replace('\\', '/') == '/my_source'
    assert mock_patch_ng.apply_args[1] == 0
    assert mock_patch_ng.apply_args[2] is False

def test_single_patch_file_from_forced_build(mock_patch_ng):
    conanfile = ConanFileMock()
    conanfile.folders.set_base_source("/my_source")
    conanfile.folders.set_base_export_sources("/my_source")
    conanfile.display_name = 'mocked/ref'
    patch(conanfile, patch_file='/my_build/patch-file')
    assert mock_patch_ng.filename == '/my_build/patch-file'
    assert mock_patch_ng.string is None
    assert mock_patch_ng.apply_args[0].replace('\\', '/') == '/my_source'
    assert mock_patch_ng.apply_args[1] == 0
    assert mock_patch_ng.apply_args[2] is False


def test_base_path(mock_patch_ng):
    conanfile = ConanFileMock()
    conanfile.folders.set_base_source("my_source")
    conanfile.folders.set_base_export_sources("my_source")
    conanfile.folders.source = "src"  # This not applies to find the patch file but for applying it
    conanfile.display_name = 'mocked/ref'
    patch(conanfile, patch_file='patch-file', base_path="subfolder")
    assert mock_patch_ng.filename.replace('\\', '/') == 'my_source/patch-file'
    assert mock_patch_ng.string is None
    assert mock_patch_ng.apply_args == (os.path.join("my_source", "src", "subfolder"), 0, False)


def test_apply_in_build_from_patch_in_source(mock_patch_ng):
    conanfile = ConanFileMock()
    conanfile.folders.set_base_source("/my_source")
    conanfile.folders.set_base_export_sources("/my_source")
    conanfile.display_name = 'mocked/ref'
    patch(conanfile, patch_file='patch-file', base_path="/my_build/subfolder")
    assert mock_patch_ng.filename.replace('\\', '/') == '/my_source/patch-file'
    assert mock_patch_ng.string is None
    assert mock_patch_ng.apply_args[0] == os.path.join("/my_build", "subfolder").replace('\\', '/')
    assert mock_patch_ng.apply_args[1] == 0
    assert mock_patch_ng.apply_args[2] is False


def test_single_patch_string(mock_patch_ng):
    conanfile = ConanFileMock()
    conanfile.folders.set_base_source("my_folder")
    conanfile.folders.set_base_export_sources("my_folder")
    conanfile.display_name = 'mocked/ref'
    output = RedirectedTestOutput()
    with redirect_output(output):
        patch(conanfile, patch_string='patch_string')
    assert mock_patch_ng.string == b'patch_string'
    assert mock_patch_ng.filename is None
    assert mock_patch_ng.apply_args == ("my_folder", 0, False)


def test_single_patch_arguments(mock_patch_ng):
    conanfile = ConanFileMock()
    conanfile.display_name = 'mocked/ref'
    conanfile.folders.set_base_source("/path/to/sources")
    conanfile.folders.set_base_export_sources("/path/to/sources")
    patch(conanfile, patch_file='patch-file', strip=23, fuzz=True)
    assert mock_patch_ng.filename.replace('\\', '/') == '/path/to/sources/patch-file'
    assert mock_patch_ng.apply_args[0].replace('\\', '/') == "/path/to/sources"
    assert mock_patch_ng.apply_args[1] == 23
    assert mock_patch_ng.apply_args[2] is True


def test_single_patch_type(mock_patch_ng):
    output = RedirectedTestOutput()
    with redirect_output(output):
        conanfile = ConanFileMock()
        conanfile.display_name = 'mocked/ref'
        patch(conanfile, patch_file='patch-file', patch_type='patch_type')
    assert 'mocked/ref: Apply patch (patch_type)\n' == output.getvalue()


def test_single_patch_description(mock_patch_ng):
    output = RedirectedTestOutput()
    with redirect_output(output):
        conanfile = ConanFileMock()
        conanfile.display_name = 'mocked/ref'
        patch(conanfile, patch_file='patch-file', patch_description='patch_description')
    assert 'mocked/ref: Apply patch (file): patch_description\n' == output.getvalue()


def test_single_patch_extra_fields(mock_patch_ng):
    output = RedirectedTestOutput()
    with redirect_output(output):
        conanfile = ConanFileMock()
        conanfile.display_name = 'mocked/ref'
        patch(conanfile, patch_file='patch-file', patch_type='patch_type',
              patch_description='patch_description')
    assert 'mocked/ref: Apply patch (patch_type): patch_description\n' == output.getvalue()


def test_single_no_patchset(monkeypatch):
    with pytest.raises(ConanException) as excinfo:
        monkeypatch.setattr(patch_ng, "fromfile", lambda _: None)

        conanfile = ConanFileMock()
        conanfile.display_name = 'mocked/ref'
        patch(conanfile, patch_file='patch-file-failed')
    assert 'Failed to parse patch: patch-file-failed' == str(excinfo.value)


def test_single_apply_fail(monkeypatch):
    class MockedApply:
        def apply(self, *args, **kwargs):
            return False

    monkeypatch.setattr(patch_ng, "fromfile", lambda _: MockedApply())

    conanfile = ConanFileMock()
    conanfile.display_name = 'mocked/ref'
    with pytest.raises(ConanException) as excinfo:
        patch(conanfile, patch_file='patch-file-failed')
    assert 'Failed to apply patch: patch-file-failed' == str(excinfo.value)


def test_multiple_no_version(mock_patch_ng):
    output = RedirectedTestOutput()
    with redirect_output(output):
        conanfile = ConanFileMock()
        conanfile.display_name = 'mocked/ref'
        conanfile.conan_data = {'patches': [
            {'patch_file': 'patches/0001-buildflatbuffers-cmake.patch',
             'base_path': 'source_subfolder', },
            {'patch_file': 'patches/0002-implicit-copy-constructor.patch',
             'base_path': 'source_subfolder',
             'patch_type': 'backport',
             'patch_source': 'https://github.com/google/flatbuffers/pull/5650',
             'patch_description': 'Needed to build with modern clang compilers.'}
        ]}
        apply_conandata_patches(conanfile)
    assert 'mocked/ref: Apply patch (file): patches/0001-buildflatbuffers-cmake.patch\n' \
           in output.getvalue()
    assert 'mocked/ref: Apply patch (backport): Needed to build with modern clang compilers.\n' \
           in output.getvalue()


def test_patch_user(mock_patch_ng):
    output = RedirectedTestOutput()
    with redirect_output(output):
        conanfile = ConanFileMock()
        conanfile.display_name = 'mocked/ref'
        conanfile.conan_data = {'patches': [
            {'patch_user': 'some replace command, the user will handle',
             'myuserthings': 'other things', },
        ]}
        apply_conandata_patches(conanfile)
        # it doesn't do anything, but it doesn't crash


def test_multiple_with_version(mock_patch_ng):
    output = RedirectedTestOutput()
    with redirect_output(output):
        conanfile = ConanFileMock()
        conanfile.display_name = 'mocked/ref'
        conandata_contents = {'patches': {
            "1.11.0": [
                {'patch_file': 'patches/0001-buildflatbuffers-cmake.patch',
                 'base_path': 'source_subfolder', },
                {'patch_file': 'patches/0002-implicit-copy-constructor.patch',
                 'base_path': 'source_subfolder',
                 'patch_type': 'backport',
                 'patch_source': 'https://github.com/google/flatbuffers/pull/5650',
                 'patch_description': 'Needed to build with modern clang compilers.'}
            ],
            "1.12.0": [
                {'patch_file': 'patches/0001-buildflatbuffers-cmake.patch',
                 'base_path': 'source_subfolder', },
            ]}}

        conanfile.conan_data = conandata_contents.copy()

        with pytest.raises(AssertionError) as excinfo:
            apply_conandata_patches(conanfile)
        assert 'Can only be applied if conanfile.version is already defined' == str(excinfo.value)

        conanfile.version = "1.2.11"

        apply_conandata_patches(conanfile)
        assert len(str(output.getvalue())) == 0

        conanfile.version = "1.11.0"
        apply_conandata_patches(conanfile)
        assert 'mocked/ref: Apply patch (file): patches/0001-buildflatbuffers-cmake.patch\n' \
               in output.getvalue()
        assert 'mocked/ref: Apply patch (backport): Needed to build with modern clang compilers.\n' \
               in output.getvalue()

        # Ensure the function is not mutating the `conan_data` structure
        assert conanfile.conan_data == conandata_contents
