import os
import stat
import tarfile
import time
import traceback
from collections import defaultdict
from multiprocessing.pool import ThreadPool

from conans.cli.output import ConanOutput
from conans.client.userio import UserInput
from conans.util import progress_bar
from conans.util.env_reader import get_env
from conans.util.progress_bar import left_justify_message
from conans.client.remote_manager import is_package_snapshot_complete
from conans.client.source import retrieve_exports_sources
from conans.errors import ConanException, NotFoundException, RecipeNotFoundException
from conans.model.manifest import gather_files, FileTreeManifest
from conans.model.ref import ConanFileReference, PackageReference, check_valid_ref
from conans.paths import (CONAN_MANIFEST, CONANFILE, EXPORT_SOURCES_TGZ_NAME,
                          EXPORT_TGZ_NAME, PACKAGE_TGZ_NAME, CONANINFO)
from conans.search.search import search_recipes
from conans.util.files import (load, clean_dirty, is_dirty,
                               gzopen_without_timestamps, set_dirty_context_manager)
from conans.util.log import logger
from conans.util.tracer import log_recipe_upload, log_compressed_files, log_package_upload
from conans.tools import cpu_count


UPLOAD_POLICY_FORCE = "force-upload"
UPLOAD_POLICY_NO_OVERWRITE = "no-overwrite"
UPLOAD_POLICY_NO_OVERWRITE_RECIPE = "no-overwrite-recipe"
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

    def collect(self, package_id, reference_or_pattern, confirm, remotes, all_packages, query):
        refs, confirm = self._collects_refs_to_upload(package_id, reference_or_pattern, confirm)
        refs_by_remote = self._collect_packages_to_upload(refs, confirm, remotes, all_packages,
                                                          query, package_id)
        return refs_by_remote

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

    def _collect_packages_to_upload(self, refs, confirm, remotes, all_packages, query, package_id):
        """ compute the references with revisions and the package_ids to be uploaded
        """
        # Group recipes by remote
        refs_by_remote = defaultdict(list)

        for ref in refs:
            # TODO: cache2.0. For 2.0 we should always specify the revision of the reference
            #  that we want to upload, check if  we should move this to other place
            # get the latest revision for the reference
            remote = remotes.selected
            if remote:
                ref_remote = remote
            else:
                # FIXME: The ref has already been obtained before, no sense to ask for latest
                rrev = self._cache.get_latest_rrev(ref)
                ref_remote = self._cache.get_remote(rrev) if rrev else None
                ref_remote = remotes.get_remote(ref_remote)

            upload = True
            if not confirm:
                msg = "Are you sure you want to upload '%s' to '%s'?" % (str(ref), ref_remote.name)
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
                    for pkg_id in self._cache.get_package_ids(ref):
                        packages_ids.append(self._cache.get_latest_prev(pkg_id))

                elif package_id:
                    # TODO: cache2.0 if we specify a package id we could have multiple package revisions
                    #  something like: upload pkg/1.0:pkg_id will upload the package id for the latest prev
                    #  or for all of them
                    prev = package_id.split("#")[1] if "#" in package_id else ""
                    package_id = package_id.split("#")[0]
                    pref = PackageReference(ref, package_id, prev)
                    # FIXME: The name is package_ids but we pass the latest prev for each package id
                    packages_ids = []
                    packages = [pref] if pref.revision else self._cache.get_package_ids(pref)
                    for pkg in packages:
                        latest_prev = self._cache.get_latest_prev(pkg) if pkg.id == package_id else None
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
                    package_id, package_revision = package.id, package.revision
                    assert package_revision is not None, "PREV cannot be None to upload"
                    prefs.append(PackageReference(ref, package_id, package_revision))
                refs_by_remote[ref_remote].append((ref, conanfile, prefs))

        return refs_by_remote


