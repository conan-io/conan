import os
import stat
import tarfile
import time
import traceback
from multiprocessing.pool import ThreadPool

from conans.cli.output import ConanOutput
from conans.client.userio import UserInput
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.util import progress_bar
from conans.util.env_reader import get_env
from conans.util.progress_bar import left_justify_message
from conans.client.source import retrieve_exports_sources
from conans.errors import ConanException, NotFoundException, RecipeNotFoundException
from conans.model.manifest import gather_files
from conans.model.ref import ConanFileReference, check_valid_ref
from conans.paths import (CONAN_MANIFEST, CONANFILE, EXPORT_SOURCES_TGZ_NAME,
                          EXPORT_TGZ_NAME, PACKAGE_TGZ_NAME, CONANINFO)
from conans.search.search import search_recipes
from conans.util.files import (load, clean_dirty, is_dirty,
                               gzopen_without_timestamps, set_dirty_context_manager)
from conans.util.log import logger
from conans.util.tracer import log_recipe_upload, log_compressed_files, log_package_upload
from conans.tools import cpu_count


UPLOAD_POLICY_FORCE = "force-upload"
UPLOAD_POLICY_SKIP = "skip-upload"


class _UploadCollecter(object):
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
    def __init__(self, cache, loader):
        self._cache = cache
        self._user_input = UserInput(cache.config.non_interactive)
        self._loader = loader

    def collect(self, package_id, reference_or_pattern, confirm, remote_name, all_packages, query):
        refs, confirm = self._collects_refs_to_upload(package_id, reference_or_pattern, confirm)
        refs = self._collect_packages_to_upload(refs, confirm, remote_name, all_packages,
                                                query, package_id)
        return refs

    def _collects_refs_to_upload(self, package_id, reference_or_pattern, confirm):
        """ validate inputs and compute the refs (without revisions) to be uploaded
        """
        if package_id and not check_valid_ref(reference_or_pattern, strict_mode=False):
            raise ConanException("-p parameter only allowed with a valid recipe reference, "
                                 "not with a pattern")

        if package_id or check_valid_ref(reference_or_pattern):
            # Upload package
            ref = ConanFileReference.loads(reference_or_pattern)
            rrev = self._cache.get_latest_rrev(ref)
            if not rrev:
                raise RecipeNotFoundException(ref)
            else:
                refs = [rrev, ]
            confirm = True
        else:
            refs = search_recipes(self._cache, reference_or_pattern)
            if not refs:
                raise NotFoundException(("No packages found matching pattern '%s'" %
                                         reference_or_pattern))
        return refs, confirm

    def _collect_packages_to_upload(self, refs, confirm, remote_name, all_packages, query,
                                    package_id):
        """ compute the references with revisions and the package_ids to be uploaded
        """
        # Group recipes by remote
        result = []

        for ref in refs:
            # TODO: cache2.0. For 2.0 we should always specify the revision of the reference
            #  that we want to upload, check if  we should move this to other place

            upload = True
            if not confirm:
                msg = "Are you sure you want to upload '%s' to '%s'?" % (str(ref), remote_name)
                upload = self._user_input.request_boolean(msg)
            if upload:
                try:
                    conanfile_path = self._cache.ref_layout(ref).conanfile()
                    conanfile = self._loader.load_basic(conanfile_path)
                except NotFoundException:
                    raise NotFoundException(("There is no local conanfile exported as %s" %
                                             str(ref)))

                # TODO: This search of binary packages has to be improved, more robust
                # So only real packages are retrieved
                if all_packages or query:
                    if all_packages:
                        query = None

                    # TODO: cache2.0 do we want to upload all package_revisions ? Just the latest
                    #  upload just the latest for the moment
                    # TODO: cache2.0 Ignoring the query for the moment
                    packages_ids = []
                    for pkg_id in self._cache.get_package_references(ref):
                        packages_ids.append(self._cache.get_latest_prev(pkg_id))

                elif package_id:
                    # TODO: cache2.0 if we specify a package id we could have multiple package revisions
                    #  something like: upload pkg/1.0:pkg_id will upload the package id for the latest prev
                    #  or for all of them
                    prev = package_id.split("#")[1] if "#" in package_id else ""
                    package_id = package_id.split("#")[0]
                    pref = PkgReference(ref, package_id, prev)
                    # FIXME: The name is package_ids but we pass the latest prev for each package id
                    packages_ids = []
                    packages = [pref] if pref.revision else self._cache.get_package_references(pref)
                    for pkg_ref in packages:
                        latest_prev = self._cache.get_latest_prev(pkg_ref) \
                            if pkg_ref.package_id == package_id else None
                        if latest_prev:
                            packages_ids.append(latest_prev)

                    if not packages_ids:
                        prev = f"#{prev}" if prev else ""
                        raise ConanException(f"Binary package {str(ref)}:{package_id}{prev} not found")
                else:
                    packages_ids = []
                if packages_ids:
                    if conanfile.build_policy == "always":
                        raise ConanException("Conanfile '%s' has build_policy='always', "
                                             "no packages can be uploaded" % str(ref))
                prefs = []
                # Gather all the complete PREFS with PREV
                for package in packages_ids:
                    package_id, package_revision = package.package_id, package.revision
                    assert package_revision is not None, "PREV cannot be None to upload"
                    prefs.append(PkgReference(ref, package_id, package_revision))
                result.append((ref, conanfile, prefs))

        return result


