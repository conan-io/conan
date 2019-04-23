import os
import stat
import tarfile
import time
from collections import defaultdict

from conans.client.remote_manager import is_package_snapshot_complete
from conans.client.source import complete_recipe_sources
from conans.errors import ConanException, NotFoundException
from conans.model.manifest import gather_files, FileTreeManifest
from conans.model.ref import ConanFileReference, PackageReference, check_valid_ref
from conans.paths import (CONAN_MANIFEST, CONANFILE, EXPORT_SOURCES_TGZ_NAME,
                          EXPORT_TGZ_NAME, PACKAGE_TGZ_NAME, CONANINFO)
from conans.search.search import search_packages, search_recipes
from conans.util.files import (load, clean_dirty, is_dirty,
                               gzopen_without_timestamps, set_dirty)
from conans.util.log import logger
from conans.util.tracer import (log_recipe_upload, log_compressed_files,
                                log_package_upload)


UPLOAD_POLICY_FORCE = "force-upload"
UPLOAD_POLICY_NO_OVERWRITE = "no-overwrite"
UPLOAD_POLICY_NO_OVERWRITE_RECIPE = "no-overwrite-recipe"
UPLOAD_POLICY_SKIP = "skip-upload"


class CmdUpload(object):
    """ This class is responsible for uploading packages to remotes. The flow is:
    - Collect all the data from the local cache:
        - Collect the refs that matches the given pattern _collect_refs_to_upload
        - Collect for every ref all the binaries IDs that has to be uploaded
          "_collect_packages_to_upload". This may discard binaries that do not
          belong to the current RREV
        The collection of this does the interactivity (ask user if yes/no),
        the errors (don't upload packages with policy=build_always, and computing
        the full REVISIONS for every that has to be uploaded.
        No remote API calls are done in this step, everything is local
    - Execute the upload. For every ref:
        - Upload the recipe of the ref: "_upload_recipe"
            - If not FORCE, check the date "_check_recipe_date", i.e. if there are
              changes, do not allow uploading if the remote date is newer than the
              local cache one
            - Retrieve the sources (exports_sources), if they are not cached, and
              uploading to a different remote. "complete_recipe_sources"
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
    def __init__(self, cache, user_io, remote_manager, loader, hook_manager):
        self._cache = cache
        self._user_io = user_io
        self._remote_manager = remote_manager
        self._registry = cache.registry
        self._loader = loader
        self._hook_manager = hook_manager

    def upload(self, upload_recorder, reference_or_pattern, package_id=None, all_packages=None,
               confirm=False, retry=0, retry_wait=0, integrity_check=False, policy=None,
               remote_name=None, query=None):
        t1 = time.time()
        refs, confirm = self._collects_refs_to_upload(package_id, reference_or_pattern, confirm)
        refs_by_remote = self._collect_packages_to_upload(refs, confirm, remote_name, all_packages,
                                                          query, package_id)
        # Do the job
        for remote, refs in refs_by_remote.items():
            self._user_io.out.info("Uploading to remote '{}':".format(remote.name))
            for (ref, conanfile, prefs) in refs:
                self._upload_ref(conanfile, ref, prefs, retry, retry_wait,
                                 integrity_check, policy, remote, upload_recorder)

        logger.debug("UPLOAD: Time manager upload: %f" % (time.time() - t1))

    def _collects_refs_to_upload(self, package_id, reference_or_pattern, confirm):
        """ validate inputs and compute the refs (without revisions) to be uploaded
        """
        if package_id and not check_valid_ref(reference_or_pattern, allow_pattern=False):
            raise ConanException("-p parameter only allowed with a valid recipe reference, "
                                 "not with a pattern")

        if package_id or check_valid_ref(reference_or_pattern, allow_pattern=False):
            # Upload package
            ref = ConanFileReference.loads(reference_or_pattern)
            refs = [ref, ]
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
        refs_by_remote = defaultdict(list)
        default_remote = (self._registry.remotes.get(remote_name) if remote_name else
                          self._registry.remotes.default)

        for ref in refs:
            metadata = self._cache.package_layout(ref).load_metadata()
            ref = ref.copy_with_rev(metadata.recipe.revision)
            if not remote_name:
                remote = self._registry.refs.get(ref) or default_remote
            else:
                remote = default_remote

            upload = True
            if not confirm:
                msg = "Are you sure you want to upload '%s' to '%s'?" % (str(ref), remote.name)
                upload = self._user_io.request_boolean(msg)
            if upload:
                try:
                    conanfile_path = self._cache.conanfile(ref)
                    conanfile = self._loader.load_class(conanfile_path)
                except NotFoundException:
                    raise NotFoundException(("There is no local conanfile exported as %s" %
                                             str(ref)))

                # TODO: This search of binary packages has to be improved, more robust
                # So only real packages are retrieved
                if all_packages or query:
                    if all_packages:
                        query = None
                    # better to do a search, that will retrieve real packages with ConanInfo
                    # Not only "package_id" folders that could be empty
                    package_layout = self._cache.package_layout(ref.copy_clear_rev())
                    packages = search_packages(package_layout, query)
                    packages_ids = list(packages.keys())
                elif package_id:
                    packages_ids = [package_id, ]
                else:
                    packages_ids = []
                if packages_ids:
                    if conanfile.build_policy == "always":
                        raise ConanException("Conanfile '%s' has build_policy='always', "
                                             "no packages can be uploaded" % str(ref))
                prefs = []
                # Gather all the complete PREFS with PREV
                for package_id in packages_ids:
                    if package_id not in metadata.packages:
                        raise ConanException("Binary package %s:%s not found"
                                             % (str(ref), package_id))
                    # Filter packages that don't match the recipe revision
                    if self._cache.config.revisions_enabled and ref.revision:
                        rec_rev = metadata.packages[package_id].recipe_revision
                        if ref.revision != rec_rev:
                            self._user_io.out.warn("Skipping package '%s', it doesn't belong to the "
                                                   "current recipe revision" % package_id)
                            continue
                    package_revision = metadata.packages[package_id].revision
                    assert package_revision is not None, "PREV cannot be None to upload"
                    prefs.append(PackageReference(ref, package_id, package_revision))
                refs_by_remote[remote].append((ref, conanfile, prefs))

        return refs_by_remote

    def _upload_ref(self, conanfile, ref, prefs, retry, retry_wait, integrity_check, policy,
                    recipe_remote, upload_recorder):
        """ Uploads the recipes and binaries identified by ref
        """
        assert (ref.revision is not None), "Cannot upload a recipe without RREV"
        conanfile_path = self._cache.conanfile(ref)
        # FIXME: I think it makes no sense to specify a remote to "pre_upload"
        # FIXME: because the recipe can have one and the package a different one
        self._hook_manager.execute("pre_upload", conanfile_path=conanfile_path,
                                   reference=ref, remote=recipe_remote)

        self._user_io.out.info("Uploading %s to remote '%s'" % (str(ref), recipe_remote.name))
        self._upload_recipe(ref, conanfile, retry, retry_wait, policy, recipe_remote)
        upload_recorder.add_recipe(ref, recipe_remote.name, recipe_remote.url)

        # Now the binaries
        if prefs:
            total = len(prefs)
            for index, pref in enumerate(prefs):
                p_remote = recipe_remote
                msg = ("Uploading package %d/%d: %s to '%s'" % (index+1, total, str(pref.id),
                                                                p_remote.name))
                self._user_io.out.info(msg)
                self._upload_package(pref, retry, retry_wait,
                                     integrity_check, policy, p_remote)
                upload_recorder.add_package(pref, p_remote.name, p_remote.url)

        # FIXME: I think it makes no sense to specify a remote to "post_upload"
        # FIXME: because the recipe can have one and the package a different one
        self._hook_manager.execute("post_upload", conanfile_path=conanfile_path, reference=ref,
                                   remote=recipe_remote)

    def _upload_recipe(self, ref, conanfile, retry, retry_wait, policy, remote):
        current_remote = self._registry.refs.get(ref)
        if remote != current_remote:
            complete_recipe_sources(self._remote_manager, self._cache, conanfile, ref)

        conanfile_path = self._cache.conanfile(ref)
        self._hook_manager.execute("pre_upload_recipe", conanfile_path=conanfile_path,
                                   reference=ref, remote=remote)

        t1 = time.time()
        the_files = self._compress_recipe_files(ref)
        local_manifest = FileTreeManifest.loads(load(the_files["conanmanifest.txt"]))

        remote_manifest = None
        if policy != UPLOAD_POLICY_FORCE:
            remote_manifest = self._check_recipe_date(ref, remote, local_manifest)
        if policy == UPLOAD_POLICY_SKIP:
            return ref

        files_to_upload, deleted = self._recipe_files_to_upload(ref, policy, the_files,
                                                                remote, remote_manifest,
                                                                local_manifest)

        if files_to_upload or deleted:
            self._remote_manager.upload_recipe(ref, files_to_upload, deleted,
                                               remote, retry, retry_wait)
            self._upload_recipe_end_msg(ref, remote)
        else:
            self._user_io.out.info("Recipe is up to date, upload skipped")
        duration = time.time() - t1
        log_recipe_upload(ref, duration, the_files, remote.name)
        self._hook_manager.execute("post_upload_recipe", conanfile_path=conanfile_path,
                                   reference=ref, remote=remote)

        # The recipe wasn't in the registry or it has changed the revision field only
        if not current_remote:
            self._registry.refs.set(ref, remote.name)

        return ref

    def _upload_package(self, pref, retry=None, retry_wait=None, integrity_check=False,
                        policy=None, p_remote=None):

        assert (pref.revision is not None), "Cannot upload a package without PREV"
        assert (pref.ref.revision is not None), "Cannot upload a package without RREV"

        conanfile_path = self._cache.conanfile(pref.ref)
        self._hook_manager.execute("pre_upload_package", conanfile_path=conanfile_path,
                                   reference=pref.ref,
                                   package_id=pref.id,
                                   remote=p_remote)

        t1 = time.time()
        the_files = self._compress_package_files(pref, integrity_check)
        if policy == UPLOAD_POLICY_SKIP:
            return None
        files_to_upload, deleted = self._package_files_to_upload(pref, policy, the_files, p_remote)

        if files_to_upload or deleted:
            self._remote_manager.upload_package(pref, files_to_upload, deleted, p_remote, retry,
                                                retry_wait)
            logger.debug("UPLOAD: Time upload package: %f" % (time.time() - t1))
        else:
            self._user_io.out.info("Package is up to date, upload skipped")

        duration = time.time() - t1
        log_package_upload(pref, duration, the_files, p_remote)
        self._hook_manager.execute("post_upload_package", conanfile_path=conanfile_path,
                                   reference=pref.ref, package_id=pref.id, remote=p_remote)

        logger.debug("UPLOAD: Time uploader upload_package: %f" % (time.time() - t1))
        cur_package_remote = self._registry.prefs.get(pref.copy_clear_rev())
        if not cur_package_remote and policy != UPLOAD_POLICY_SKIP:
            self._registry.prefs.set(pref, p_remote.name)

        return pref

    def _compress_recipe_files(self, ref):
        export_folder = self._cache.export(ref)

        for f in (EXPORT_TGZ_NAME, EXPORT_SOURCES_TGZ_NAME):
            tgz_path = os.path.join(export_folder, f)
            if is_dirty(tgz_path):
                self._user_io.out.warn("%s: Removing %s, marked as dirty" % (str(ref), f))
                os.remove(tgz_path)
                clean_dirty(tgz_path)

        files, symlinks = gather_files(export_folder)
        if CONANFILE not in files or CONAN_MANIFEST not in files:
            raise ConanException("Cannot upload corrupted recipe '%s'" % str(ref))
        export_src_folder = self._cache.export_sources(ref, short_paths=None)
        src_files, src_symlinks = gather_files(export_src_folder)
        the_files = _compress_recipe_files(files, symlinks, src_files, src_symlinks, export_folder,
                                           self._user_io.out)
        return the_files

    def _compress_package_files(self, pref, integrity_check):

        t1 = time.time()
        # existing package, will use short paths if defined
        package_folder = self._cache.package(pref, short_paths=None)

        if is_dirty(package_folder):
            raise ConanException("Package %s is corrupted, aborting upload.\n"
                                 "Remove it with 'conan remove %s -p=%s'"
                                 % (pref, pref.ref, pref.id))
        tgz_path = os.path.join(package_folder, PACKAGE_TGZ_NAME)
        if is_dirty(tgz_path):
            self._user_io.out.warn("%s: Removing %s, marked as dirty"
                                   % (str(pref), PACKAGE_TGZ_NAME))
            os.remove(tgz_path)
            clean_dirty(tgz_path)
        # Get all the files in that directory
        files, symlinks = gather_files(package_folder)

        if CONANINFO not in files or CONAN_MANIFEST not in files:
            logger.error("Missing info or manifest in uploading files: %s" % (str(files)))
            raise ConanException("Cannot upload corrupted package '%s'" % str(pref))

        logger.debug("UPLOAD: Time remote_manager build_files_set : %f" % (time.time() - t1))
        if integrity_check:
            self._package_integrity_check(pref, files, package_folder)
            logger.debug("UPLOAD: Time remote_manager check package integrity : %f"
                         % (time.time() - t1))

        the_files = _compress_package_files(files, symlinks, package_folder, self._user_io.out)
        return the_files

    def _recipe_files_to_upload(self, ref, policy, the_files, remote, remote_manifest,
                                local_manifest):
        self._remote_manager.check_credentials(remote)
        remote_snapshot = self._remote_manager.get_recipe_snapshot(ref, remote)
        files_to_upload = {filename.replace("\\", "/"): path
                           for filename, path in the_files.items()}
        if not remote_snapshot:
            return files_to_upload, set()

        deleted = set(remote_snapshot).difference(the_files)
        if policy != UPLOAD_POLICY_FORCE:
            if remote_manifest is None:
                # This is the weird scenario, we have a snapshot but don't have a manifest.
                # Can be due to concurrency issues, so we can try retrieve it now
                try:
                    remote_manifest, _ = self._remote_manager.get_recipe_manifest(ref, remote)
                except NotFoundException:
                    # This is weird, the manifest still not there, better upload everything
                    self._user_io.out.warn("The remote recipe doesn't have the 'conanmanifest.txt' "
                                           "file and will be uploaded: '{}'".format(ref))
                    return files_to_upload, deleted

            if remote_manifest == local_manifest:
                return None, None

            if policy in (UPLOAD_POLICY_NO_OVERWRITE, UPLOAD_POLICY_NO_OVERWRITE_RECIPE):
                raise ConanException("Local recipe is different from the remote recipe. "
                                     "Forbidden overwrite.")

        return files_to_upload, deleted

    def _package_files_to_upload(self, pref, policy, the_files, remote):
        self._remote_manager.check_credentials(remote)
        remote_snapshot = self._remote_manager.get_package_snapshot(pref, remote)

        if remote_snapshot:
            if not is_package_snapshot_complete(remote_snapshot):
                return the_files, set([])
            remote_manifest, _ = self._remote_manager.get_package_manifest(pref, remote)
            local_manifest = FileTreeManifest.loads(load(the_files["conanmanifest.txt"]))
            if remote_manifest == local_manifest:
                return None, None
            if policy == UPLOAD_POLICY_NO_OVERWRITE:
                raise ConanException("Local package is different from the remote package. Forbidden "
                                     "overwrite.")
        deleted = set(remote_snapshot).difference(the_files)
        return the_files, deleted

    def _upload_recipe_end_msg(self, ref, remote):
        msg = "Uploaded conan recipe '%s' to '%s'" % (str(ref), remote.name)
        url = remote.url.replace("https://api.bintray.com/conan", "https://bintray.com")
        msg += ": %s" % url
        self._user_io.out.info(msg)

    def _package_integrity_check(self, pref, files, package_folder):
        # If package has been modified remove tgz to regenerate it
        self._user_io.out.rewrite_line("Checking package integrity...")

        # short_paths = None is enough if there exist short_paths
        layout = self._cache.package_layout(pref.ref, short_paths=None)
        read_manifest, expected_manifest = layout.package_manifests(pref)

        if read_manifest != expected_manifest:
            self._user_io.out.writeln("")
            diff = read_manifest.difference(expected_manifest)
            for fname, (h1, h2) in diff.items():
                self._user_io.out.warn("Mismatched checksum '%s' (manifest: %s, file: %s)"
                                       % (fname, h1, h2))

            if PACKAGE_TGZ_NAME in files:
                try:
                    tgz_path = os.path.join(package_folder, PACKAGE_TGZ_NAME)
                    os.unlink(tgz_path)
                except Exception:
                    pass
            error_msg = os.linesep.join("Mismatched checksum '%s' (manifest: %s, file: %s)"
                                        % (fname, h1, h2) for fname, (h1, h2) in diff.items())
            logger.error("Manifests doesn't match!\n%s" % error_msg)
            raise ConanException("Cannot upload corrupted package '%s'" % str(pref))
        else:
            self._user_io.out.rewrite_line("Package integrity OK!")
        self._user_io.out.writeln("")

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
            self._user_io.out.info("\n%s" % ("-"*40))
            self._user_io.out.info("Remote manifest:")
            self._user_io.out.info(remote_recipe_manifest)
            self._user_io.out.info("Local manifest:")
            self._user_io.out.info(local_manifest)
            difference = remote_recipe_manifest.difference(local_manifest)
            if "conanfile.py" in difference:
                contents = load(os.path.join(self._cache.export(ref), "conanfile.py"))
                endlines = "\\r\\n" if "\r\n" in contents else "\\n"
                self._user_io.out.info("Local 'conanfile.py' using '%s' line-ends" % endlines)
                remote_contents = self._remote_manager.get_recipe_path(ref, path="conanfile.py",
                                                                       remote=remote)
                endlines = "\\r\\n" if "\r\n" in remote_contents else "\\n"
                self._user_io.out.info("Remote 'conanfile.py' using '%s' line-ends" % endlines)
            self._user_io.out.info("\n%s" % ("-"*40))
        except Exception as e:
            self._user_io.out.info("Error printing information about the diff: %s" % str(e))


def _compress_recipe_files(files, symlinks, src_files, src_symlinks, dest_folder, output):
    # This is the minimum recipe
    result = {CONANFILE: files.pop(CONANFILE),
              CONAN_MANIFEST: files.pop(CONAN_MANIFEST)}

    export_tgz_path = files.pop(EXPORT_TGZ_NAME, None)
    sources_tgz_path = files.pop(EXPORT_SOURCES_TGZ_NAME, None)

    def add_tgz(tgz_name, tgz_path, tgz_files, tgz_symlinks, msg):
        if tgz_path:
            result[tgz_name] = tgz_path
        elif tgz_files:
            output.rewrite_line(msg)
            tgz_path = compress_files(tgz_files, tgz_symlinks, tgz_name, dest_folder, output)
            result[tgz_name] = tgz_path

    add_tgz(EXPORT_TGZ_NAME, export_tgz_path, files, symlinks, "Compressing recipe...")
    add_tgz(EXPORT_SOURCES_TGZ_NAME, sources_tgz_path, src_files, src_symlinks,
            "Compressing recipe sources...")

    return result


def _compress_package_files(files, symlinks, dest_folder, output):
    tgz_path = files.get(PACKAGE_TGZ_NAME)
    if not tgz_path:
        output.writeln("Compressing package...")
        tgz_files = {f: path for f, path in files.items() if f not in [CONANINFO, CONAN_MANIFEST]}
        tgz_path = compress_files(tgz_files, symlinks, PACKAGE_TGZ_NAME, dest_folder, output)

    return {PACKAGE_TGZ_NAME: tgz_path,
            CONANINFO: files[CONANINFO],
            CONAN_MANIFEST: files[CONAN_MANIFEST]}


def compress_files(files, symlinks, name, dest_dir, output=None):
    t1 = time.time()
    # FIXME, better write to disk sequentially and not keep tgz contents in memory
    tgz_path = os.path.join(dest_dir, name)
    set_dirty(tgz_path)
    with open(tgz_path, "wb") as tgz_handle:
        # tgz_contents = BytesIO()
        tgz = gzopen_without_timestamps(name, mode="w", fileobj=tgz_handle)

        for filename, dest in sorted(symlinks.items()):
            info = tarfile.TarInfo(name=filename)
            info.type = tarfile.SYMTYPE
            info.linkname = dest
            tgz.addfile(tarinfo=info)

        mask = ~(stat.S_IWOTH | stat.S_IWGRP)
        i_file = 0
        n_files = len(files)
        last_progress = None
        if output and n_files > 1 and not output.is_terminal:
            output.write("[")
        for filename, abs_path in sorted(files.items()):
            info = tarfile.TarInfo(name=filename)
            info.size = os.stat(abs_path).st_size
            info.mode = os.stat(abs_path).st_mode & mask
            if os.path.islink(abs_path):
                info.type = tarfile.SYMTYPE
                info.linkname = os.readlink(abs_path)  # @UndefinedVariable
                tgz.addfile(tarinfo=info)
            else:
                with open(abs_path, 'rb') as file_handler:
                    tgz.addfile(tarinfo=info, fileobj=file_handler)
            if output and n_files > 1:
                i_file = i_file + 1
                units = min(50, int(50 * i_file / n_files))
                if last_progress != units:  # Avoid screen refresh if nothing has change
                    if output.is_terminal:
                        text = "%s/%s files" % (i_file, n_files)
                        output.rewrite_line("[%s%s] %s" % ('=' * units, ' ' * (50 - units), text))
                    else:
                        output.write('=' * (units - (last_progress or 0)))
                    last_progress = units

        if output and n_files > 1:
            if output.is_terminal:
                output.writeln("")
            else:
                output.writeln("]")
        tgz.close()

    clean_dirty(tgz_path)
    duration = time.time() - t1
    log_compressed_files(files, duration, tgz_path)

    return tgz_path
