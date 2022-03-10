import os
import stat
import tarfile
import time

from conans.cli.conan_app import ConanApp
from conans.cli.output import ConanOutput
from conans.client.source import retrieve_exports_sources
from conans.errors import ConanException, NotFoundException
from conans.paths import (CONAN_MANIFEST, CONANFILE, EXPORT_SOURCES_TGZ_NAME,
                          EXPORT_TGZ_NAME, PACKAGE_TGZ_NAME, CONANINFO)
from conans.util.files import (clean_dirty, is_dirty, gather_files,
                               gzopen_without_timestamps, set_dirty_context_manager)
from conans.util.tracer import log_recipe_upload, log_compressed_files, log_package_upload

UPLOAD_POLICY_FORCE = "force-upload"
UPLOAD_POLICY_SKIP = "skip-upload"


class _RecipeData:
    def __init__(self, ref, prefs=None):
        self.ref = ref
        self.upload = None
        self.force = None
        self.build_always = None
        self.files = None
        self.packages = [_PackageData(p) for p in prefs or []]

    def serialize(self):
        return {
            "ref": repr(self.ref),
            "upload": self.upload,
            "force": self.force,
            "build_always": self.build_always,
            "files": self.files,
            "packages": [r.serialize() for r in self.packages]
        }


class _PackageData:
    def __init__(self, pref):
        self.pref = pref
        self.upload = None
        self.files = None
        self.force = None

    def serialize(self):
        return {
            "pref": repr(self.pref),
            "upload": self.upload,
            "force": self.force,
            "files": self.files
        }


class _UploadData:
    def __init__(self):
        self.recipes = []

    def serialize(self):
        return [r.serialize() for r in self.recipes]

    def add_ref(self, ref):
        self.recipes.append(_RecipeData(ref))

    def add_prefs(self, prefs):
        self.recipes.append(_RecipeData(prefs[0].ref, prefs))


class UploadChecker:
    """
    Check:
        - Performs a package corruption integrity check
    """
    def __init__(self, app):
        self._app = app
        self._output = ConanOutput()

    def check(self, upload_data):
        for recipe in upload_data.recipes:
            for package in recipe.packages:
                self._package_integrity_check(package.pref)

    def _package_integrity_check(self, pref):
        self._output.rewrite_line("Checking package integrity...")

        # short_paths = None is enough if there exist short_paths
        pkg_layout = self._app.cache.pkg_layout(pref)
        read_manifest, expected_manifest = pkg_layout.package_manifests()

        if read_manifest != expected_manifest:
            self._output.writeln("")
            diff = read_manifest.difference(expected_manifest)
            for fname, (h1, h2) in diff.items():
                self._output.warning("Mismatched checksum '%s' (manifest: %s, file: %s)"
                                     % (fname, h1, h2))
            raise ConanException("Cannot upload corrupted package '%s'" % str(pref))
        else:
            self._output.rewrite_line("Package integrity OK!")
        self._output.writeln("")


class UploadUpstreamChecker:

    def __init__(self, app: ConanApp):
        self._app = app
        self._output = ConanOutput()

    def check(self, upload_bundle, remote, force):
        for recipe in upload_bundle.recipes:
            if recipe.upload:
                self._check_upstream_recipe(recipe, remote, force)
                for package in recipe.packages:
                    if package.upload:
                        self._check_upstream_package(package, remote, force)

    def _check_upstream_recipe(self, recipe, remote, force):
        self._output.info("Checking which revisions exist in the remote server")
        ref = recipe.ref
        try:
            assert ref.revision
            # TODO: It is a bit ugly, interface-wise to ask for revisions to check existence
            server_ref = self._app.remote_manager.get_recipe_revision_reference(ref, remote)
            assert server_ref
        except NotFoundException:
            recipe.force = False
        else:
            if force:
                self._output.info("{} already in server, forcing upload".format(ref.repr_notime()))
                recipe.force = True
            else:
                self._output.info("{} already in server, skipping upload".format(ref.repr_notime()))
                recipe.upload = False
                recipe.force = False

    def _check_upstream_package(self, package, remote, force):
        pref = package.pref
        assert (pref.revision is not None), "Cannot upload a package without PREV"
        assert (pref.ref.revision is not None), "Cannot upload a package without RREV"

        try:
            # TODO: It is a bit ugly, interface-wise to ask for revisions to check existence
            server_revisions = self._app.remote_manager.get_package_revision_reference(pref, remote)
            assert server_revisions
        except NotFoundException:
            if package.upload is not False:
                package.upload = True
            package.force = False
        else:
            if force:
                self._output.info("{} already in server, forcing upload".format(pref.repr_notime()))
                package.force = True
            else:
                self._output.info("{} already in server, skipping upload".format(pref.repr_notime()))
                package.upload = False
                package.force = False


