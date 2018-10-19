import os
import time
from conans.client.source import complete_recipe_sources
from conans.errors import ConanException, NotFoundException
from conans.model.conan_file import get_recipe_revision
from conans.model.info import ConanInfo
from conans.model.ref import PackageReference, ConanFileReference
from conans.search.search import search_recipes, search_packages
from conans.util.files import load
from conans.util.log import logger


def _is_a_reference(ref):
    try:
        ConanFileReference.loads(ref)
        return "*" not in ref  # If is a pattern, it is not a reference
    except ConanException:
        pass
    return False


UPLOAD_POLICY_FORCE = "force-upload"
UPLOAD_POLICY_NO_OVERWRITE = "no-overwrite"
UPLOAD_POLICY_NO_OVERWRITE_RECIPE = "no-overwrite-recipe"
UPLOAD_POLICY_SKIP = "skip-upload"


class CmdUpload(object):

    def __init__(self, client_cache, user_io, remote_manager, registry, loader, plugin_manager):
        self._client_cache = client_cache
        self._user_io = user_io
        self._remote_manager = remote_manager
        self._registry = registry
        self._loader = loader
        self._plugin_manager = plugin_manager

    def upload(self, recorder, reference_or_pattern, package_id=None, all_packages=None,
               confirm=False, retry=0, retry_wait=0, integrity_check=False, policy=None,
               remote_name=None, query=None):
        """If package_id is provided, conan_reference_or_pattern is a ConanFileReference"""

        if package_id and not _is_a_reference(reference_or_pattern):
            raise ConanException("-p parameter only allowed with a valid recipe reference, "
                                 "not with a pattern")
        t1 = time.time()
        if package_id or _is_a_reference(reference_or_pattern):  # Upload package
            ref = ConanFileReference.loads(reference_or_pattern)
            references = [ref, ]
            confirm = True
        else:
            references = search_recipes(self._client_cache, reference_or_pattern)
            if not references:
                raise NotFoundException(("No packages found matching pattern '%s'" %
                                         reference_or_pattern))

        for conan_ref in references:
            upload = True
            if not confirm:
                msg = "Are you sure you want to upload '%s'?" % str(conan_ref)
                upload = self._user_io.request_boolean(msg)
            if upload:
                try:
                    conanfile_path = self._client_cache.conanfile(conan_ref)
                    conan_file = self._loader.load_class(conanfile_path)
                except NotFoundException:
                    raise NotFoundException(("There is no local conanfile exported as %s" %
                                             str(conan_ref)))
                if all_packages:
                    packages_ids = self._client_cache.conan_packages(conan_ref)
                elif query:
                    packages = search_packages(self._client_cache, conan_ref, query)
                    packages_ids = list(packages.keys())
                elif package_id:
                    packages_ids = [package_id, ]
                else:
                    packages_ids = []
                self._upload(conan_file, conan_ref, packages_ids, retry, retry_wait,
                             integrity_check, policy, remote_name, recorder)

        logger.debug("====> Time manager upload: %f" % (time.time() - t1))

    def _upload(self, conan_file, conan_ref, packages_ids, retry, retry_wait,
                integrity_check, policy, remote_name, recorder):
        """Uploads the recipes and binaries identified by conan_ref"""

        default_remote = self._registry.remotes.default
        cur_recipe_remote = self._registry.refs.get(conan_ref)
        if remote_name:  # If remote_name is given, use it
            recipe_remote = self._registry.remotes.get(remote_name)
        else:
            recipe_remote = cur_recipe_remote or default_remote

        conanfile_path = self._client_cache.conanfile(conan_ref)
        # FIXME: I think it makes no sense to specify a remote to "pre_upload"
        # FIXME: because the recipe can have one and the package a different one
        self._plugin_manager.execute("pre_upload", conanfile_path=conanfile_path,
                                     reference=conan_ref, remote=recipe_remote)

        if policy != UPLOAD_POLICY_FORCE:
            remote_manifest = self._check_recipe_date(conan_ref, recipe_remote)
        else:
            remote_manifest = None

        self._user_io.out.info("Uploading %s to remote '%s'" % (str(conan_ref), recipe_remote.name))
        recipe_revision = get_recipe_revision(conan_file, self._client_cache, conan_ref)
        conan_ref.revision = recipe_revision
        new_ref = self._upload_recipe(conan_ref, retry, retry_wait, policy, recipe_remote,
                                      remote_manifest)

        recorder.add_recipe(new_ref.full_repr(), recipe_remote.name, recipe_remote.url)
        if packages_ids:
            # Filter packages that don't match the recipe revision
            if new_ref.revision:
                recipe_package_ids = []
                for package_id in packages_ids:
                    pref = PackageReference(new_ref, package_id)
                    package_folder = self._client_cache.package(pref, conan_file.short_paths)
                    rec_rev = ConanInfo.load_from_package(package_folder).recipe_revision
                    if new_ref.revision != rec_rev:
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
                pref = PackageReference(new_ref, package_id)
                p_remote = recipe_remote
                self._upload_package(pref, index + 1, total, retry, retry_wait,
                                     integrity_check, policy, p_remote)
                recorder.add_package(new_ref.full_repr(), package_id)

        # FIXME: I think it makes no sense to specify a remote to "post_upload"
        # FIXME: because the recipe can have one and the package a different one
        self._plugin_manager.execute("post_upload", conanfile_path=conanfile_path,
                                     reference=conan_ref, remote=recipe_remote)

    def _upload_recipe(self, conan_reference, retry, retry_wait, policy, remote, remote_manifest):
        conan_file_path = self._client_cache.conanfile(conan_reference)
        current_remote = self._registry.refs.get(conan_reference)
        if remote != current_remote:
            conanfile = self._loader.load_class(conan_file_path)
            complete_recipe_sources(self._remote_manager, self._client_cache, self._registry,
                                    conanfile, conan_reference)
        new_ref = self._remote_manager.upload_recipe(conan_reference, remote, retry, retry_wait,
                                                     policy=policy, remote_manifest=remote_manifest)

        cur_recipe_remote = self._registry.refs.get(conan_reference.copy_without_revision())
        cur_full_ref = self._registry.refs.get_with_revision(conan_reference.copy_without_revision())
        updated_ref = (cur_full_ref and
                       new_ref.copy_without_revision() == cur_full_ref.copy_without_revision() and
                       new_ref.revision != cur_full_ref.revision)
        # The recipe wasn't in the registry or it has changed the revision field only
        if (not cur_recipe_remote or updated_ref) and policy != UPLOAD_POLICY_SKIP:
            self._registry.refs.set(new_ref, remote.name)

        return new_ref

    def _upload_package(self, pref, index=1, total=1, retry=None, retry_wait=None,
                        integrity_check=False, policy=None, p_remote=None):
        """Uploads the package identified by package_id"""

        msg = ("Uploading package %d/%d: %s to '%s'" % (index, total, str(pref.package_id),
                                                        p_remote.name))
        t1 = time.time()
        self._user_io.out.info(msg)

        if pref.conan.revision:
            # Read the hashes (revisions) and build a correct package reference for the server
            # FIXME: Extract from registry
            package_revision = self._client_cache.package_summary_hash(pref)
            # Copy to not modify the original with the revisions
            pref = pref.copy_with_revisions(pref.conan.revision, package_revision)
        else:
            pref = pref.copy_without_revision()

        new_pref = self._remote_manager.upload_package(pref, p_remote, retry, retry_wait,
                                                       integrity_check, policy)
        logger.debug("====> Time uploader upload_package: %f" % (time.time() - t1))

        cur_package_ref = self._registry.prefs.get(pref)
        if (not cur_package_ref or pref != new_pref) and policy != UPLOAD_POLICY_SKIP:
            self._registry.prefs.set(pref, p_remote.name)

        return new_pref

    def _check_recipe_date(self, conan_ref, remote):
        try:
            remote_recipe_manifest = self._remote_manager.get_conan_manifest(conan_ref, remote)
        except NotFoundException:
            return  # First time uploading this package

        local_manifest = self._client_cache.load_manifest(conan_ref)

        if (remote_recipe_manifest != local_manifest and
                remote_recipe_manifest.time > local_manifest.time):
            self._print_manifest_information(remote_recipe_manifest, local_manifest, conan_ref, remote)
            raise ConanException("Remote recipe is newer than local recipe: "
                                 "\n Remote date: %s\n Local date: %s" %
                                 (remote_recipe_manifest.time, local_manifest.time))

        return remote_recipe_manifest

    def _print_manifest_information(self, remote_recipe_manifest, local_manifest, conan_ref, remote):
        try:
            self._user_io.out.info("\n%s" % ("-"*40))
            self._user_io.out.info("Remote manifest:")
            self._user_io.out.info(remote_recipe_manifest)
            self._user_io.out.info("Local manifest:")
            self._user_io.out.info(local_manifest)
            difference = remote_recipe_manifest.difference(local_manifest)
            if "conanfile.py" in difference:
                contents = load(os.path.join(self._client_cache.export(conan_ref),
                                                   "conanfile.py"))
                endlines = "\\r\\n" if "\r\n" in contents else "\\n"
                self._user_io.out.info("Local 'conanfile.py' using '%s' line-ends" % endlines)
                remote_contents = self._remote_manager.get_path(conan_ref, package_id=None,
                                                                path="conanfile.py", remote=remote)
                endlines = "\\r\\n" if "\r\n" in remote_contents else "\\n"
                self._user_io.out.info("Remote 'conanfile.py' using '%s' line-ends" % endlines)
            self._user_io.out.info("\n%s" % ("-"*40))
        except Exception as e:
            self._user_io.out.info("Error printing information about the diff: %s" % str(e))

