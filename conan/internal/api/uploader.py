import fnmatch
import os
import shutil
import time

from conan.internal.conan_app import ConanApp
from conan.api.output import ConanOutput
from conans.client.source import retrieve_exports_sources
from conan.internal.errors import NotFoundException
from conan.errors import ConanException
from conan.internal.paths import (CONAN_MANIFEST, CONANFILE, EXPORT_SOURCES_TGZ_NAME,
                                  EXPORT_TGZ_NAME, PACKAGE_TGZ_NAME, CONANINFO)
from conans.util.files import (clean_dirty, is_dirty, gather_files,
                               gzopen_without_timestamps, set_dirty_context_manager, mkdir,
                               human_size)

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

    def check(self, upload_bundle, remote, force):
        for ref, recipe_bundle in upload_bundle.refs().items():
            self._check_upstream_recipe(ref, recipe_bundle, remote, force)
            for pref, prev_bundle in upload_bundle.prefs(ref, recipe_bundle).items():
                self._check_upstream_package(pref, prev_bundle, remote, force)

    def _check_upstream_recipe(self, ref, ref_bundle, remote, force):
        output = ConanOutput(scope=str(ref))
        output.info("Checking which revisions exist in the remote server")
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
                output.info(f"Recipe '{ref.repr_notime()}' already in server, forcing upload")
                ref_bundle["force_upload"] = True
                ref_bundle["upload"] = True
            else:
                output.info(f"Recipe '{ref.repr_notime()}' already in server, skipping upload")
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
            output = ConanOutput(scope=str(pref.ref))
            if force:
                output.info(f"Package '{pref.repr_notime()}' already in server, forcing upload")
                prev_bundle["force_upload"] = True
                prev_bundle["upload"] = True
            else:
                output.info(f"Package '{pref.repr_notime()}' already in server, skipping upload")
                prev_bundle["force_upload"] = False
                prev_bundle["upload"] = False