class _PackagePreparator(object):
    def __init__(self, cache, remote_manager, hook_manager):
        self._cache = cache
        self._remote_manager = remote_manager
        self._output = ConanOutput()
        self._hook_manager = hook_manager

    def prepare_recipe(self, ref, conanfile, remote, remotes, policy):
        """ do a bunch of things that are necessary before actually executing the upload:
        - retrieve exports_sources to complete the recipe if necessary
        - compress the artifacts in conan_export.tgz and conan_export_sources.tgz
        - check if package is ok to be uploaded, if scm info missing, will raise
        - check if the remote recipe is newer, raise
        - compare and decide which files need to be uploaded (and deleted from server)
        """
        recipe_layout = self._cache.ref_layout(ref)
        current_remote_name = self._cache.get_remote(ref)

        if remote.name != current_remote_name:
            retrieve_exports_sources(self._remote_manager, self._cache, recipe_layout, conanfile,
                                     ref, remotes)

        conanfile_path = recipe_layout.conanfile()
        self._hook_manager.execute("pre_upload_recipe", conanfile_path=conanfile_path,
                                   reference=ref, remote=remote)

        t1 = time.time()
        cache_files = self._compress_recipe_files(recipe_layout, ref)

        local_manifest = FileTreeManifest.loads(load(cache_files["conanmanifest.txt"]))

        remote_manifest = None
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

            remote_manifest = self._check_recipe_date(ref, remote, local_manifest)

        if policy == UPLOAD_POLICY_SKIP:
            return

        files_to_upload, deleted = self._recipe_files_to_upload(ref, policy, cache_files, remote,
                                                                remote_manifest, local_manifest)
        return (files_to_upload, deleted, cache_files, conanfile_path, t1, current_remote_name,
                recipe_layout)

    def _check_recipe_date(self, ref, remote, local_manifest):
        try:
            remote_recipe_manifest, ref = self._remote_manager.get_recipe_manifest(ref, remote)
        except NotFoundException:
            return  # First time uploading this package

        if (remote_recipe_manifest != local_manifest and
                remote_recipe_manifest.time > local_manifest.time):
            self._print_manifest_information(remote_recipe_manifest, local_manifest, ref, remote)
            raise ConanException("Remote recipe is newer than local recipe: "
                                 "\n Remote date: %s\n Local date: %s" %
                                 (remote_recipe_manifest.time, local_manifest.time))

        return remote_recipe_manifest

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

    def _recipe_files_to_upload(self, ref, policy, files, remote, remote_manifest, local_manifest):
        self._remote_manager.check_credentials(remote)
        remote_snapshot = self._remote_manager.get_recipe_snapshot(ref, remote)
        if not remote_snapshot:
            return files, set()

        deleted = set(remote_snapshot).difference(files)
        if policy != UPLOAD_POLICY_FORCE:
            if remote_manifest is None:
                # This is the weird scenario, we have a snapshot but don't have a manifest.
                # Can be due to concurrency issues, so we can try retrieve it now
                try:
                    remote_manifest, _ = self._remote_manager.get_recipe_manifest(ref, remote)
                except NotFoundException:
                    # This is weird, the manifest still not there, better upload everything
                    self._output.warning("The remote recipe doesn't have the 'conanmanifest.txt' "
                                         "file and will be uploaded: '{}'".format(ref))
                    return files, deleted

            if remote_manifest == local_manifest:
                return None, None

            if policy in (UPLOAD_POLICY_NO_OVERWRITE, UPLOAD_POLICY_NO_OVERWRITE_RECIPE):
                raise ConanException("Local recipe is different from the remote recipe. "
                                     "Forbidden overwrite.")

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
        files_to_upload, deleted = self._package_files_to_upload(pref, policy, cache_files, p_remote)
        return files_to_upload, deleted, cache_files

    def _compress_package_files(self, layout, pref, integrity_check):
        t1 = time.time()

        if layout.package_is_dirty():
            raise ConanException("Package %s is corrupted, aborting upload.\n"
                                 "Remove it with 'conan remove %s -p=%s'"
                                 % (pref, pref.ref, pref.id))

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

    def _package_files_to_upload(self, pref, policy, the_files, remote):
        self._remote_manager.check_credentials(remote)
        remote_snapshot = self._remote_manager.get_package_snapshot(pref, remote)

        if remote_snapshot and policy != UPLOAD_POLICY_FORCE:
            if not is_package_snapshot_complete(remote_snapshot):
                return the_files, set()
            remote_manifest, _ = self._remote_manager.get_package_manifest(pref, remote)
            local_manifest = FileTreeManifest.loads(load(the_files["conanmanifest.txt"]))
            if remote_manifest == local_manifest:
                return None, None
            if policy == UPLOAD_POLICY_NO_OVERWRITE:
                raise ConanException("Local package is different from the remote package. Forbidden"
                                     " overwrite.")
        deleted = set(remote_snapshot).difference(the_files)
        return the_files, deleted


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
    - get_package_snapshot() to do the diff and know what files to upload
    - get_recipe_manifest() to check the date and raise if policy requires
    - get_package_manifest() to raise if policy!=force and manifests change
    """
    def __init__(self, cache, remote_manager, loader, hook_manager):
        self._cache = cache
        self._progress_output = progress_bar.ProgressOutput(ConanOutput())
        self._remote_manager = remote_manager
        self._loader = loader
        self._hook_manager = hook_manager
        self._upload_thread_pool = None
        self._exceptions_list = []
        self._preparator = _PackagePreparator(cache, remote_manager, hook_manager)
        self._user_input = UserInput(self._cache.config.non_interactive)

    def upload(self, reference_or_pattern, remotes, upload_recorder, package_id=None,
               all_packages=None, confirm=False, retry=None, retry_wait=None, integrity_check=False,
               policy=None, query=None, parallel_upload=False):
        t1 = time.time()

        collecter = _UploadCollecter(self._cache, self._loader)
        refs_by_remote = collecter.collect(package_id, reference_or_pattern, confirm, remotes,
                                           all_packages, query)

        if parallel_upload:
            self._cache.config.non_interactive = True
        self._upload_thread_pool = ThreadPool(
            cpu_count() if parallel_upload else 1)

        for remote, refs in refs_by_remote.items():
            self._progress_output.info("Uploading to remote '{}':".format(remote.name))

            def upload_ref(ref_conanfile_prefs):
                _ref, _conanfile, _prefs = ref_conanfile_prefs
                try:
                    self._upload_ref(_conanfile, _ref, _prefs, retry, retry_wait,
                                     integrity_check, policy, remote, upload_recorder, remotes)
                except BaseException as base_exception:
                    base_trace = traceback.format_exc()
                    self._exceptions_list.append((base_exception, _ref, base_trace, remote))

            self._upload_thread_pool.map(upload_ref,
                                         [(ref, conanfile, prefs) for (ref, conanfile, prefs) in
                                          refs])

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

    def _upload_ref(self, conanfile, ref, prefs, retry, retry_wait, integrity_check, policy,
                    recipe_remote, upload_recorder, remotes):
        """ Uploads the recipes and binaries identified by ref
        """
        assert (ref.revision is not None), "Cannot upload a recipe without RREV"
        conanfile_path = self._cache.ref_layout(ref).conanfile()
        # FIXME: I think it makes no sense to specify a remote to "pre_upload"
        # FIXME: because the recipe can have one and the package a different one
        self._hook_manager.execute("pre_upload", conanfile_path=conanfile_path,
                                   reference=ref, remote=recipe_remote)
        msg = "\rUploading %s to remote '%s'" % (str(ref), recipe_remote.name)
        self._progress_output.info(left_justify_message(msg))
        self._upload_recipe(ref, conanfile, retry, retry_wait, policy, recipe_remote, remotes)
        upload_recorder.add_recipe(ref, recipe_remote.name, recipe_remote.url)

        # Now the binaries
        if prefs:
            total = len(prefs)
            p_remote = recipe_remote

            def upload_package_index(index_pref):
                index, pref = index_pref
                try:
                    up_msg = "\rUploading package %d/%d: %s to '%s'" % (index + 1, total,
                                                                        str(pref.id),
                                                                        p_remote.name)
                    self._progress_output.info(left_justify_message(up_msg))
                    self._upload_package(pref, retry, retry_wait, integrity_check, policy, p_remote)
                    upload_recorder.add_package(pref, p_remote.name, p_remote.url)
                except BaseException as pkg_exc:
                    trace = traceback.format_exc()
                    return pkg_exc, pref, trace, p_remote

            def upload_package_callback(ret):
                package_exceptions = [r for r in ret if r is not None]
                self._exceptions_list.extend(package_exceptions)
                if not package_exceptions:
                    # FIXME: I think it makes no sense to specify a remote to "post_upload"
                    # FIXME: because the recipe can have one and the package a different one
                    self._hook_manager.execute("post_upload", conanfile_path=conanfile_path,
                                               reference=ref, remote=recipe_remote)

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
                                       remote=recipe_remote)

    def _upload_recipe(self, ref, conanfile, retry, retry_wait, policy, remote, remotes):
        prep = self._preparator.prepare_recipe(ref, conanfile, remote, remotes, policy)

        if policy == UPLOAD_POLICY_SKIP:
            return ref

        files_to_upload, deleted, cache_files, conanfile_path, t1, current_remote_name, layout = prep
        if files_to_upload or deleted:
            self._remote_manager.upload_recipe(ref, files_to_upload, deleted, remote, retry,
                                               retry_wait)
            msg = "\rUploaded conan recipe '%s' to '%s': %s" % (str(ref), remote.name, remote.url)
            self._progress_output.info(left_justify_message(msg))
        else:
            self._progress_output.info("Recipe is up to date, upload skipped")
        duration = time.time() - t1
        log_recipe_upload(ref, duration, cache_files, remote.name)
        self._hook_manager.execute("post_upload_recipe", conanfile_path=conanfile_path,
                                   reference=ref, remote=remote)

        # The recipe wasn't in the registry or it has changed the revision field only
        if not current_remote_name:
            self._cache.set_remote(ref, remote.name)

        return ref

    def _upload_package(self, pref, retry=None, retry_wait=None, integrity_check=False,
                        policy=None, p_remote=None):

        assert (pref.revision is not None), "Cannot upload a package without PREV"
        assert (pref.ref.revision is not None), "Cannot upload a package without RREV"

        ref_layout = self._cache.ref_layout(pref.ref)
        conanfile_path = ref_layout.conanfile()
        self._hook_manager.execute("pre_upload_package", conanfile_path=conanfile_path,
                                   reference=pref.ref,
                                   package_id=pref.id,
                                   remote=p_remote)

        t1 = time.time()
        prep = self._preparator.prepare_package(pref, integrity_check, policy, p_remote)
        if policy == UPLOAD_POLICY_SKIP:
            return None
        files_to_upload, deleted, cache_files = prep

        if files_to_upload or deleted:
            self._remote_manager.upload_package(pref, files_to_upload, deleted, p_remote, retry,
                                                retry_wait)
            logger.debug("UPLOAD: Time upload package: %f" % (time.time() - t1))
        else:
            self._progress_output.info("Package is up to date, upload skipped")

        duration = time.time() - t1
        log_package_upload(pref, duration, cache_files, p_remote)
        self._hook_manager.execute("post_upload_package", conanfile_path=conanfile_path,
                                   reference=pref.ref, package_id=pref.id, remote=p_remote)

        logger.debug("UPLOAD: Time uploader upload_package: %f" % (time.time() - t1))

        cur_package_remote = self._cache.get_remote(pref)
        if not cur_package_remote:
            self._cache.set_remote(pref, p_remote.name)
        return pref


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
