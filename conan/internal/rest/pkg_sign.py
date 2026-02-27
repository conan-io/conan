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

    # Sort files by filename to ensure consistent order
    for fname in sorted(os.listdir(artifacts_folder)):
        file_path = os.path.join(artifacts_folder, fname)

        if os.path.isfile(file_path):
            entry = {
                "file": fname,
                "sha256": sha256sum(file_path)
            }
            files_list.append(entry)

    save(os.path.join(signature_folder, PKGSIGN_MANIFEST),
         json.dumps({"files": files_list}, indent=2))


def _save_signatures(signature_folder, signatures):
    """
    Saves the content of signatures file in the signature folder
    :param signature_folder: Signature folder path
    :param signatures: dict of {filename: signature_value}
    """
    for signature in signatures:
        for key in ["method", "provider", "sign_artifacts"]:
            if not signature.get(key):
                raise ConanException(f"[Package sign] Signature '{key}' is missing in signature data")
        if not isinstance(signature.get("sign_artifacts"), dict):
            raise ConanException("[Package sign] Signature 'sign_artifacts' must be a dict of "
                                 "{name: filename}")
    content = {
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
        ConanOutput().warning(f"[Package sign] Manifest file '{PKGSIGN_MANIFEST}' does not exist in "
                              f"signature folder '{signature_folder}'. Please update your plugin "
                              f"according to the docs at https://docs.conan.io/2/reference/extensions/package_signing.html"
                              f". Skipping checksum verification!", warn_tag="deprecated")
        return

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
                f"[Package sign] Checksum mismatch for file {filename}: "
                f"expected {expected_checksum}, got {actual_checksum}."
            )
        else:
            ConanOutput().info(f"[Package sign] Checksum verified for file {filename} ({actual_checksum}).")


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
        if isinstance(signatures, list):
            # Save signatures file with the plugin's returned signatures data
            if signatures:
                _save_signatures(metadata_sign, signatures)
        else:
            # Fallback to old behavior (plugin sign() returns None)
            ConanOutput().warning("[Package sign] The signature plugin sign() function must return "
                                  "a list of signature dicts. See the documentation at "
                                  "https://docs.conan.io/2/reference/extensions/package_signing.html",
                                  warn_tag="deprecated")

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

    def verify(self, ref, folder, metadata_folder, files):
        if self._plugin_verify_function is None:
            return
        metadata_sign = os.path.join(metadata_folder, "sign")
        _verify_files_checksums(metadata_sign, files)  # Verify package files checksums before calling the plugin
        self._plugin_verify_function(ref, artifacts_folder=folder, signature_folder=metadata_sign,
                                     files=files)