class _PackagePreparator(object):
    def __init__(self, cache, remote_manager, hook_manager):
        self._cache = cache
        self._remote_manager = remote_manager
        self._output = ConanOutput()
        self._hook_manager = hook_manager

    def prepare_recipe(self, ref, conanfile, remote, remotes, policy, force):
        """ do a bunch of things that are necessary before actually executing the upload:
        - retrieve exports_sources to complete the recipe if necessary
        - compress the artifacts in conan_export.tgz and conan_export_sources.tgz
        - check if package is ok to be uploaded, if scm info missing, will raise
        - check if the remote recipe is newer, raise
        - compare and decide which files need to be uploaded (and deleted from server)
        """
        recipe_layout = self._cache.ref_layout(ref)

        retrieve_exports_sources(self._remote_manager, recipe_layout, conanfile, ref, remotes)

        conanfile_path = recipe_layout.conanfile()
        self._hook_manager.execute("pre_upload_recipe", conanfile_path=conanfile_path,
                                   reference=ref, remote=remote)

        t1 = time.time()
        cache_files = self._compress_recipe_files(recipe_layout, ref)

        if policy != UPLOAD_POLICY_FORCE:
            # Check SCM data for auto fields
            if hasattr(conanfile, "scm") and (
                    conanfile.scm.get("url") == "auto" or conanfile.scm.get("revision") == "auto" or
                    conanfile.scm.get("type") is None or conanfile.scm.get("url") is None or
                    conanfile.scm.get("revision") is None):
                raise ConanException("The recipe contains invalid data in the 'scm' attribute"
                                     " (some 'auto' values or missing fields 'type', 'url' or"
                                     " 'revision'). Use '--force' to ignore this error or export"
                                     " again the recipe ('conan export' or 'conan create') to"
                                     " fix these issues.")

        if policy == UPLOAD_POLICY_SKIP:
            return

        files_to_upload, deleted = self._recipe_files_to_upload(ref, cache_files, remote, force)
        return files_to_upload, deleted, cache_files, conanfile_path, t1, recipe_layout

    def _print_manifest_information(self, remote_recipe_manifest, local_manifest, ref, remote):
        try:
            self._output.info("\n%s" % ("-"*40))
            self._output.info("Remote manifest:")
            self._output.info(remote_recipe_manifest)
            self._output.info("Local manifest:")
            self._output.info(local_manifest)
            difference = remote_recipe_manifest.difference(local_manifest)
            if "conanfile.py" in difference:
                contents = load(self._cache.ref_layout(ref).conanfile())
                endlines = "\\r\\n" if "\r\n" in contents else "\\n"
                self._output.info("Local 'conanfile.py' using '%s' line-ends" % endlines)
                remote_contents = self._remote_manager.get_recipe_path(ref, path="conanfile.py",
                                                                       remote=remote)
                endlines = "\\r\\n" if "\r\n" in remote_contents else "\\n"
                self._output.info("Remote 'conanfile.py' using '%s' line-ends" % endlines)
            self._output.info("\n%s" % ("-"*40))
        except Exception as e:
            self._output.info("Error printing information about the diff: %s" % str(e))

    def _recipe_files_to_upload(self, ref, files, remote, force):
        # TODO: Check this weird place to check credentials
        self._remote_manager.check_credentials(remote)
        if not force:
            return files, set()
        # only check difference if it is a force upload
        remote_snapshot = self._remote_manager.get_recipe_snapshot(ref, remote)
        if not remote_snapshot:
            return files, set()

        deleted = set(remote_snapshot).difference(files)
        return files, deleted

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

    def prepare_package(self, pref, integrity_check, policy, p_remote):
        pkg_layout = self._cache.pkg_layout(pref)
        cache_files = self._compress_package_files(pkg_layout, pref, integrity_check)

        if policy == UPLOAD_POLICY_SKIP:
            return None
        return cache_files

    def _compress_package_files(self, layout, pref, integrity_check):
        t1 = time.time()

        if layout.package_is_dirty():
            raise ConanException("Package %s is corrupted, aborting upload.\n"
                                 "Remove it with 'conan remove %s -p=%s'"
                                 % (pref, pref.ref, pref.package_id))

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
            logger.error("Missing info or manifest in uploading files: %s" % (str(files)))
            raise ConanException("Cannot upload corrupted package '%s'" % str(pref))

        logger.debug("UPLOAD: Time remote_manager build_files_set : %f" % (time.time() - t1))
        if integrity_check:
            self._package_integrity_check(pref, files, package_folder)
            logger.debug("UPLOAD: Time remote_manager check package integrity : %f"
                         % (time.time() - t1))

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

    def _package_integrity_check(self, pref, files, package_folder):
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

            if PACKAGE_TGZ_NAME in files:
                tgz_path = os.path.join(package_folder, PACKAGE_TGZ_NAME)
                try:
                    os.unlink(tgz_path)
                except OSError:
                    pass
            error_msg = os.linesep.join("Mismatched checksum '%s' (manifest: %s, file: %s)"
                                        % (fname, h1, h2) for fname, (h1, h2) in diff.items())
            logger.error("Manifests doesn't match!\n%s" % error_msg)
            raise ConanException("Cannot upload corrupted package '%s'" % str(pref))
        else:
            self._output.rewrite_line("Package integrity OK!")
        self._output.writeln("")


