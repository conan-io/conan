import json
import os

import pytest

from conan.test.utils.tools import temp_folder, save_files, load

from conan.internal.rest.pkg_sign import _save_manifest, _save_signatures, _verify_files_checksums
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


def test_save_manifest_content_with_empty_files(pkg_sign_tools):
    """Test that _create_manifest_content correctly creates manifest for empty files."""
    artifacts_folder, signature_folder = pkg_sign_tools
    _save_manifest(artifacts_folder, signature_folder)
    content = json.loads(load(os.path.join(signature_folder, "pkgsign-manifest.json")))

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
    """Test that _save_manifest creates a json file that only includes files, not directories."""
    artifacts_folder, signature_folder = pkg_sign_tools
    # Create a subdirectory
    subdir = os.path.join(artifacts_folder, "subdir")
    os.mkdir(subdir)

    _save_manifest(artifacts_folder, signature_folder)
    content = json.loads(load(os.path.join(signature_folder, "pkgsign-manifest.json")))
    filenames = [f["file"] for f in content["files"]]

    # Should not include the directory
    assert "subdir" not in filenames
    assert len(content["files"]) == 2  # Only the two original files


def test_save_load_manifest(pkg_sign_tools):
    """Test that saving and loading manifest preserves all data correctly."""
    artifacts_folder, signature_folder = pkg_sign_tools
    _save_manifest(artifacts_folder, signature_folder)

    # Verify file exists
    manifest_path = os.path.join(signature_folder, "pkgsign-manifest.json")
    assert os.path.isfile(manifest_path)

    # Load and verify content
    manifest = json.loads(load(manifest_path))
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


def test_save_load_signatures(pkg_sign_tools):
    """Test that saving and loading signatures preserves all data correctly."""
    artifacts_folder, signature_folder = pkg_sign_tools
    # Manifest must exist before saving signatures
    _save_manifest(artifacts_folder, signature_folder)

    signatures = [{
        "method": "openssl-dgst",
        "provider": "my-organization",
        "sign_artifacts": {
            "manifest": "pkgsign-manifest.json",
            "conan_package.tgz": "conan_package.tgz.sig",
            "conanmanifest.txt": "conanmanifest.txt.sig"
        }
    }]
    _save_signatures(signature_folder, signatures)

    # Verify file exists
    signatures_path = os.path.join(signature_folder, "pkgsign-signatures.json")
    assert os.path.isfile(signatures_path)

    # Load and verify content
    loaded = json.loads(load(signatures_path))
    assert len(loaded["signatures"]) == 1

    signature = loaded["signatures"][0]
    assert signature["method"] == "openssl-dgst"
    assert signature["provider"] == "my-organization"
    assert signature["sign_artifacts"]["manifest"] == "pkgsign-manifest.json"
    assert signature["sign_artifacts"]["conan_package.tgz"] == "conan_package.tgz.sig"
    assert signature["sign_artifacts"]["conanmanifest.txt"] == "conanmanifest.txt.sig"


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

    signatures_path = os.path.join(signature_folder, "pkgsign-signatures.json")
    loaded = json.loads(load(signatures_path))
    assert len(loaded["signatures"]) == 2
    assert loaded["signatures"][0]["method"] == "gpg"
    assert loaded["signatures"][0]["sign_artifacts"]["signature"] == "pkgsign-manifest.json.gpg"
    assert loaded["signatures"][1]["method"] == "cosign"
    assert loaded["signatures"][1]["sign_artifacts"]["signature"] == "pkgsign-manifest.json.sig"


def test_save_signatures_validates_required_fields(pkg_sign_tools):
    """Test that _save_signatures validates required signature fields."""
    artifacts_folder, signature_folder = pkg_sign_tools
    _save_manifest(artifacts_folder, signature_folder)

    # Missing method
    with pytest.raises(ConanException, match="'method' is missing in signature data"):
        _save_signatures(signature_folder,
                         [{"provider": "my-organization","sign_artifacts": {}}])

    # Missing provider
    with pytest.raises(ConanException, match="'provider' is missing in signature data"):
        _save_signatures(signature_folder, [{"method": "gpg", "sign_artifacts": {}}])

    # Missing sign_artifacts
    with pytest.raises(ConanException, match="'sign_artifacts' is missing in signature data"):
        _save_signatures(signature_folder,
                         [{"method": "gpg", "provider": "my-organization"}])

    # sign_artifacts not a dict
    with pytest.raises(ConanException, match="'sign_artifacts' must be a dict"):
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
