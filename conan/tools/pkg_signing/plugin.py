import copy
import os
import json

from conan.internal.util.files import sha256sum
from conan.tools.files import load, save

# FIXME: Maybe this tools should be placed at conan.api.cache, as they are not recipe tools

SIGN_SUMMARY_CONTENT = {
    "provider": None,
    "method": None,
    "files": {}
}

SIGN_SUMMARY_FILENAME = "sign-summary.json"


def get_summary_file_path(signature_folder):
    """"
    Gets the path of the summary file path
    @param signature_folder: Signature folder path
    @return: Path of the summary file
    """
    return os.path.join(signature_folder, SIGN_SUMMARY_FILENAME)


def load_summary(signature_folder):
    """"
    Loads the summary file from the signature folder
    @param signature_folder: Signature folder path
    @return: Dictionary object with the content of the summary
    """
    return json.loads(load(None, get_summary_file_path(signature_folder)))


def is_pkg_signed(signature_folder):
    """"
    Indicates if the package is signed or not
    @param signature_folder: Signature folder path
    @return: True if the package is signed (the summary file exists and has content)
    """
    try:
        c = load_summary(signature_folder)
    except FileNotFoundError:
        return False
    return bool(c.get("provider") and c.get("method"))


def create_summary_content(artifacts_folder):
    """
    Creates the summary content as a dictionary for manipulation
    @param artifacts_folder: Artifacts folder path
    @return: Dictionary with the summary content
    """
    checksums = {}
    for fname in os.listdir(artifacts_folder):
        file_path = os.path.join(artifacts_folder, fname)
        if os.path.isfile(file_path):
            sha256 = sha256sum(file_path)
            checksums[fname] = sha256
    assert checksums, f"Summary file content cannot be created: No files found in {artifacts_folder}"
    sorted_checksums = dict(sorted(checksums.items()))
    content = copy.deepcopy(SIGN_SUMMARY_CONTENT)
    content["files"] = sorted_checksums
    return content


def save_summary(signature_folder, content):
    """
    Saves the content of the summary to the signature folder using SIGN_SUMMARY_FILENAME as the
    file name
    @param signature_folder: Signature folder path
    @param content: Content of the summary file
    """
    assert content.get("provider")
    assert content.get("method")
    save(None, get_summary_file_path(signature_folder), json.dumps(content))
