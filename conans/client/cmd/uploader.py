import os
import shutil
import time

from conan.internal.conan_app import ConanApp
from conan.api.output import ConanOutput
from conans.client.source import retrieve_exports_sources
from conans.errors import ConanException, NotFoundException
from conans.paths import (CONAN_MANIFEST, CONANFILE, EXPORT_SOURCES_TGZ_NAME,
                          EXPORT_TGZ_NAME, PACKAGE_TGZ_NAME, CONANINFO)
from conans.util.files import (clean_dirty, is_dirty, gather_files,
                               gzopen_without_timestamps, set_dirty_context_manager, mkdir)

UPLOAD_POLICY_FORCE = "force-upload"
UPLOAD_POLICY_SKIP = "skip-upload"


class UploadUpstreamChecker:
    """ decides if something needs to be uploaded or force-uploaded checking if that exact
    revision already exists in the remote server, or if the --force parameter is forcing the upload
    This is completely irrespective of the actual package contents, it only uses the local
    computed revision and the remote one
    """
    def __init__(self, app: ConanApp):
        self._app = app
        self._output = ConanOutput()

    def check(self, upload_bundle, remote, force):
        for ref, recipe_bundle in upload_bundle.refs():
            self._check_upstream_recipe(ref, recipe_bundle, remote, force)
            for pref, prev_bundle in upload_bundle.prefs(ref, recipe_bundle):
                self._check_upstream_package(pref, prev_bundle, remote, force)

    def _check_upstream_recipe(self, ref, ref_bundle, remote, force):
        self._output.info("Checking which revisions exist in the remote server")
        try:
            assert ref.revision
            # TODO: It is a bit ugly, interface-wise to ask for revisions to check existence
            server_ref = self._app.remote_manager.get_recipe_revision_reference(ref, remote)
            assert server_ref  # If successful (not raising NotFoundException), this will exist
        except NotFoundException:
            ref_bundle["force_upload"] = False
            ref_bundle["upload"] = True
        else:
            if force:
                self._output.info("Recipe '{}' already in server, forcing upload".format(ref.repr_notime()))
                ref_bundle["force_upload"] = True
                ref_bundle["upload"] = True
            else:
                self._output.info("Recipe '{}' already in server, skipping upload".format(ref.repr_notime()))
                ref_bundle["upload"] = False
                ref_bundle["force_upload"] = False

    def _check_upstream_package(self, pref, prev_bundle, remote, force):
        assert (pref.revision is not None), "Cannot upload a package without PREV"
        assert (pref.ref.revision is not None), "Cannot upload a package without RREV"

        try:
            # TODO: It is a bit ugly, interface-wise to ask for revisions to check existence
            server_revisions = self._app.remote_manager.get_package_revision_reference(pref, remote)
            assert server_revisions
        except NotFoundException:
            prev_bundle["force_upload"] = False
            prev_bundle["upload"] = True
        else:
            if force:
                self._output.info("Package '{}' already in server, forcing upload".format(pref.repr_notime()))
                prev_bundle["force_upload"] = True
                prev_bundle["upload"] = True
            else:
                self._output.info("Package '{}' already in server, skipping upload".format(pref.repr_notime()))
                prev_bundle["force_upload"] = False
                prev_bundle["upload"] = False


