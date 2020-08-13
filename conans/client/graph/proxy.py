import os

from requests.exceptions import RequestException

from conans.client.graph.graph import (RECIPE_DOWNLOADED, RECIPE_INCACHE, RECIPE_NEWER,
                                       RECIPE_NOT_IN_REMOTE, RECIPE_NO_REMOTE, RECIPE_UPDATEABLE,
                                       RECIPE_UPDATED, RECIPE_EDITABLE)
from conans.client.output import ScopedOutput
from conans.client.recorder.action_recorder import INSTALL_ERROR_MISSING, INSTALL_ERROR_NETWORK
from conans.client.remover import DiskRemover
from conans.errors import ConanException, NotFoundException, RecipeNotFoundException
from conans.paths.package_layouts.package_editable_layout import PackageEditableLayout
from conans.util.tracer import log_recipe_got_from_local_cache


class ConanProxy(object):
    def __init__(self, cache, output, remote_manager):
        # collaborators
        self._cache = cache
        self._out = output
        self._remote_manager = remote_manager

    def get_recipe(self, ref, check_updates, update, remotes, recorder):
        layout = self._cache.package_layout(ref)
        if isinstance(layout, PackageEditableLayout):
            conanfile_path = layout.conanfile()
            status = RECIPE_EDITABLE
            # TODO: log_recipe_got_from_editable(reference)
            # TODO: recorder.recipe_fetched_as_editable(reference)
            return conanfile_path, status, None, ref

        with layout.conanfile_write_lock(self._out):
            result = self._get_recipe(layout, ref, check_updates, update, remotes, recorder)
            conanfile_path, status, remote, new_ref = result

            if status not in (RECIPE_DOWNLOADED, RECIPE_UPDATED):
                log_recipe_got_from_local_cache(new_ref)
                recorder.recipe_fetched_from_cache(new_ref)

        return conanfile_path, status, remote, new_ref

    def _get_recipe(self, layout, ref, check_updates, update, remotes, recorder):
        output = ScopedOutput(str(ref), self._out)
        # check if it is in disk
        conanfile_path = layout.conanfile()

        # NOT in disk, must be retrieved from remotes
        if not os.path.exists(conanfile_path):
            remote, new_ref = self._download_recipe(layout, ref, output, remotes, remotes.selected,
                                                    recorder)
            status = RECIPE_DOWNLOADED
            return conanfile_path, status, remote, new_ref

        metadata = layout.load_metadata()
        cur_revision = metadata.recipe.revision
        cur_remote = metadata.recipe.remote
        cur_remote = remotes[cur_remote] if cur_remote else None
        selected_remote = remotes.selected or cur_remote

        check_updates = check_updates or update
        requested_different_revision = (ref.revision is not None) and cur_revision != ref.revision
        if requested_different_revision:
            if check_updates:
                remote, new_ref = self._download_recipe(layout, ref, output, remotes,
                                                        selected_remote, recorder)
                status = RECIPE_DOWNLOADED
                return conanfile_path, status, remote, new_ref
            else:
                raise NotFoundException("The '%s' revision recipe in the local cache doesn't "
                                        "match the requested '%s'."
                                        " Use '--update' to check in the remote."
                                        % (cur_revision, repr(ref)))

        if not check_updates:
            status = RECIPE_INCACHE
            ref = ref.copy_with_rev(cur_revision)
            return conanfile_path, status, cur_remote, ref

        # Checking updates in the server
        if not selected_remote:
            status = RECIPE_NO_REMOTE
            ref = ref.copy_with_rev(cur_revision)
            return conanfile_path, status, None, ref

        try:  # get_recipe_manifest can fail, not in server
            upstream_manifest, ref = self._remote_manager.get_recipe_manifest(ref, selected_remote)
        except NotFoundException:
            status = RECIPE_NOT_IN_REMOTE
            ref = ref.copy_with_rev(cur_revision)
            return conanfile_path, status, selected_remote, ref

        read_manifest = layout.recipe_manifest()
        if upstream_manifest != read_manifest:
            if upstream_manifest.time > read_manifest.time:
                if update:
                    DiskRemover().remove_recipe(layout, output=output)
                    output.info("Retrieving from remote '%s'..." % selected_remote.name)
                    self._download_recipe(layout, ref, output, remotes, selected_remote, recorder)
                    with layout.update_metadata() as metadata:
                        metadata.recipe.remote = selected_remote.name
                    status = RECIPE_UPDATED
                    return conanfile_path, status, selected_remote, ref
                else:
                    status = RECIPE_UPDATEABLE
            else:
                status = RECIPE_NEWER
        else:
            status = RECIPE_INCACHE

        ref = ref.copy_with_rev(cur_revision)
        return conanfile_path, status, selected_remote, ref

    def _download_recipe(self, layout, ref, output, remotes, remote, recorder):

        def _retrieve_from_remote(the_remote):
            output.info("Trying with '%s'..." % the_remote.name)
            # If incomplete, resolve the latest in server
            _ref = self._remote_manager.get_recipe(ref, the_remote)
            output.info("Downloaded recipe revision %s" % _ref.revision)
            with layout.update_metadata() as metadata:
                metadata.recipe.remote = the_remote.name
            recorder.recipe_downloaded(ref, the_remote.url)
            return _ref

        if remote:
            output.info("Retrieving from server '%s' " % remote.name)
        else:
            try:
                remote_name = layout.load_metadata().recipe.remote
                if remote_name:
                    remote = remotes[remote_name]
            except (IOError, RecipeNotFoundException):
                pass
            else:
                if remote:
                    output.info("Retrieving from predefined remote '%s'" % remote.name)

        if remote:
            try:
                new_ref = _retrieve_from_remote(remote)
                return remote, new_ref
            except NotFoundException:
                msg = "%s was not found in remote '%s'" % (str(ref), remote.name)
                recorder.recipe_install_error(ref, INSTALL_ERROR_MISSING,
                                              msg, remote.url)
                raise NotFoundException(msg)
            except RequestException as exc:
                recorder.recipe_install_error(ref, INSTALL_ERROR_NETWORK,
                                              str(exc), remote.url)
                raise exc

        output.info("Not found in local cache, looking in remotes...")
        remotes = remotes.values()
        if not remotes:
            raise ConanException("No remote defined")
        for remote in remotes:
            try:
                new_ref = _retrieve_from_remote(remote)
                return remote, new_ref
            # If not found continue with the next, else raise
            except NotFoundException:
                pass
        else:
            msg = "Unable to find '%s' in remotes" % ref.full_str()
            recorder.recipe_install_error(ref, INSTALL_ERROR_MISSING,
                                          msg, None)
            raise NotFoundException(msg)