class PackagePreparator:
    def __init__(self, app: ConanApp):
        self._app = app
        self._output = ConanOutput()

    def prepare(self, upload_bundle):
        self._output.info("Preparing artifacts to upload")
        for recipe in upload_bundle.recipes:
            layout = self._app.cache.ref_layout(recipe.ref)
            conanfile_path = layout.conanfile()
            conanfile = self._app.loader.load_basic(conanfile_path)

            if recipe.upload:
                self._prepare_recipe(recipe, conanfile, self._app.enabled_remotes)
            if conanfile.build_policy == "always":
                recipe.build_always = True
            else:
                recipe.build_always = False
                for package in recipe.packages:
                    if package.upload:
                        self._prepare_package(package)

    def _prepare_recipe(self, recipe, conanfile, remotes):
        """ do a bunch of things that are necessary before actually executing the upload:
        - retrieve exports_sources to complete the recipe if necessary
        - compress the artifacts in conan_export.tgz and conan_export_sources.tgz
        - check if package is ok to be uploaded
        - check if the remote recipe is newer, raise
        - compare and decide which files need to be uploaded (and deleted from server)
        """
        try:
            ref = recipe.ref
            recipe_layout = self._app.cache.ref_layout(ref)
            retrieve_exports_sources(self._app.remote_manager, recipe_layout, conanfile, ref,
                                     remotes)
            cache_files = self._compress_recipe_files(recipe_layout, ref)
            recipe.files = cache_files
        except Exception as e:
            raise ConanException(f"{recipe.ref} Error while compressing: {e}")

    def _compress_recipe_files(self, layout, ref):
        download_export_folder = layout.download_export()

        for f in (EXPORT_TGZ_NAME, EXPORT_SOURCES_TGZ_NAME):
            tgz_path = os.path.join(download_export_folder, f)
            if is_dirty(tgz_path):
                self._output.warning("%s: Removing %s, marked as dirty" % (str(ref), f))
                os.remove(tgz_path)
                clean_dirty(tgz_path)

        export_folder = layout.export()
        files, symlinked_folders = gather_files(export_folder)
        files.update(symlinked_folders)
        if CONANFILE not in files or CONAN_MANIFEST not in files:
            raise ConanException("Cannot upload corrupted recipe '%s'" % str(ref))
        export_src_folder = layout.export_sources()
        src_files, src_symlinked_folders = gather_files(export_src_folder)
        src_files.update(src_symlinked_folders)

        result = {CONANFILE: files.pop(CONANFILE),
                  CONAN_MANIFEST: files.pop(CONAN_MANIFEST)}

        def add_tgz(tgz_name, tgz_files, msg):
            tgz = os.path.join(download_export_folder, tgz_name)
            if os.path.isfile(tgz):
                result[tgz_name] = tgz
            elif tgz_files:
                if self._output and not self._output.is_terminal:
                    self._output.info(msg)
                compresslevel = self._app.cache.new_config.get("core.gzip:compresslevel",
                                                               check_type=int)
                tgz = compress_files(tgz_files, tgz_name, download_export_folder,
                                     compresslevel=compresslevel)
                result[tgz_name] = tgz

        add_tgz(EXPORT_TGZ_NAME, files, "Compressing recipe...")
        add_tgz(EXPORT_SOURCES_TGZ_NAME, src_files, "Compressing recipe sources...")
        return result

    def _prepare_package(self, package):
        pref = package.pref
        pkg_layout = self._app.cache.pkg_layout(pref)
        if pkg_layout.package_is_dirty():
            raise ConanException("Package %s is corrupted, aborting upload.\n"
                                 "Remove it with 'conan remove %s -p=%s'"
                                 % (pref, pref.ref, pref.package_id))
        cache_files = self._compress_package_files(pkg_layout, pref)
        package.files = cache_files

    def _compress_package_files(self, layout, pref):
        download_pkg_folder = layout.download_package()
        package_tgz = os.path.join(download_pkg_folder, PACKAGE_TGZ_NAME)
        if is_dirty(package_tgz):
            self._output.warning("%s: Removing %s, marked as dirty" % (str(pref), PACKAGE_TGZ_NAME))
            os.remove(package_tgz)
            clean_dirty(package_tgz)

        # Get all the files in that directory
        # existing package, will use short paths if defined
        package_folder = layout.package()
        files, symlinked_folders = gather_files(package_folder)
        files.update(symlinked_folders)

        if CONANINFO not in files or CONAN_MANIFEST not in files:
            raise ConanException("Cannot upload corrupted package '%s'" % str(pref))

        if not os.path.isfile(package_tgz):
            if self._output and not self._output.is_terminal:
                self._output.info("Compressing package...")
            tgz_files = {f: path for f, path in files.items() if
                         f not in [CONANINFO, CONAN_MANIFEST]}
            compresslevel = self._app.cache.new_config.get("core.gzip:compresslevel", check_type=int)
            tgz_path = compress_files(tgz_files, PACKAGE_TGZ_NAME, download_pkg_folder,
                                      compresslevel=compresslevel)
            assert tgz_path == package_tgz
            assert os.path.exists(package_tgz)

        return {PACKAGE_TGZ_NAME: package_tgz,
                CONANINFO: files[CONANINFO],
                CONAN_MANIFEST: files[CONAN_MANIFEST]}