class CmdUpload(object):
    """ This class is responsible for uploading packages to remotes. The flow is:
    - Collect all the packages to be uploaded with the UploadCollecter
    - Execute the upload. For every ref:
        - Upload the recipe of the ref: "_upload_recipe"
            - If not FORCE, check the date "_check_recipe_date", i.e. if there are
              changes, do not allow uploading if the remote date is newer than the
              local cache one
            - Retrieve the sources (exports_sources), if they are not cached, and
              uploading to a different remote. "retrieve_exports_sources"
            - Gather files and create 2 .tgz (exports, exports_sources) with
              "_compress_recipe_files"
            - Decide which files have to be uploaded and deleted from the server
              based on the different with the remote snapshot "_recipe_files_to_upload"
              This can raise if upload policy is not overwrite
            - Execute the real transfer "remote_manager.upload_recipe()"
        - For every package_id of every ref: "_upload_package"
            - Gather files and create package.tgz. "_compress_package_files"
            - (Optional) Do the integrity check of the package
            - Decide which files to upload and delete from server:
              "_package_files_to_upload". Can raise if policy is NOT overwrite
            - Do the actual upload

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
        self._preparator = _PackagePreparator(app.cache, app.remote_manager, app.hook_manager)
        self._user_input = UserInput(self._cache.config.non_interactive)

    def upload(self, reference_or_pattern, package_id=None,
               all_packages=None, confirm=False, retry=None, retry_wait=None, integrity_check=False,
               policy=None, query=None, parallel_upload=False):
        t1 = time.time()

        remote = self._app.selected_remote
        collecter = _UploadCollecter(self._cache, self._loader)
        refs_to_upload = collecter.collect(package_id, reference_or_pattern, confirm, remote.name,
                                           all_packages, query)

        if parallel_upload:
            self._cache.config.non_interactive = True
        self._upload_thread_pool = ThreadPool(cpu_count() if parallel_upload else 1)

        self._progress_output.info("Uploading to remote '{}':".format(remote.name))

        def upload_ref(ref_conanfile_prefs):
            _ref, _conanfile, _prefs = ref_conanfile_prefs
            try:
                self._upload_ref(_conanfile, _ref, _prefs, retry, retry_wait,
                                 integrity_check, policy)
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

        logger.debug("UPLOAD: Time manager upload: %f" % (time.time() - t1))

    def _upload_ref(self, conanfile, ref, prefs, retry, retry_wait, integrity_check, policy):
        """ Uploads the recipes and binaries identified by ref
        """
        assert (ref.revision is not None), "Cannot upload a recipe without RREV"
        conanfile_path = self._cache.ref_layout(ref).conanfile()
        # FIXME: I think it makes no sense to specify a remote to "pre_upload"
        # FIXME: because the recipe can have one and the package a different one
        remote = self._app.selected_remote
        self._hook_manager.execute("pre_upload", conanfile_path=conanfile_path,
                                   reference=ref, remote=remote)
        msg = "\rUploading %s to remote '%s'" % (str(ref), remote.name)
        self._progress_output.info(left_justify_message(msg))
        self._upload_recipe(ref, conanfile, retry, retry_wait, policy, remote)

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
                    self._upload_package(pref, remote, retry, retry_wait, integrity_check, policy)
                except BaseException as pkg_exc:
                    trace = traceback.format_exc()
                    return pkg_exc, pref, trace, remote

            def upload_package_callback(ret):
                package_exceptions = [r for r in ret if r is not None]
                self._exceptions_list.extend(package_exceptions)
                if not package_exceptions:
                    # FIXME: I think it makes no sense to specify a remote to "post_upload"
                    # FIXME: because the recipe can have one and the package a different one
                    self._hook_manager.execute("post_upload", conanfile_path=conanfile_path,
                                               reference=ref, remote=remote)

            # This doesn't wait for the packages to end, so the function returns
            # and the "pool entry" for the recipe is released
            self._upload_thread_pool.map_async(upload_package_index,
                                               [(index, pref) for index, pref
                                                in enumerate(prefs)],
                                               callback=upload_package_callback)
        else:
            # FIXME: I think it makes no sense to specify a remote to "post_upload"
            # FIXME: because the recipe can have one and the package a different one
            self._hook_manager.execute("post_upload", conanfile_path=conanfile_path, reference=ref,
                                       remote=remote)

    def _upload_recipe(self, ref, conanfile, retry, retry_wait, policy, remote):
        force = False
        try:
            assert ref.revision
            # TODO: It is a bit ugly, interface-wise to ask for revisions to check existence
            server_revisions = self._remote_manager.get_recipe_revisions(ref, remote)
            assert ref.revision == server_revisions[0]["revision"]
            assert len(server_revisions) == 1
        except NotFoundException:
            pass
        else:
            if policy == UPLOAD_POLICY_FORCE:
                force = True
                self._progress_output.info("{} already in server, forcing upload".format(repr(ref)))
            else:
                self._progress_output.info("{} already in server, skipping upload".format(repr(ref)))
                return

        remotes = self._app.enabled_remotes
        prep = self._preparator.prepare_recipe(ref, conanfile, remote, remotes, policy, force)

        if policy == UPLOAD_POLICY_SKIP:
            return ref

        files_to_upload, deleted, cache_files, conanfile_path, t1, layout = prep
        if files_to_upload or deleted:
            upload_ref = RecipeReference.from_conanref(ref)
            self._remote_manager.upload_recipe(upload_ref, files_to_upload, deleted, remote, retry,
                                               retry_wait)
            msg = "\rUploaded conan recipe '%s' to '%s': %s" % (str(ref), remote.name, remote.url)
            self._progress_output.info(left_justify_message(msg))
        else:
            self._progress_output.info("Recipe is up to date, upload skipped")
        duration = time.time() - t1
        log_recipe_upload(ref, duration, cache_files, remote.name)
        self._hook_manager.execute("post_upload_recipe", conanfile_path=conanfile_path,
                                   reference=ref, remote=remote)

        return ref

    def _upload_package(self, pref, remote, retry=None, retry_wait=None, integrity_check=False,
                        policy=None):

        assert (pref.revision is not None), "Cannot upload a package without PREV"
        assert (pref.ref.revision is not None), "Cannot upload a package without RREV"

        try:
            # TODO: It is a bit ugly, interface-wise to ask for revisions to check existence
            server_revisions = self._remote_manager.get_package_revisions(pref, remote)
            assert pref.revision == server_revisions[0]["revision"]
            assert len(server_revisions) == 1
        except NotFoundException:
            pass
        else:
            if policy == UPLOAD_POLICY_FORCE:
                self._progress_output.info("{} already in server, forcing upload".format(repr(pref)))
            else:
                self._progress_output.info("{} already in server, skipping upload".format(repr(pref)))
                return

        ref_layout = self._cache.ref_layout(pref.ref)
        conanfile_path = ref_layout.conanfile()
        self._hook_manager.execute("pre_upload_package", conanfile_path=conanfile_path,
                                   reference=pref.ref,
                                   package_id=pref.package_id,
                                   remote=remote)

        t1 = time.time()
        cache_files = self._preparator.prepare_package(pref, integrity_check, policy, remote)
        if policy == UPLOAD_POLICY_SKIP:
            return None

        self._remote_manager.upload_package(pref, cache_files, remote, retry, retry_wait)
        logger.debug("UPLOAD: Time upload package: %f" % (time.time() - t1))

        duration = time.time() - t1
        log_package_upload(pref, duration, cache_files, remote)
        self._hook_manager.execute("post_upload_package", conanfile_path=conanfile_path,
                                   reference=pref.ref, package_id=pref.package_id, remote=remote)
        logger.debug("UPLOAD: Time uploader upload_package: %f" % (time.time() - t1))


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