class PackagePreparator:
    def __init__(self, app: ConanApp, global_conf):
        self._app = app
        self._global_conf = global_conf

    def prepare(self, upload_bundle, enabled_remotes):
        local_url = self._global_conf.get("core.scm:local_url", choices=["allow", "block"])
        for ref, bundle in upload_bundle.refs().items():
            layout = self._app.cache.recipe_layout(ref)
            conanfile_path = layout.conanfile()
            conanfile = self._app.loader.load_basic(conanfile_path)
            url = conanfile.conan_data.get("scm", {}).get("url") if conanfile.conan_data else None
            if local_url != "allow" and url is not None:
                if not any(url.startswith(v) for v in ("ssh", "git", "http", "file")):
                    raise ConanException(f"Package {ref} contains conandata scm url={url}\n"
                                         "This isn't a remote URL, the build won't be reproducible\n"
                                         "Failing because conf 'core.scm:local_url!=allow'")

            if bundle.get("upload"):
                self._prepare_recipe(ref, bundle, conanfile, enabled_remotes)
            for pref, prev_bundle in upload_bundle.prefs(ref, bundle).items():
                if prev_bundle.get("upload"):
                    self._prepare_package(pref, prev_bundle)

    def _prepare_recipe(self, ref, ref_bundle, conanfile, remotes):
        """ do a bunch of things that are necessary before actually executing the upload:
        - retrieve exports_sources to complete the recipe if necessary
        - compress the artifacts in conan_export.tgz and conan_export_sources.tgz
        """
        try:
            recipe_layout = self._app.cache.recipe_layout(ref)
            retrieve_exports_sources(self._app.remote_manager, recipe_layout, conanfile, ref,
                                     remotes)
            cache_files = self._compress_recipe_files(recipe_layout, ref)
            ref_bundle["files"] = cache_files
        except Exception as e:
            raise ConanException(f"{ref} Error while compressing: {e}")

    def _compress_recipe_files(self, layout, ref):
        download_export_folder = layout.download_export()

        output = ConanOutput(scope=str(ref))
        for f in (EXPORT_TGZ_NAME, EXPORT_SOURCES_TGZ_NAME):
            tgz_path = os.path.join(download_export_folder, f)
            if is_dirty(tgz_path):
                output.warning("Removing %s, marked as dirty" % f)
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

        def add_tgz(tgz_name, tgz_files):
            tgz = os.path.join(download_export_folder, tgz_name)
            if os.path.isfile(tgz):
                result[tgz_name] = tgz
            elif tgz_files:
                compresslevel = self._global_conf.get("core.gzip:compresslevel", check_type=int)
                tgz = compress_files(tgz_files, tgz_name, download_export_folder,
                                     compresslevel=compresslevel, ref=ref)
                result[tgz_name] = tgz

        add_tgz(EXPORT_TGZ_NAME, files)
        add_tgz(EXPORT_SOURCES_TGZ_NAME, src_files)
        return result

    def _prepare_package(self, pref, prev_bundle):
        pkg_layout = self._app.cache.pkg_layout(pref)
        if pkg_layout.package_is_dirty():
            raise ConanException(f"Package {pref} is corrupted, aborting upload.\n"
                                 f"Remove it with 'conan remove {pref}'")
        cache_files = self._compress_package_files(pkg_layout, pref)
        prev_bundle["files"] = cache_files

    def _compress_package_files(self, layout, pref):
        output = ConanOutput(scope=str(pref))
        download_pkg_folder = layout.download_package()
        package_tgz = os.path.join(download_pkg_folder, PACKAGE_TGZ_NAME)
        if is_dirty(package_tgz):
            output.warning("Removing %s, marked as dirty" % PACKAGE_TGZ_NAME)
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
            tgz_files = {f: path for f, path in files.items()}
            compresslevel = self._global_conf.get("core.gzip:compresslevel", check_type=int)
            tgz_path = compress_files(tgz_files, PACKAGE_TGZ_NAME, download_pkg_folder,
                                      compresslevel=compresslevel, ref=pref)
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

    def upload(self, upload_data, remote):
        for ref, bundle in upload_data.refs().items():
            if bundle.get("upload"):
                self.upload_recipe(ref, bundle, remote)
            for pref, prev_bundle in upload_data.prefs(ref, bundle).items():
                if prev_bundle.get("upload"):
                    self.upload_package(pref, prev_bundle, remote)

    def upload_recipe(self, ref, bundle, remote):
        output = ConanOutput(scope=str(ref))
        cache_files = bundle["files"]

        output.info(f"Uploading recipe '{ref.repr_notime()}' ({_total_size(cache_files)})")

        t1 = time.time()
        self._app.remote_manager.upload_recipe(ref, cache_files, remote)

        duration = time.time() - t1
        output.debug(f"Upload {ref} in {duration} time")
        return ref

    def upload_package(self, pref, prev_bundle, remote):
        output = ConanOutput(scope=str(pref.ref))
        cache_files = prev_bundle["files"]
        assert (pref.revision is not None), "Cannot upload a package without PREV"
        assert (pref.ref.revision is not None), "Cannot upload a package without RREV"

        output.info(f"Uploading package '{pref.repr_notime()}' ({_total_size(cache_files)})")

        t1 = time.time()
        self._app.remote_manager.upload_package(pref, cache_files, remote)
        duration = time.time() - t1
        output.debug(f"Upload {pref} in {duration} time")


def compress_files(files, name, dest_dir, compresslevel=None, ref=None):
    t1 = time.time()
    # FIXME, better write to disk sequentially and not keep tgz contents in memory
    tgz_path = os.path.join(dest_dir, name)
    ConanOutput(scope=str(ref)).info(f"Compressing {name}")
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


def _total_size(cache_files):
    total_size = 0
    for file in cache_files.values():
        stat = os.stat(file)
        total_size += stat.st_size
    return human_size(total_size)


def _metadata_files(folder, metadata):
    result = {}
    for root, _, files in os.walk(folder):
        for f in files:
            abs_path = os.path.join(root, f)
            relpath = os.path.relpath(abs_path, folder)
            if metadata:
                if not any(fnmatch.fnmatch(relpath, m) for m in metadata):
                    continue
            path = os.path.join("metadata", relpath).replace("\\", "/")
            result[path] = abs_path
    return result


def gather_metadata(package_list, cache, metadata):
    for rref, recipe_bundle in package_list.refs().items():
        if metadata or recipe_bundle["upload"]:
            metadata_folder = cache.recipe_layout(rref).metadata()
            files = _metadata_files(metadata_folder, metadata)
            if files:
                ConanOutput(scope=str(rref)).info(f"Recipe metadata: {len(files)} files")
                recipe_bundle.setdefault("files", {}).update(files)
                recipe_bundle["upload"] = True

        for pref, pkg_bundle in package_list.prefs(rref, recipe_bundle).items():
            if metadata or pkg_bundle["upload"]:
                metadata_folder = cache.pkg_layout(pref).metadata()
                files = _metadata_files(metadata_folder, metadata)
                if files:
                    ConanOutput(scope=str(pref)).info(f"Package metadata: {len(files)} files")
                    pkg_bundle.setdefault("files", {}).update(files)
                    pkg_bundle["upload"] = True