class PackagePreparator:
    def __init__(self, app: ConanApp):
        self._app = app
        self._output = ConanOutput()

    def prepare(self, upload_bundle, enabled_remotes):
        self._output.info("Preparing artifacts to upload")
        for ref, bundle in upload_bundle.refs():
            layout = self._app.cache.ref_layout(ref)
            conanfile_path = layout.conanfile()
            conanfile = self._app.loader.load_basic(conanfile_path)

            if bundle.get("upload"):
                self._prepare_recipe(ref, bundle, conanfile, enabled_remotes)
            for pref, prev_bundle in upload_bundle.prefs(ref, bundle):
                if prev_bundle.get("upload"):
                    self._prepare_package(pref, prev_bundle)

    def _prepare_recipe(self, ref, ref_bundle, conanfile, remotes):
        """ do a bunch of things that are necessary before actually executing the upload:
        - retrieve exports_sources to complete the recipe if necessary
        - compress the artifacts in conan_export.tgz and conan_export_sources.tgz
        """
        try:
            recipe_layout = self._app.cache.ref_layout(ref)
            retrieve_exports_sources(self._app.remote_manager, recipe_layout, conanfile, ref,
                                     remotes)
            cache_files = self._compress_recipe_files(recipe_layout, ref)
            ref_bundle["files"] = cache_files
        except Exception as e:
            raise ConanException(f"{ref} Error while compressing: {e}")

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

        # We do a copy of conanfile and conanmanifest to the download_export_folder
        # so it is identical as when it is downloaded, and all files are from the same location
        # to be uploaded
        mkdir(download_export_folder)
        shutil.copy2(os.path.join(export_folder, CONANFILE),
                     os.path.join(download_export_folder, CONANFILE))
        shutil.copy2(os.path.join(export_folder, CONAN_MANIFEST),
                     os.path.join(download_export_folder, CONAN_MANIFEST))
        result = {CONANFILE: os.path.join(download_export_folder, CONANFILE),
                  CONAN_MANIFEST: os.path.join(download_export_folder, CONAN_MANIFEST)}
        # Files NOT included in the tgz
        files.pop(CONANFILE)
        files.pop(CONAN_MANIFEST)

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

    def _prepare_package(self, pref, prev_bundle):
        pkg_layout = self._app.cache.pkg_layout(pref)
        if pkg_layout.package_is_dirty():
            raise ConanException("Package %s is corrupted, aborting upload.\n"
                                 "Remove it with 'conan remove %s -p=%s'"
                                 % (pref, pref.ref, pref.package_id))
        cache_files = self._compress_package_files(pkg_layout, pref)
        prev_bundle["files"] = cache_files

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

        # Do a copy so the location of CONANINFO and MANIFEST is the "download" folder one
        mkdir(download_pkg_folder)
        shutil.copy2(os.path.join(package_folder, CONANINFO),
                     os.path.join(download_pkg_folder, CONANINFO))
        shutil.copy2(os.path.join(package_folder, CONAN_MANIFEST),
                     os.path.join(download_pkg_folder, CONAN_MANIFEST))
        # Files NOT included in the tgz
        files.pop(CONANINFO)
        files.pop(CONAN_MANIFEST)

        if not os.path.isfile(package_tgz):
            if self._output and not self._output.is_terminal:
                self._output.info("Compressing package...")
            tgz_files = {f: path for f, path in files.items()}
            compresslevel = self._app.cache.new_config.get("core.gzip:compresslevel", check_type=int)
            tgz_path = compress_files(tgz_files, PACKAGE_TGZ_NAME, download_pkg_folder,
                                      compresslevel=compresslevel)
            assert tgz_path == package_tgz
            assert os.path.exists(package_tgz)

        return {PACKAGE_TGZ_NAME: package_tgz,
                CONANINFO: os.path.join(download_pkg_folder, CONANINFO),
                CONAN_MANIFEST: os.path.join(download_pkg_folder, CONAN_MANIFEST)}


class UploadExecutor:
    """ does the actual file transfer to the remote. The files to be uploaded have already
    been computed and are passed in the ``upload_data`` parameter, so this executor is also
    agnostic about which files are transferred
    """
    def __init__(self, app: ConanApp):
        self._app = app
        self._output = ConanOutput()

    def upload(self, upload_data, remote):
        self._output.info("Uploading artifacts")
        for ref, bundle in upload_data.refs():
            if bundle.get("upload"):
                self.upload_recipe(ref, bundle, remote)
            for pref, prev_bundle in upload_data.prefs(ref, bundle):
                if prev_bundle.get("upload"):
                    self.upload_package(pref, prev_bundle, remote)

    def upload_recipe(self, ref, bundle, remote):
        self._output.info(f"Uploading recipe '{ref.repr_notime()}'")
        t1 = time.time()
        cache_files = bundle["files"]

        self._app.remote_manager.upload_recipe(ref, cache_files, remote)

        duration = time.time() - t1
        self._output.debug(f"Upload {ref} in {duration} time")
        return ref

    def upload_package(self, pref, prev_bundle, remote):
        self._output.info(f"Uploading package '{pref.repr_notime()}'")
        cache_files = prev_bundle["files"]
        assert (pref.revision is not None), "Cannot upload a package without PREV"
        assert (pref.ref.revision is not None), "Cannot upload a package without RREV"

        t1 = time.time()
        self._app.remote_manager.upload_package(pref, cache_files, remote)
        duration = time.time() - t1
        self._output.debug(f"Upload {pref} in {duration} time")


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
        for filename, abs_path in sorted(files.items()):
            # recursive is False in case it is a symlink to a folder
            tgz.add(abs_path, filename, recursive=False)
        tgz.close()

    duration = time.time() - t1
    ConanOutput().debug(f"{name} compressed in {duration} time")
    return tgz_path
