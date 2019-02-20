import os

from conans.client.graph.graph import RECIPE_CONSUMER, RECIPE_VIRTUAL
from conans.client.cache.remote_registry import Remote
from conans.errors import ConanException
from conans.model.manifest import FileTreeManifest
from conans.model.ref import PackageReference
from conans.paths.simple_paths import SimplePaths


class ManifestManager(object):

    def __init__(self, folder, user_io, cache):
        self._paths = SimplePaths(folder)
        self._user_io = user_io
        self._cache = cache
        self._log = []

    def check_graph(self, graph, verify, interactive):
        if verify and not os.path.exists(self._paths.store):
            raise ConanException("Manifest folder does not exist: %s"
                                 % self._paths.store)
        for node in graph.ordered_iterate():
            if node.recipe in (RECIPE_CONSUMER, RECIPE_VIRTUAL):
                continue
            self._handle_recipe(node, verify, interactive)
            self._handle_package(node, verify, interactive)

    def _handle_recipe(self, node, verify, interactive):
        ref = node.ref
        export = self._cache.export(ref)
        exports_sources_folder = self._cache.export_sources(ref)
        read_manifest = FileTreeManifest.load(export)
        expected_manifest = FileTreeManifest.create(export, exports_sources_folder)
        self._check_not_corrupted(ref, read_manifest, expected_manifest)
        folder = self._paths.export(ref)
        self._handle_folder(folder, ref, read_manifest, interactive, node.remote, verify)

    def _handle_package(self, node, verify, interactive):
        ref = node.ref
        pref = PackageReference(ref, node.package_id)
        package_folder = self._cache.package(pref)
        read_manifest = FileTreeManifest.load(package_folder)
        expected_manifest = FileTreeManifest.create(package_folder)
        self._check_not_corrupted(pref, read_manifest, expected_manifest)
        folder = self._paths.package(pref)
        self._handle_folder(folder, pref, read_manifest, interactive, node.remote, verify)

    def _handle_folder(self, folder, ref, read_manifest, interactive, remote, verify):
        assert(isinstance(remote, Remote) or remote is None)
        remote_name = "local cache" if not remote else "%s:%s" % (remote.name, remote.url)
        if os.path.exists(folder):
            self._handle_manifest(ref, folder, read_manifest, interactive, remote_name, verify)
        else:
            if verify:
                raise ConanException("New manifest '%s' detected.\n"
                                     "Remote: %s\nProject manifest doesn't match installed one"
                                     % (str(ref), remote_name))
            else:
                self._check_accept_install(interactive, ref, remote_name)
                self._log.append("Installed manifest for '%s' from %s"
                                 % (str(ref), remote_name))
                read_manifest.save(folder)

    def _check_accept_install(self, interactive, ref, remote_name):
        if (interactive and
            not self._user_io.request_boolean("Installing %s from %s\n"
                                              "Do you trust it?" % (str(ref), remote_name),
                                              True)):
            raise ConanException("Installation of '%s' rejected!" % str(ref))

    @staticmethod
    def _check_not_corrupted(ref, read_manifest, expected_manifest):
        if read_manifest != expected_manifest:
            raise ConanException("%s local cache package is corrupted: "
                                 "some file hash doesn't match manifest"
                                 % (str(ref)))

    def _handle_manifest(self, ref, folder, read_manifest, interactive, remote_name, verify):
        captured_manifest = FileTreeManifest.load(folder)
        if captured_manifest == read_manifest:
            self._log.append("Manifest for '%s': OK" % str(ref))
        elif verify:
            diff = captured_manifest.difference(read_manifest)
            error_msg = os.linesep.join("Mismatched checksum '%s' (manifest: %s, file: %s)"
                                        % (fname, h1, h2) for fname, (h1, h2) in diff.items())
            raise ConanException("Modified or new manifest '%s' detected.\n"
                                 "Remote: %s\nProject manifest doesn't match installed one\n%s"
                                 % (str(ref), remote_name, error_msg))
        else:
            self._check_accept_install(interactive, ref, remote_name)
            self._log.append("Installed manifest for '%s' from %s"
                             % (str(ref), remote_name))
            read_manifest.save(folder)

    def print_log(self):
        self._user_io.out.success("\nManifests : %s" % self._paths.store)
        for log_entry in self._log:
            self._user_io.out.info(log_entry)
