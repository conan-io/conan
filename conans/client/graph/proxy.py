from datetime import datetime
import time

from requests.exceptions import RequestException

from conans.client.graph.graph import (RECIPE_DOWNLOADED, RECIPE_INCACHE, RECIPE_NEWER,
                                       RECIPE_NOT_IN_REMOTE, RECIPE_NO_REMOTE, RECIPE_UPDATEABLE,
                                       RECIPE_UPDATED, RECIPE_EDITABLE,
                                       RECIPE_INCACHE_DATE_UPDATED)
from conans.client.output import ScopedOutput
from conans.client.recorder.action_recorder import INSTALL_ERROR_MISSING, INSTALL_ERROR_NETWORK
from conans.client.remover import DiskRemover
from conans.errors import ConanException, NotFoundException, RecipeNotFoundException
from conans.model.ref import ConanFileReference
from conans.util.tracer import log_recipe_got_from_local_cache



class ConanProxy(object):
    def __init__(self, cache, output, remote_manager):
        # collaborators
        self._cache = cache
        self._out = output
        self._remote_manager = remote_manager

    def get_recipe(self, ref, check_updates, update, remotes):

        # TODO: cache2.0 check editables
        # if isinstance(layout, PackageEditableLayout):
        #     conanfile_path = layout.conanfile()
        #     status = RECIPE_EDITABLE
        #     # TODO: log_recipe_got_from_editable(reference)
        #     # TODO: recorder.recipe_fetched_as_editable(reference)
        #     return conanfile_path, status, None, ref

        # TODO: cache2.0 Check with new locks
        # with layout.conanfile_write_lock(self._out):
        result = self._get_recipe(ref, check_updates, update, remotes)
        conanfile_path, status, remote, new_ref = result

        if status not in (RECIPE_DOWNLOADED, RECIPE_UPDATED):
            log_recipe_got_from_local_cache(new_ref)

        return conanfile_path, status, remote, new_ref

    def _get_recipe(self, reference, check_updates, update, remotes):
        output = ScopedOutput(str(reference), self._out)

        check_updates = check_updates or update

        conanfile_path = self._cache.editable_path(reference)
        if conanfile_path is not None:
            return conanfile_path, RECIPE_EDITABLE, None, reference

        # check if it there's any revision of this recipe in the local cache
        ref = self._cache.get_latest_rrev(reference)

        # NOT in disk, must be retrieved from remotes
        if not ref:
            # we will only check all servers for latest revision if we did a --update
            remote, new_ref = self._download_recipe(reference, output, remotes,
                                                    remotes.selected,
                                                    check_all_servers=check_updates)
            recipe_layout = self._cache.ref_layout(new_ref)
            status = RECIPE_DOWNLOADED
            conanfile_path = recipe_layout.conanfile()
            return conanfile_path, status, remote, new_ref

        # TODO: cache2.0: check with new --update flows
        recipe_layout = self._cache.ref_layout(ref)
        conanfile_path = recipe_layout.conanfile()
        cur_remote = self._cache.get_remote(recipe_layout.reference)
        cur_remote = remotes[cur_remote] if cur_remote else None
        selected_remote = remotes.selected or cur_remote

        if check_updates:

            remote, latest_rrev, remote_time = self._get_rrev_from_remotes(reference,
                                                                           remotes.values(),
                                                                           check_all_servers=True)
            if latest_rrev:
                # check if we already have the latest in local cache
                # TODO: cache2.0 here if we already have a revision in the cache but we add the
                #  --update argument and we find that same revision in server, we will not
                #  download anything but we will UPDATE the date of that revision in the
                #  local cache and WE ARE ALSO UPDATING THE REMOTE
                #  Check if this is the flow we want to follow
                cache_time = self._cache.get_timestamp(ref)
                if latest_rrev.revision != ref.revision:
                    if cache_time < remote_time:
                        # the remote one is newer
                        output.info("Retrieving from remote '%s'..." % remote.name)
                        remote, new_ref = self._download_recipe(latest_rrev, output,
                                                                remotes, remote)
                        new_recipe_layout = self._cache.ref_layout(new_ref)
                        new_conanfile_path = new_recipe_layout.conanfile()
                        status = RECIPE_UPDATED
                        return new_conanfile_path, status, remote, new_ref
                    else:
                        status = RECIPE_NEWER
                else:
                    # TODO: cache2.0 we are returning RECIPE_UPDATED just because we are updating
                    #  the date
                    if cache_time >= remote_time:
                        status = RECIPE_INCACHE
                    else:
                        selected_remote = remote
                        self._cache.update_reference(ref,
                                                     new_timestamp=remote_time)
                        status = RECIPE_INCACHE_DATE_UPDATED
                return conanfile_path, status, selected_remote, ref
            else:
                status = RECIPE_NOT_IN_REMOTE
                return conanfile_path, status, selected_remote, ref
        else:
            status = RECIPE_INCACHE
            return conanfile_path, status, cur_remote, ref

    def _get_rrev_from_remotes(self, reference, remotes, check_all_servers):
        output = ScopedOutput(str(reference), self._out)

        results = []
        for remote in remotes:
            try:
                output.info(f"Checking remote: {remote.name}")

                remote_rrev = self._remote_manager.get_latest_recipe_revision_with_time(reference,
                                                                                        remote)
                if remote_rrev.get('reference'):
                    results.append({'remote': remote,
                                    'reference': remote_rrev.get("reference"),
                                    'time': remote_rrev.get("time")})

                if len(results) > 0 and not check_all_servers:
                    break
            except NotFoundException:
                pass

        if len(results) == 0:
            return None, None, None

        remotes_results = sorted(results, key=lambda k: k['time'], reverse=True)
        # get the latest revision from all remotes
        found_rrev = remotes_results[0]
        return found_rrev.get("remote"), found_rrev.get("reference"), found_rrev.get("time")

    # searches in all the remotes and downloads the latest from all of them
    # TODO: refactor this, it's confusing
    #  get the recipe selection with _get_rrev_from_remotes out from here if possible
    def _download_recipe(self, ref, output, remotes, remote, check_all_servers=True):

        def _retrieve_from_remote(the_remote, reference):
            output.info("Trying with '%s'..." % the_remote.name)
            # If incomplete, resolve the latest in server
            _ref, _ref_time = self._remote_manager.get_recipe(reference, the_remote)
            self._cache.set_timestamp(_ref, _ref_time)
            output.info("Downloaded recipe revision %s" % _ref.revision)
            return _ref

        if remote:
            output.info("Retrieving from server '%s' " % remote.name)
        else:
            latest_rrev = self._cache.get_latest_rrev(ref)
            if latest_rrev:
                remote_name = self._cache.get_remote(latest_rrev)
                if remote_name:
                    remote = remotes[remote_name]
                    output.info("Retrieving from predefined remote '%s'" % remote.name)

        if remote:
            try:
                new_ref = _retrieve_from_remote(remote, ref)
                return remote, new_ref
            except NotFoundException:
                msg = "%s was not found in remote '%s'" % (str(ref), remote.name)
                raise NotFoundException(msg)
            except RequestException as exc:
                raise exc

        output.info("Not found in local cache, looking in remotes...")
        remotes = remotes.values()
        if not remotes:
            raise ConanException("No remote defined")

        remote, latest_rrev, _ = self._get_rrev_from_remotes(ref, remotes, check_all_servers)

        if not latest_rrev:
            msg = "Unable to find '%s' in remotes" % ref.full_str()
            raise NotFoundException(msg)

        new_ref = _retrieve_from_remote(remote, latest_rrev)
        return remote, new_ref
