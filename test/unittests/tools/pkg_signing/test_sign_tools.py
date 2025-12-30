import os

import pytest

from conan.test.utils.tools import temp_folder, save_files

from conan.tools.pkg_signing.plugin import (_create_manifest_content, get_manifest_filepath,
                                            load_manifest, _save_manifest, get_signatures_filepath,
                                            load_signatures, _save_signatures,
                                            _verify_files_checksums)
from conan.errors import ConanException


@pytest.fixture
def pkg_sign_tools():
    main_folder = temp_folder()
    artifacts_folder = os.path.join(main_folder, "af")
    os.mkdir(artifacts_folder)
    signature_folder = os.path.join(main_folder, "sf")
    os.mkdir(signature_folder)
    save_files(artifacts_folder, {"conan_package.tgz": "", "conanmanifest.txt": ""})
    return artifacts_folder, signature_folder


def test_get_manifest_filepath(pkg_sign_tools):
    """Test that get_manifest_filepath returns the correct path for the manifest file."""
    _, signature_folder = pkg_sign_tools
    manifest_path = get_manifest_filepath(signature_folder)
    assert manifest_path == os.path.join(signature_folder, "pkgsign-manifest.json")


def test_create_manifest_content_with_empty_files(pkg_sign_tools):
    """Test that _create_manifest_content correctly creates manifest for empty files."""
    artifacts_folder, _ = pkg_sign_tools
    content = _create_manifest_content(artifacts_folder)

    # Verify structure
    assert "files" in content
    assert isinstance(content["files"], list)
    assert len(content["files"]) == 2

    # Files should be sorted alphabetically
    files = content["files"]
    assert files[0]["file"] == "conan_package.tgz"
    assert files[1]["file"] == "conanmanifest.txt"

    # Empty file SHA256
    empty_file_sha256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert files[0]["sha256"] == empty_file_sha256
    assert files[1]["sha256"] == empty_file_sha256


def test_create_manifest_content_ignores_directories(pkg_sign_tools):
    """Test that _create_manifest_content only includes files, not directories."""
    artifacts_folder, _ = pkg_sign_tools
    # Create a subdirectory
    subdir = os.path.join(artifacts_folder, "subdir")
    os.mkdir(subdir)

    content = _create_manifest_content(artifacts_folder)
    filenames = [f["file"] for f in content["files"]]

    # Should not include the directory
    assert "subdir" not in filenames
    assert len(content["files"]) == 2  # Only the two original files


def test_save_load_manifest(pkg_sign_tools):
    """Test that saving and loading manifest preserves all data correctly."""
    artifacts_folder, signature_folder = pkg_sign_tools
    _save_manifest(artifacts_folder, signature_folder)

    # Verify file exists
    manifest_path = get_manifest_filepath(signature_folder)
    assert os.path.exists(manifest_path)

    # Load and verify content
    manifest = load_manifest(signature_folder)
    assert "files" in manifest
    assert isinstance(manifest["files"], list)
    assert len(manifest["files"]) == 2

    # Verify files are sorted and contain expected data
    filenames = [f["file"] for f in manifest["files"]]
    assert filenames == ["conan_package.tgz", "conanmanifest.txt"]

    # Verify each file entry has required fields
    for file_entry in manifest["files"]:
        assert "file" in file_entry
        assert "sha256" in file_entry
        assert len(file_entry["sha256"]) == 64


def test_get_signatures_filepath(pkg_sign_tools):
    """Test that get_signatures_filepath returns the correct path for the signatures file."""
    _, signature_folder = pkg_sign_tools
    signatures_path = get_signatures_filepath(signature_folder)
    assert signatures_path == os.path.join(signature_folder, "pkgsign-signatures.json")


def test_save_load_signatures(pkg_sign_tools):
    """Test that saving and loading signatures preserves all data correctly."""
    artifacts_folder, signature_folder = pkg_sign_tools
    # Manifest must exist before saving signatures
    _save_manifest(artifacts_folder, signature_folder)

    signatures = [{
        "method": "openssl-dgst",
        "provider": "my-organization",
        "sign_artifacts": {
            "conan_package signature": "conan_package.tgz.sig",
            "conanmanifest signature": "conanmanifest.txt.sig"
        }
    }]
    _save_signatures(signature_folder, signatures)

    # Verify file exists
    assert os.path.exists(get_signatures_filepath(signature_folder))

    # Load and verify content
    loaded = load_signatures(signature_folder)
    assert loaded["manifest"] == "pkgsign-manifest.json"
    assert len(loaded["signatures"]) == 1

    signature = loaded["signatures"][0]
    assert signature["method"] == "openssl-dgst"
    assert signature["provider"] == "my-organization"
    assert signature["sign_artifacts"]["conan_package signature"] == "conan_package.tgz.sig"
    assert signature["sign_artifacts"]["conanmanifest signature"] == "conanmanifest.txt.sig"


