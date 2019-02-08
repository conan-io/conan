import os
from collections import defaultdict

import time

from conans.client.source import complete_recipe_sources
from conans.errors import ConanException, NotFoundException
from conans.model.ref import ConanFileReference, PackageReference, check_valid_ref
from conans.search.search import search_packages, search_recipes
from conans.util.files import load
from conans.util.log import logger

UPLOAD_POLICY_FORCE = "force-upload"
UPLOAD_POLICY_NO_OVERWRITE = "no-overwrite"
UPLOAD_POLICY_NO_OVERWRITE_RECIPE = "no-overwrite-recipe"
UPLOAD_POLICY_SKIP = "skip-upload"


class CmdUpload(object):

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
        """ If package_id is provided, reference_or_pattern is a ConanFileReference """

        if package_id and not check_valid_ref(reference_or_pattern, allow_pattern=False):
            raise ConanException("-p parameter only allowed with a valid recipe reference, "
                                 "not with a pattern")
        t1 = time.time()
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

        # Group recipes by remote
        refs_by_remote = defaultdict(list)
        default_remote = (self._registry.remotes.get(remote_name) if remote_name else
                          self._registry.remotes.default)

        for ref in refs:
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
                refs_by_remote[remote].append((ref, conanfile))

        # Do the job
        for remote, refs in refs_by_remote.items():
            self._user_io.out.info("Uploading to remote '{}':".format(remote.name))
            for (ref, conanfile) in refs:
                if all_packages:
                    packages_ids = self._cache.conan_packages(ref)
                elif query:
                    packages = search_packages(self._cache, ref, query)
                    packages_ids = list(packages.keys())
                elif package_id:
                    packages_ids = [package_id, ]
                else:
                    packages_ids = []
                self._upload(conanfile, ref, packages_ids, retry, retry_wait,
                             integrity_check, policy, remote, upload_recorder)

        logger.debug("UPLOAD: Time manager upload: %f" % (time.time() - t1))

    def _upload(self, conan_file, ref, packages_ids, retry, retry_wait,
                integrity_check, policy, recipe_remote, upload_recorder):
        """Uploads the recipes and binaries identified by conan_ref"""
        metadata = self._cache.package_layout(ref).load_metadata()
        ref = ref.copy_with_rev(metadata.recipe.revision)
        conanfile_path = self._cache.conanfile(ref)
        # FIXME: I think it makes no sense to specify a remote to "pre_upload"
        # FIXME: because the recipe can have one and the package a different one
        self._hook_manager.execute("pre_upload", conanfile_path=conanfile_path,
                                   reference=ref, remote=recipe_remote)

        if policy != UPLOAD_POLICY_FORCE:
            remote_manifest = self._check_recipe_date(ref, recipe_remote)
        else:
            remote_manifest = None

        self._user_io.out.info("Uploading %s to remote '%s'" % (str(ref), recipe_remote.name))
        self._upload_recipe(ref, retry, retry_wait, policy, recipe_remote, remote_manifest)
        upload_recorder.add_recipe(ref, recipe_remote.name, recipe_remote.url)
        if packages_ids:
            # Filter packages that don't match the recipe revision
            if self._cache.config.revisions_enabled and ref.revision:
                recipe_package_ids = []
                for package_id in packages_ids:
                    rec_rev = metadata.packages[package_id].recipe_revision
                    if ref.revision != rec_rev:
                        self._user_io.out.warn("Skipping package '%s', it doesn't belong to "
                                               "the current recipe revision" % package_id)
                    else:
                        recipe_package_ids.append(package_id)
                packages_ids = recipe_package_ids

            # Can't use build_policy_always here because it's not loaded (only load_class)
            if conan_file.build_policy == "always":
                raise ConanException("Conanfile has build_policy='always', "
                                     "no packages can be uploaded")
            total = len(packages_ids)
            for index, package_id in enumerate(packages_ids):
                p_remote = recipe_remote
                new_pref = self._upload_package(ref, package_id, metadata, index + 1, total, retry, retry_wait,
                                                integrity_check, policy, p_remote)
                upload_recorder.add_package(new_pref, p_remote.name, p_remote.url)

        # FIXME: I think it makes no sense to specify a remote to "post_upload"
        # FIXME: because the recipe can have one and the package a different one
        self._hook_manager.execute("post_upload", conanfile_path=conanfile_path, reference=ref,
                                   remote=recipe_remote)

    def _upload_recipe(self, ref, retry, retry_wait, policy, remote, remote_manifest):
        conan_file_path = self._cache.conanfile(ref)
        current_remote = self._registry.refs.get(ref)

        if remote != current_remote:
            conanfile = self._loader.load_class(conan_file_path)
            complete_recipe_sources(self._remote_manager, self._cache, conanfile, ref)
        self._remote_manager.upload_recipe(ref, remote, retry, retry_wait,
                                           policy=policy, remote_manifest=remote_manifest)

        # The recipe wasn't in the registry or it has changed the revision field only
        if not current_remote and policy != UPLOAD_POLICY_SKIP:
            self._registry.refs.set(ref, remote.name)

        return ref

    def _upload_package(self, ref, package_id, metadata, index=1, total=1, retry=None, retry_wait=None,
                        integrity_check=False, policy=None, p_remote=None):
        """Uploads the package identified by package_id"""

        msg = ("Uploading package %d/%d: %s to '%s'" % (index, total, str(package_id), p_remote.name))
        t1 = time.time()
        self._user_io.out.info(msg)

        # Read the revisions and build a correct package reference for the server
        package_revision = metadata.packages[package_id].revision
        # Copy to not modify the original with the revisions
        new_pref = PackageReference(ref, package_id, package_revision)

        assert (new_pref.revision is not None)
        assert (new_pref.ref.revision is not None)

        self._remote_manager.upload_package(new_pref, p_remote, retry, retry_wait, integrity_check,
                                            policy)
        logger.debug("UPLOAD: Time uploader upload_package: %f" % (time.time() - t1))

        cur_package_remote = self._registry.prefs.get(new_pref.copy_clear_rev())
        if not cur_package_remote and policy != UPLOAD_POLICY_SKIP:
            self._registry.prefs.set(new_pref, p_remote.name)

        return new_pref

    def _check_recipe_date(self, ref, remote):
        try:
            remote_recipe_manifest = self._remote_manager.get_conan_manifest(ref, remote)
        except NotFoundException:
            return  # First time uploading this package

        local_manifest = self._cache.package_layout(ref).load_manifest()
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
                remote_contents = self._remote_manager.get_path(ref, package_id=None,
                                                                path="conanfile.py", remote=remote)
                endlines = "\\r\\n" if "\r\n" in remote_contents else "\\n"
                self._user_io.out.info("Remote 'conanfile.py' using '%s' line-ends" % endlines)
            self._user_io.out.info("\n%s" % ("-"*40))
        except Exception as e:
            self._user_io.out.info("Error printing information about the diff: %s" % str(e))
