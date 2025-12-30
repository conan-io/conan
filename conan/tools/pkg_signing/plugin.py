import copy
import os
import json

from conan.api.output import ConanOutput
from conan.errors import ConanException
from conan.internal.util.files import load, sha256sum, save

# FIXME: Maybe this tools should be placed at conan.api.subapi.cache as they are not recipe tools?

PKGSIGN_MANIFEST = "pkgsign-manifest.json"
PKGSIGN_SIGNATURES = "pkgsign-signatures.json"


def get_manifest_filepath(signature_folder):
    """
    Gets the path of the summary file path
    :param signature_folder: Signature folder path
    :return: Path of the summary file
    """
    return os.path.join(signature_folder, PKGSIGN_MANIFEST)


def load_manifest(signature_folder):
    """
    Loads the summary file from the signature folder
    :param signature_folder: Signature folder path
    :return: Dictionary object with the content of the summary
    """
    return json.loads(load(get_manifest_filepath(signature_folder)))


def _create_manifest_content(artifacts_folder):
    """
    Creates the summary content as a dictionary for manipulation.

    Returns a structure like:
        {
            "files": [
                {"file": "conan_package.tgz", "sha256": "abc123"},
                {"file": "other_file.bin", "sha256": "fff999"},
                ...
            ]
        }
    """
    files_list = []

    for fname in os.listdir(artifacts_folder):
        file_path = os.path.join(artifacts_folder, fname)

        if os.path.isfile(file_path):
            entry = {
                "file": fname,
                "sha256": sha256sum(file_path)
            }
            files_list.append(entry)

    # Sort files by filename to ensure consistent order
    files_list.sort(key=lambda x: x["file"])

    return {"files": files_list}


def _save_manifest(artifacts_folder, signature_folder):
    """
    Saves the content of manifest file in the signature folder
    :param signature_folder: Signature folder path
    """
    content = _create_manifest_content(artifacts_folder)
    save(get_manifest_filepath(signature_folder), json.dumps(content, indent=2))


def get_signatures_filepath(signature_folder):
    """
    Gets the path of the signatures file path
    :param signature_folder: Signature folder path
    :return: Path of the signatures file
    """
    return os.path.join(signature_folder, PKGSIGN_SIGNATURES)


def load_signatures(signature_folder):
    """
    Loads the signatures file pkgsign-signatures.json from the signature folder
    :param signature_folder: Signature folder path
    :return: dict of {filename: signature_value}
    """
    return json.loads(load(get_signatures_filepath(signature_folder)))


def _save_signatures(signature_folder, signatures):
    """
    Saves the content of signatures file in the signature folder
    :param signature_folder: Signature folder path
    :param signatures: dict of {filename: signature_value}
    """
    assert isinstance(signatures, list),\
        "The signature plugin function must return a list of signatures values"
    for signature in signatures:
        assert signature.get("method"), "Signature 'method' must be set"
        assert signature.get("provider"), "Signature 'provider' must be set"
        assert signature.get("sign_artifacts"), "Signature 'sign_artifacts' must be set"
        assert isinstance(signature.get("sign_artifacts"), dict), \
            "'sign_artifacts' must be a dict of {name: signature_filename}"
    assert os.path.isfile(get_manifest_filepath(signature_folder)),\
        "Manifest file must exist before saving signatures"
    content = {
        "manifest": PKGSIGN_MANIFEST,
        "signatures": signatures
    }
    save(get_signatures_filepath(signature_folder), json.dumps(content, indent=2))


def _verify_files_checksums(signature_folder, files):
    """
    Verifies that the files' checksums match those stored in the summary.
    :param signature_folder: Signature folder path
    :param files: dict of {filename: filepath} of files in artifact folder to verify
    """
    if not os.path.isfile(get_manifest_filepath(signature_folder)):
        raise ConanException(f"Manifest file does not exist in signature folder "
                             f"{get_manifest_filepath(signature_folder)}")

    expected_list = load_manifest(signature_folder).get("files", [])
    expected_files = {item["file"]: item["sha256"] for item in expected_list}

    # This is checking that the files of the package exist in the manifest instead of the opposite
    # because some files might be missing such as conan_sources.tgz
    for filename, file_path in files.items():
        expected_checksum = expected_files.get(filename)
        actual_checksum = sha256sum(file_path)

        if actual_checksum != expected_checksum:
            raise ConanException(
                f"Checksum mismatch for file {filename}: "
                f"expected {expected_checksum}, got {actual_checksum}."
            )
        else:
            ConanOutput().info(f"Checksum verified for file {filename} ({actual_checksum}).")
