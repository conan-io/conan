import os
import stat
import tarfile
import time
import traceback

from conans.cli.output import ConanOutput
from conans.client.source import retrieve_exports_sources
from conans.client.userio import UserInput
from conans.errors import ConanException, NotFoundException, RecipeNotFoundException
from conans.model.manifest import gather_files
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.paths import (CONAN_MANIFEST, CONANFILE, EXPORT_SOURCES_TGZ_NAME,
                          EXPORT_TGZ_NAME, PACKAGE_TGZ_NAME, CONANINFO)
from conans.search.search import search_recipes
from conans.util import progress_bar
from conans.util.files import (clean_dirty, is_dirty,
                               gzopen_without_timestamps, set_dirty_context_manager)
from conans.util.progress_bar import left_justify_message
from conans.util.tracer import log_recipe_upload, log_compressed_files, log_package_upload

UPLOAD_POLICY_FORCE = "force-upload"
UPLOAD_POLICY_SKIP = "skip-upload"


class _RecipeData:
    def __init__(self, ref, prefs=None):
        self.ref = ref
        self.upload = None
        self.force = None
        self.dirty = None
        self.build_always = None
        self.files = None
        self.packages = [_PackageData(p) for p in prefs or []]

    def serialize(self):
        return {
            "ref": repr(self.ref),
            "dirty": self.dirty,
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


class _UploadCollecter:
    """
    Collect all the packages in the local cache to be uploaded:
    - Collect the refs that matches the given pattern _collect_refs_to_upload
    - Collect for every ref all the binaries IDs that has to be uploaded
      "_collect_packages_to_upload". This may discard binaries that do not
      belong to the current RREV
    The collection of this does the interactivity (ask user if yes/no),
    the errors (don't upload packages with policy=build_always, and computing
    the full REVISIONS for every that has to be uploaded.
    No remote API calls are done in this step, everything is local
    """
    def __init__(self, cache):
        self._cache = cache
        self._user_input = UserInput(cache.config.non_interactive)

    def collect(self, pattern, confirm, all_packages):
        """ validate inputs and compute the refs (without revisions) to be uploaded
        """
        def complete_latest_rev(recipe_ref):
            # If the user input doesn't provide revision, assume latest
            if recipe_ref.revision is None:
                latest = self._cache.get_latest_rrev(recipe_ref)
                if not latest:
                    raise RecipeNotFoundException(recipe_ref.to_conanfileref())
                recipe_ref.revision = latest.revision

        result = _UploadData()
        try:
            pref = PkgReference.loads(pattern)
        except ConanException:
            try:
                ref = RecipeReference.loads(pattern)
                complete_latest_rev(ref)
                # If it is a valid and existing reference, then add it
                refs = [ref]
            except ConanException as e:
                refs = search_recipes(self._cache, pattern)
                if not refs:
                    raise NotFoundException(f"No recipes found matching pattern '{pattern}'")

                refs = [RecipeReference.from_conanref(r) for r in refs]
                for r in refs:
                    assert r.revision is not None  # search should return with revision

                # Confirmation is requested only for pattern case, because if exact, not an issue
                if not confirm:
                    confirmed_refs = []
                    for ref in refs:
                        msg = "Are you sure you want to upload '%s'?" % (str(ref))
                        upload = self._user_input.request_boolean(msg)
                        if upload:
                            confirmed_refs.append(ref)
                    refs = confirmed_refs
            # Now check the binaries
            for r in refs:
                if all_packages:
                    prefs = self._cache.get_package_references(r)
                    for p in prefs:
                        p2 = self._cache.get_latest_prev(p)
                        p.revision = p2.revision
                        assert p.revision is not None
                    if prefs:
                        result.add_prefs(prefs)
                    else:
                        result.add_ref(r)
                else:
                    result.add_ref(r)
        else:
            complete_latest_rev(pref.ref)
            p2 = self._cache.get_latest_prev(pref)
            if p2 is None:
                raise ConanException(f"There is not package binary matching {pref}")
            pref.revision = p2.revision
            result.add_prefs([pref])
        return result


class _UploadChecker:
    """
    Check which revisions already exist in the server, if they already exist, not necessary
    to upload
    """
    def __init__(self, remote_manager, output):
        self._remote_manager = remote_manager
        self._output = output

    def check(self, upload_data, remote, policy):
        self._output.info("Checking which revisions exist in the remote server")
        for recipe in upload_data.recipes:
            self.check_recipe(recipe, remote, policy)
            for package in recipe.packages:
                self.check_package(package, remote, policy)

    def check_recipe(self, recipe, remote, policy):
        ref = recipe.ref
        try:
            assert ref.revision
            # TODO: It is a bit ugly, interface-wise to ask for revisions to check existence
            server_revisions = self._remote_manager.get_recipe_revisions(ref.to_conanfileref(),
                                                                         remote)
            assert ref.revision == server_revisions[0]["revision"]
            assert len(server_revisions) == 1
        except NotFoundException:
            recipe.upload = True
            recipe.force = False
        else:
            if policy == UPLOAD_POLICY_FORCE:
                self._output.info("{} already in server, forcing upload".format(repr(ref)))
                recipe.upload = True
                recipe.force = False
            else:
                self._output.info("{} already in server, skipping upload".format(repr(ref)))
                recipe.upload = False
                recipe.force = False

    def check_package(self, package, remote, policy):
        pref = package.pref
        assert (pref.revision is not None), "Cannot upload a package without PREV"
        assert (pref.ref.revision is not None), "Cannot upload a package without RREV"

        try:
            # TODO: It is a bit ugly, interface-wise to ask for revisions to check existence
            server_revisions = self._remote_manager.get_package_revisions(pref, remote)
            assert pref.revision == server_revisions[0]["revision"]
            assert len(server_revisions) == 1
        except NotFoundException:
            package.upload = True
            package.force = False
        else:
            if policy == UPLOAD_POLICY_FORCE:
                self._output.info("{} already in server, forcing upload".format(repr(pref)))
                package.upload = True
                package.force = True
            else:
                self._output.info("{} already in server, skipping upload".format(repr(pref)))
                package.upload = False
                package.force = False


class _PackagePreparator:
    def __init__(self, cache, remote_manager, hook_manager, loader):
        self._cache = cache
        self._remote_manager = remote_manager
        self._output = ConanOutput()
        self._hook_manager = hook_manager
        self._loader = loader

    def prepare(self, upload_data, remotes, integrity_check):
        self._output.info("Preparing artifacts to upload")
        for recipe in upload_data.recipes:
            layout = self._cache.ref_layout(recipe.ref)
            conanfile_path = layout.conanfile()
            conanfile = self._loader.load_basic(conanfile_path)
            if recipe.upload:
                self.prepare_recipe(recipe, conanfile, remotes)
            if conanfile.build_policy == "always":
                recipe.build_always = True
            else:
                recipe.build_always = False
                for package in recipe.packages:
                    if package.upload:
                        self.prepare_package(package, integrity_check)

    def prepare_recipe(self, recipe, conanfile, remotes):
        """ do a bunch of things that are necessary before actually executing the upload:
        - retrieve exports_sources to complete the recipe if necessary
        - compress the artifacts in conan_export.tgz and conan_export_sources.tgz
        - check if package is ok to be uploaded, if scm info missing, will raise
        - check if the remote recipe is newer, raise
        - compare and decide which files need to be uploaded (and deleted from server)
        """
        try:
            ref = recipe.ref
            recipe_layout = self._cache.ref_layout(ref)
            retrieve_exports_sources(self._remote_manager, recipe_layout, conanfile,
                                     ref.to_conanfileref(), remotes)
            cache_files = self._compress_recipe_files(recipe_layout, ref)
            recipe.files = cache_files

            # Check SCM data for auto fields
            if hasattr(conanfile, "scm") and (
                    conanfile.scm.get("url") == "auto" or conanfile.scm.get("revision") == "auto" or
                    conanfile.scm.get("type") is None or conanfile.scm.get("url") is None or
                    conanfile.scm.get("revision") is None):
                recipe.dirty = True
            else:
                recipe.dirty = False
        except Exception as e:
            print(traceback.format_exc())
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
        files, symlinks = gather_files(export_folder)
        if CONANFILE not in files or CONAN_MANIFEST not in files:
            raise ConanException("Cannot upload corrupted recipe '%s'" % str(ref))
        export_src_folder = layout.export_sources()
        src_files, src_symlinks = gather_files(export_src_folder)

        result = {CONANFILE: files.pop(CONANFILE),
                  CONAN_MANIFEST: files.pop(CONAN_MANIFEST)}

        def add_tgz(tgz_name, tgz_files, tgz_symlinks, msg):
            tgz = os.path.join(download_export_folder, tgz_name)
            if os.path.isfile(tgz):
                result[tgz_name] = tgz
            elif tgz_files:
                if self._output and not self._output.is_terminal:
                    self._output.info(msg)
                tgz = compress_files(tgz_files, tgz_symlinks, tgz_name, download_export_folder)
                result[tgz_name] = tgz

        add_tgz(EXPORT_TGZ_NAME, files, symlinks, "Compressing recipe...")
        add_tgz(EXPORT_SOURCES_TGZ_NAME, src_files, src_symlinks, "Compressing recipe sources...")
        return result

    def prepare_package(self, package, integrity_check):
        pref = package.pref
        pkg_layout = self._cache.pkg_layout(pref)
        if pkg_layout.package_is_dirty():
            raise ConanException("Package %s is corrupted, aborting upload.\n"
                                 "Remove it with 'conan remove %s -p=%s'"
                                 % (pref, pref.ref, pref.package_id))
        cache_files = self._compress_package_files(pkg_layout, pref)
        package.files = cache_files
        if integrity_check:
            self._package_integrity_check(pref)

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
        files, symlinks = gather_files(package_folder)

        if CONANINFO not in files or CONAN_MANIFEST not in files:
            raise ConanException("Cannot upload corrupted package '%s'" % str(pref))

        if not os.path.isfile(package_tgz):
            if self._output and not self._output.is_terminal:
                self._output.info("Compressing package...")
            tgz_files = {f: path for f, path in files.items() if
                         f not in [CONANINFO, CONAN_MANIFEST]}
            tgz_path = compress_files(tgz_files, symlinks, PACKAGE_TGZ_NAME, download_pkg_folder)
            assert tgz_path == package_tgz
            assert os.path.exists(package_tgz)

        return {PACKAGE_TGZ_NAME: package_tgz,
                CONANINFO: files[CONANINFO],
                CONAN_MANIFEST: files[CONAN_MANIFEST]}

    def _package_integrity_check(self, pref):
        # If package has been modified remove tgz to regenerate it
        self._output.rewrite_line("Checking package integrity...")

        # short_paths = None is enough if there exist short_paths
        pkg_layout = self._cache.pkg_layout(pref)
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


class CmdUpload(object):
    """
    All the REVISIONS are local defined, not retrieved from servers

    This requires calling to the remote API methods:
    - get_recipe_sources() to get the export_sources if they are missing
    - get_recipe_snapshot() to do the diff and know what files to upload
    """
    def __init__(self, app):
        self._app = app
        self._cache = app.cache
        self._progress_output = progress_bar.ProgressOutput(ConanOutput())
        self._remote_manager = app.remote_manager
        self._loader = app.loader
        self._hook_manager = app.hook_manager
        self._upload_thread_pool = None
        self._exceptions_list = []

    def upload(self, reference_or_pattern,
               all_packages=None, confirm=False, retry=None, retry_wait=None, integrity_check=False,
               policy=None, query=None, parallel_upload=False):
        t1 = time.time()

        remote = self._app.selected_remote
        collecter = _UploadCollecter(self._cache)
        upload_data = collecter.collect(reference_or_pattern, confirm, all_packages)

        checker = _UploadChecker(self._remote_manager, self._progress_output)
        checker.check(upload_data, remote, policy)

        preparator = _PackagePreparator(self._cache, self._remote_manager, self._hook_manager,
                                        self._loader)
        preparator.prepare(upload_data, self._app.enabled_remotes, integrity_check)
        # print("PREPARED", json.dumps(upload_data.serialize(), indent=2))

        if policy == UPLOAD_POLICY_SKIP:
            return None

        self._remote_manager.check_credentials(remote)
        executor = _UploadExecutor(self._remote_manager, self._cache, self._hook_manager,
                                   self._progress_output)
        executor.upload(upload_data, retry, retry_wait, remote)

        '''
        self._upload_thread_pool = ThreadPool(cpu_count() if parallel_upload else 1)

        def upload_ref(ref_conanfile_prefs):
            _ref, _conanfile, _prefs = ref_conanfile_prefs
            try:
                self._upload_ref(_conanfile, _ref, _prefs, retry, retry_wait)
            except BaseException as base_exception:
                base_trace = traceback.format_exc()
                self._exceptions_list.append((base_exception, _ref, base_trace, remote))

        self._upload_thread_pool.map(upload_ref, refs_to_upload)
        self._upload_thread_pool.close()
        self._upload_thread_pool.join()

        if len(self._exceptions_list) > 0:
            for exc, ref, trace, remote in self._exceptions_list:
                t = "recipe" if isinstance(ref, ConanFileReference) else "package"
                msg = "%s: Upload %s to '%s' failed: %s\n" % (str(ref), t, remote.name, str(exc))
                if get_env("CONAN_VERBOSE_TRACEBACK", False):
                    msg += trace
                self._progress_output.error(msg)

            raise ConanException("Errors uploading some packages")
        '''

    def _upload_ref(self, conanfile, ref, prefs, retry, retry_wait):
        """ Uploads the recipes and binaries identified by ref
        """
        assert (ref.revision is not None), "Cannot upload a recipe without RREV"
        conanfile_path = self._cache.ref_layout(ref).conanfile()
        # FIXME: I think it makes no sense to specify a remote to "pre_upload"
        # FIXME: because the recipe can have one and the package a different one
        remote = self._app.selected_remote
        msg = "\rUploading %s to remote '%s'" % (str(ref), remote.name)
        self._progress_output.info(left_justify_message(msg))
        self._upload_recipe(ref, conanfile, retry, retry_wait, remote)

        # Now the binaries
        if prefs:
            total = len(prefs)

            def upload_package_index(index_pref):
                index, pref = index_pref
                try:
                    up_msg = "\rUploading package %d/%d: %s to '%s'" % (index + 1, total,
                                                                        str(pref.package_id),
                                                                        remote.name)
                    self._progress_output.info(left_justify_message(up_msg))
                    self._upload_package(pref, remote, retry, retry_wait)
                except BaseException as pkg_exc:
                    trace = traceback.format_exc()
                    return pkg_exc, pref, trace, remote

            def upload_package_callback(ret):
                package_exceptions = [r for r in ret if r is not None]
                self._exceptions_list.extend(package_exceptions)

            # This doesn't wait for the packages to end, so the function returns
            # and the "pool entry" for the recipe is released
            self._upload_thread_pool.map_async(upload_package_index,
                                               [(index, pref) for index, pref
                                                in enumerate(prefs)],
                                               callback=upload_package_callback)


class _UploadExecutor:
    def __init__(self, remote_manager, cache, hook_manager, output):
        self._remote_manager = remote_manager
        self._cache = cache
        self._hook_manager = hook_manager
        self._output = output

    def upload(self, upload_data, retry, retry_wait, remote):
        self._output.info("Uploading artifacts")
        for recipe in upload_data.recipes:
            if recipe.dirty and not recipe.force:
                raise ConanException("The recipe contains invalid data in the 'scm' attribute"
                                     " (some 'auto' values or missing fields 'type', 'url' or"
                                     " 'revision'). Use '--force' to ignore this error or export"
                                     " again the recipe ('conan export' or 'conan create') to"
                                     " fix these issues.")
            if recipe.upload:
                self.upload_recipe(recipe, remote, retry, retry_wait)
            if recipe.build_always and recipe.packages:
                # TODO: Maybe do not raise? Allow it with --force?
                raise ConanException("Conanfile '%s' has build_policy='always', "
                                     "no packages can be uploaded" % str(recipe.ref))
            for package in recipe.packages:
                if package.upload:
                    self.upload_package(package, remote, retry, retry_wait)

    def _recipe_files_to_upload(self, ref, files, remote, force):
        if not force:
            return files, set()
        # only check difference if it is a force upload
        remote_snapshot = self._remote_manager.get_recipe_snapshot(ref, remote)
        if not remote_snapshot:
            return files, set()

        deleted = set(remote_snapshot).difference(files)
        return files, deleted

    def upload_recipe(self, recipe, remote, retry, retry_wait):
        self._output.info(f"Uploading {recipe.ref}")
        t1 = time.time()
        ref = recipe.ref
        cache_files = recipe.files
        force = recipe.force
        files_to_upload, deleted = self._recipe_files_to_upload(ref, cache_files, remote, force)

        ref_layout = self._cache.ref_layout(ref)
        conanfile_path = ref_layout.conanfile()
        self._hook_manager.execute("pre_upload_recipe", conanfile_path=conanfile_path,
                                   reference=ref, remote=remote)

        upload_ref = ref
        self._remote_manager.upload_recipe(upload_ref, files_to_upload, deleted, remote, retry,
                                           retry_wait)
        duration = time.time() - t1
        log_recipe_upload(ref.to_conanfileref(), duration, cache_files, remote.name)
        self._hook_manager.execute("post_upload_recipe", conanfile_path=conanfile_path,
                                   reference=ref, remote=remote)
        return ref

    def upload_package(self, package, remote, retry=None, retry_wait=None):
        self._output.info(f"Uploading {package.pref}")
        pref = package.pref
        cache_files = package.files
        assert (pref.revision is not None), "Cannot upload a package without PREV"
        assert (pref.ref.revision is not None), "Cannot upload a package without RREV"

        ref_layout = self._cache.ref_layout(pref.ref)
        conanfile_path = ref_layout.conanfile()
        self._hook_manager.execute("pre_upload_package", conanfile_path=conanfile_path,
                                   reference=pref.ref,
                                   package_id=pref.package_id,
                                   remote=remote)
        t1 = time.time()
        self._remote_manager.upload_package(pref, cache_files, remote, retry, retry_wait)
        duration = time.time() - t1
        log_package_upload(pref, duration, cache_files, remote)
        self._hook_manager.execute("post_upload_package", conanfile_path=conanfile_path,
                                   reference=pref.ref, package_id=pref.package_id, remote=remote)


def compress_files(files, symlinks, name, dest_dir):
    t1 = time.time()
    # FIXME, better write to disk sequentially and not keep tgz contents in memory
    tgz_path = os.path.join(dest_dir, name)
    with set_dirty_context_manager(tgz_path), open(tgz_path, "wb") as tgz_handle:
        tgz = gzopen_without_timestamps(name, mode="w", fileobj=tgz_handle)

        for filename, dest in sorted(symlinks.items()):
            info = tarfile.TarInfo(name=filename)
            info.type = tarfile.SYMTYPE
            info.linkname = dest
            info.size = 0  # A symlink shouldn't have size
            tgz.addfile(tarinfo=info)

        mask = ~(stat.S_IWOTH | stat.S_IWGRP)
        with progress_bar.iterate_list_with_progress(sorted(files.items()),
                                                     "Compressing %s" % name) as pg_file_list:
            for filename, abs_path in pg_file_list:
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