class UploadExecutor:
    def __init__(self, app: ConanApp):
        self._app = app
        self._output = ConanOutput()

    def upload(self, upload_data, remote):

        if upload_data.any_upload:
            self._output.info("Uploading artifacts")
        for recipe in upload_data.recipes:
            if recipe.upload:
                self.upload_recipe(recipe, remote)
            if recipe.build_always and recipe.packages:
                # TODO: Maybe do not raise? Allow it with --force?
                raise ConanException("Conanfile '%s' has build_policy='always', "
                                     "no packages can be uploaded" % str(recipe.ref))
            for package in recipe.packages:
                if package.upload:
                    self.upload_package(package, remote)

    def _recipe_files_to_upload(self, ref, files, remote, force):
        if not force:
            return files, set()
        # only check difference if it is a force upload
        remote_snapshot = self._app.remote_manager.get_recipe_snapshot(ref, remote)
        if not remote_snapshot:
            return files, set()

        deleted = set(remote_snapshot).difference(files)
        return files, deleted

    def upload_recipe(self, recipe, remote):
        self._output.info(f"Uploading {recipe.ref}")
        t1 = time.time()
        ref = recipe.ref
        cache_files = recipe.files
        force = recipe.force
        files_to_upload, deleted = self._recipe_files_to_upload(ref, cache_files, remote, force)

        ref_layout = self._app.cache.ref_layout(ref)
        conanfile_path = ref_layout.conanfile()
        self._app.hook_manager.execute("pre_upload_recipe", conanfile_path=conanfile_path,
                                       reference=ref, remote=remote)

        upload_ref = ref
        self._app.remote_manager.upload_recipe(upload_ref, files_to_upload, deleted, remote)

        duration = time.time() - t1
        log_recipe_upload(ref, duration, cache_files, remote.name)
        self._app.hook_manager.execute("post_upload_recipe", conanfile_path=conanfile_path,
                                       reference=ref, remote=remote)
        return ref

    def upload_package(self, package, remote):
        self._output.info(f"Uploading {package.pref.repr_reduced()}")
        pref = package.pref
        cache_files = package.files
        assert (pref.revision is not None), "Cannot upload a package without PREV"
        assert (pref.ref.revision is not None), "Cannot upload a package without RREV"

        ref_layout = self._app.cache.ref_layout(pref.ref)
        conanfile_path = ref_layout.conanfile()
        self._app.hook_manager.execute("pre_upload_package", conanfile_path=conanfile_path,
                                       reference=pref.ref,
                                       package_id=pref.package_id,
                                       remote=remote)
        t1 = time.time()
        self._app.remote_manager.upload_package(pref, cache_files, remote)
        duration = time.time() - t1
        log_package_upload(pref, duration, cache_files, remote)
        self._app.hook_manager.execute("post_upload_package", conanfile_path=conanfile_path,
                                       reference=pref.ref, package_id=pref.package_id, remote=remote)


def compress_files(files, name, dest_dir, compresslevel=None, ref=None):
    t1 = time.time()
    # FIXME, better write to disk sequentially and not keep tgz contents in memory
    tgz_path = os.path.join(dest_dir, name)
    if name in (PACKAGE_TGZ_NAME, EXPORT_SOURCES_TGZ_NAME) and len(files) > 100:
        ref_name = f"{ref}:" or ""
        ConanOutput().info(f"Compressing {ref_name}{name}")
    with set_dirty_context_manager(tgz_path), open(tgz_path, "wb") as tgz_handle:
        tgz = gzopen_without_timestamps(name, mode="w", fileobj=tgz_handle,
                                        compresslevel=compresslevel)
        mask = ~(stat.S_IWOTH | stat.S_IWGRP)
        for filename, abs_path in sorted(files.items()):
            info = tarfile.TarInfo(name=filename)
            info.size = os.stat(abs_path).st_size
            info.mode = os.stat(abs_path).st_mode & mask
            if os.path.islink(abs_path):
                info.type = tarfile.SYMTYPE
                info.size = 0  # A symlink shouldn't have size
                info.linkname = os.readlink(abs_path)  # @UndefinedVariable
                tgz.addfile(tarinfo=info)
            else:
                with open(abs_path, 'rb') as file_handler:
                    tgz.addfile(tarinfo=info, fileobj=file_handler)
        tgz.close()

    duration = time.time() - t1
    log_compressed_files(files, duration, tgz_path)

    return tgz_path
