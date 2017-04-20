import os
from conans.paths import SimplePaths
from conans.model.manifest import FileTreeManifest
from conans.util.files import load, save
from conans.errors import ConanException


class ManifestManager(object):

    def __init__(self, folder, user_io, client_cache, verify=False, interactive=False):
        if verify and not os.path.exists(folder):
            raise ConanException("Manifest folder does not exist: %s" % folder)
        self._paths = SimplePaths(folder)
        self._user_io = user_io
        self._client_cache = client_cache
        self._verify = verify
        self._interactive = interactive
        self._log = []

    def print_log(self):
        self._user_io.out.success("\nManifests")
        for log_entry in self._log:
            self._user_io.out.info(log_entry)

    def _handle_add(self, reference, remote, manifest, path):
        # query the user for approval
        if self._interactive:
            ok = self._user_io.request_boolean("Installing %s from %s\n"
                                               "Do you trust it?" % (str(reference), remote),
                                               True)
        else:
            ok = True

        if ok:
            save(path, str(manifest))
            self._log.append("Installed manifest for '%s' from %s" % (str(reference), remote))
        else:
            raise ConanException("Installation of '%s' rejected!" % str(reference))

    def _check(self, reference, manifest, remote, path):
        if os.path.exists(path):
            existing_manifest = FileTreeManifest.loads(load(path))
            if existing_manifest == manifest:
                self._log.append("Manifest for '%s': OK" % str(reference))
                return

        if self._verify:
            diff = existing_manifest.difference(manifest)
            error_msg = os.linesep.join("Mismatched checksum '%s' (manifest: %s, file: %s)"
                                        % (fname, h1, h2) for fname, (h1, h2) in diff.items())
            raise ConanException("Modified or new manifest '%s' detected.\n"
                                 "Remote: %s\nProject manifest doesn't match installed one\n%s"
                                 % (str(reference), remote, error_msg))

        self._handle_add(reference, remote, manifest, path)

    def _match_manifests(self, read_manifest, expected_manifest, reference):
        if read_manifest is None or read_manifest != expected_manifest:
            raise ConanException("%s local cache package is corrupted: "
                                 "some file hash doesn't match manifest"
                                 % (str(reference)))

    def check_recipe(self, conan_reference, remote):
        manifests = self._client_cache.conan_manifests(conan_reference)
        read_manifest, expected_manifest = manifests
        remote = "local cache" if not remote else "%s:%s" % (remote.name, remote.url)
        self._match_manifests(read_manifest, expected_manifest, conan_reference)

        path = self._paths.digestfile_conanfile(conan_reference)
        self._check(conan_reference, read_manifest, remote, path)

    def check_package(self, package_reference, remote):
        manifests = self._client_cache.package_manifests(package_reference)
        read_manifest, expected_manifest = manifests
        remote = "local cache" if not remote else "%s:%s" % (remote.name, remote.url)
        self._match_manifests(read_manifest, expected_manifest, package_reference)

        path = self._paths.digestfile_package(package_reference, short_paths=None)
        self._check(package_reference, read_manifest, remote, path)