def test_save_signatures_with_multiple_signatures(pkg_sign_tools):
    """Test that _save_signatures can handle multiple signature entries."""
    artifacts_folder, signature_folder = pkg_sign_tools
    _save_manifest(artifacts_folder, signature_folder)

    signatures = [
        {
            "method": "gpg",
            "provider": "my-organization",
            "sign_artifacts": {"signature": "pkgsign-manifest.json.gpg"}
        },
        {
            "method": "cosign",
            "provider": "my-organization",
            "sign_artifacts": {"signature": "pkgsign-manifest.json.sig"}
        }
    ]
    _save_signatures(signature_folder, signatures)

    loaded = load_signatures(signature_folder)
    assert len(loaded["signatures"]) == 2
    assert loaded["signatures"][0]["method"] == "gpg"
    assert loaded["signatures"][0]["sign_artifacts"]["signature"] == "pkgsign-manifest.json.gpg"
    assert loaded["signatures"][1]["method"] == "cosign"
    assert loaded["signatures"][1]["sign_artifacts"]["signature"] == "pkgsign-manifest.json.sig"


def test_save_signatures_requires_manifest(pkg_sign_tools):
    """Test that _save_signatures raises an error if manifest doesn't exist."""
    _, signature_folder = pkg_sign_tools

    signatures = [{
        "method": "gpg",
        "provider": "my-organization",
        "sign_artifacts": {"file signature": "file.txt.gpg"}
    }]

    with pytest.raises(AssertionError, match="Manifest file must exist"):
        _save_signatures(signature_folder, signatures)


def test_save_signatures_validates_list_type(pkg_sign_tools):
    """Test that _save_signatures validates signatures is a list."""
    artifacts_folder, signature_folder = pkg_sign_tools
    _save_manifest(artifacts_folder, signature_folder)

    with pytest.raises(AssertionError, match="must return a list"):
        _save_signatures(signature_folder, {"not": "a list"})


def test_save_signatures_validates_required_fields(pkg_sign_tools):
    """Test that _save_signatures validates required signature fields."""
    artifacts_folder, signature_folder = pkg_sign_tools
    _save_manifest(artifacts_folder, signature_folder)

    # Missing method
    with pytest.raises(AssertionError, match="'method' must be set"):
        _save_signatures(signature_folder,
                         [{"provider": "my-organization","sign_artifacts": {}}])

    # Missing provider
    with pytest.raises(AssertionError, match="'provider' must be set"):
        _save_signatures(signature_folder, [{"method": "gpg", "sign_artifacts": {}}])

    # Missing sign_artifacts
    with pytest.raises(AssertionError, match="'sign_artifacts' must be set"):
        _save_signatures(signature_folder,
                         [{"method": "gpg", "provider": "my-organization"}])

    # sign_artifacts not a dict
    with pytest.raises(AssertionError, match="must be a dict"):
        _save_signatures(signature_folder,
                         [{"method": "gpg", "provider": "my-organization",
                                    "sign_artifacts": "not a dict"}])


def test_verify_files_checksums_success(pkg_sign_tools):
    """Test that verify_files_checksums succeeds when all checksums match."""
    artifacts_folder, signature_folder = pkg_sign_tools
    _save_manifest(artifacts_folder, signature_folder)

    files = {
        "conan_package.tgz": os.path.join(artifacts_folder, "conan_package.tgz"),
        "conanmanifest.txt": os.path.join(artifacts_folder, "conanmanifest.txt")
    }
    # Should not raise an exception
    _verify_files_checksums(signature_folder, files)


def test_verify_files_checksums_partial_files(pkg_sign_tools):
    """Test that verify_files_checksums works with a subset of files. This is to test in case that conan_sources.tgz is not present."""
    artifacts_folder, signature_folder = pkg_sign_tools
    _save_manifest(artifacts_folder, signature_folder)

    # Verify only one file
    files = {
        "conanmanifest.txt": os.path.join(artifacts_folder, "conanmanifest.txt")
    }
    # Should not raise an exception
    _verify_files_checksums(signature_folder, files)


def test_verify_files_checksums_mismatch(pkg_sign_tools):
    """Test that verify_files_checksums raises exception when checksums don't match."""
    artifacts_folder, signature_folder = pkg_sign_tools
    _save_manifest(artifacts_folder, signature_folder)

    # Modify file content to cause checksum mismatch
    modified_file = os.path.join(artifacts_folder, "conan_package.tgz")
    with open(modified_file, "w") as f:
        f.write("modified content")

    files = {
        "conan_package.tgz": modified_file,
        "conanmanifest.txt": os.path.join(artifacts_folder, "conanmanifest.txt")
    }

    with pytest.raises(ConanException, match="Checksum mismatch for file conan_package.tgz"):
        _verify_files_checksums(signature_folder, files)


def test_verify_files_checksums_missing_file_in_manifest(pkg_sign_tools):
    """Test that verify_files_checksums handles files not in manifest."""
    artifacts_folder, signature_folder = pkg_sign_tools
    _save_manifest(artifacts_folder, signature_folder)

    # Try to verify a file that doesn't exist in manifest
    new_file = os.path.join(artifacts_folder, "new_file.txt")
    with open(new_file, "w") as f:
        f.write("content")

    files = {"new_file.txt": new_file}

    # Should raise exception because file is not in manifest (expected_checksum is None)
    with pytest.raises(ConanException, match="Checksum mismatch"):
        _verify_files_checksums(signature_folder, files)
