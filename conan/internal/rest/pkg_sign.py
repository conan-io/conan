import os
import json

from conan.api.output import ConanOutput
from conan.errors import ConanException
from conan.internal.cache.conan_reference_layout import METADATA
from conan.internal.cache.home_paths import HomePaths
from conan.internal.loader import load_python_file
from conan.internal.util.files import load, mkdir, save, sha256sum


PKGSIGN_MANIFEST = "pkgsign-manifest.json"
PKGSIGN_SIGNATURES = "pkgsign-signatures.json"


def _save_manifest(artifacts_folder, signature_folder):
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
    save(os.path.join(signature_folder, PKGSIGN_MANIFEST),
         json.dumps({"files": files_list}, indent=2))


def _save_signatures(signature_folder, signatures):
    """
    Saves the content of signatures file in the signature folder
    :param signature_folder: Signature folder path
    :param signatures: dict of {filename: signature_value}
    """
    for signature in signatures:
        assert signature.get("method"), "Signature 'method' must be set"
        assert signature.get("provider"), "Signature 'provider' must be set"
        assert signature.get("sign_artifacts"), "Signature 'sign_artifacts' must be set"
        assert isinstance(signature.get("sign_artifacts"), dict), \
            "'sign_artifacts' must be a dict of {name: signature_filename}"
    assert os.path.isfile(os.path.join(signature_folder, PKGSIGN_MANIFEST)),\
        "Manifest file must exist before saving signatures"
    content = {
        "manifest": PKGSIGN_MANIFEST,
        "signatures": signatures
    }
    save(os.path.join(signature_folder, PKGSIGN_SIGNATURES), json.dumps(content, indent=2))


def _verify_files_checksums(signature_folder, files):
    """
    Verifies that the files' checksums match those stored in the summary.
    :param signature_folder: Signature folder path
    :param files: dict of {filename: filepath} of files in artifact folder to verify
    """
    if not os.path.isfile(os.path.join(signature_folder, PKGSIGN_MANIFEST)):
        raise ConanException(f"Manifest file does not exist in signature folder "
                             f"{os.path.join(signature_folder, PKGSIGN_MANIFEST)}")

    manifest_content = load(os.path.join(signature_folder, PKGSIGN_MANIFEST))
    expected_list = json.loads(manifest_content).get("files", [])
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


class PkgSignaturesPlugin:
    def __init__(self, cache, home_folder):
        self._cache = cache
        signer = HomePaths(home_folder).sign_plugin_path
        if os.path.isfile(signer):
            mod, _ = load_python_file(signer)
            self._plugin_sign_function = getattr(mod, "sign", None)
            self._plugin_verify_function = getattr(mod, "verify", None)
        else:
            self._plugin_sign_function = self._plugin_verify_function = None

    @property
    def is_sign_configured(self):
        return self._plugin_sign_function is not None

    @property
    def is_verify_configured(self):
        return self._plugin_verify_function is not None

    def sign_pkg(self, ref, files, folder):
        metadata_sign = os.path.join(folder, METADATA, "sign")
        mkdir(metadata_sign)
        # Generate the package sign manifest before calling the plugin
        _save_manifest(folder, metadata_sign)
        signatures = self._plugin_sign_function(ref, artifacts_folder=folder,
                                                signature_folder=metadata_sign)
        # Save signatures file with the plugin's returned signatures data
        if not isinstance(signatures, list):
            raise ConanException("The signature plugin function must return"
                                 "a list of signature dicts")
        _save_signatures(metadata_sign, signatures)
        # Add files to package bundle so they get uploaded
        files[f"{METADATA}/sign/{PKGSIGN_MANIFEST}"] = os.path.join(metadata_sign, PKGSIGN_MANIFEST)
        files[f"{METADATA}/sign/{PKGSIGN_SIGNATURES}"] = os.path.join(metadata_sign, PKGSIGN_SIGNATURES)
        for sig in signatures:
            for name, file in sig.get("sign_artifacts", {}).items():
                #TODO: print output?
                files[f"{METADATA}/sign/{file}"] = os.path.join(metadata_sign, file)

    def sign(self, upload_data):
        if not self.is_sign_configured:
            return

        for rref, packages in upload_data.items():
            recipe_bundle = upload_data.recipe_dict(rref)
            if recipe_bundle["upload"]:
                self.sign_pkg(rref, recipe_bundle["files"],
                              self._cache.recipe_layout(rref).download_export())
            for pref in packages:
                pkg_bundle = upload_data.package_dict(pref)
                if pkg_bundle["upload"]:
                    self.sign_pkg(pref, pkg_bundle["files"],
                                  self._cache.pkg_layout(pref).download_package())

    def verify(self, ref, folder, files):
        if not self.is_verify_configured:
            return
        metadata_sign = os.path.join(folder, METADATA, "sign")
        _verify_files_checksums(metadata_sign, files)  # Verify package files checksums before calling the plugin
        self._plugin_verify_function(ref, artifacts_folder=folder, signature_folder=metadata_sign,
                                     files=files)
