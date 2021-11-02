from requests.exceptions import RequestException

from conans.cli.output import ConanOutput
from conans.cli.output import ScopedOutput
from conans.client.graph.graph import (RECIPE_DOWNLOADED, RECIPE_INCACHE, RECIPE_NEWER,
                                       RECIPE_NOT_IN_REMOTE, RECIPE_UPDATED, RECIPE_EDITABLE,
                                       RECIPE_INCACHE_DATE_UPDATED, RECIPE_UPDATEABLE)
from conans.errors import ConanException, NotFoundException
from conans.util.tracer import log_recipe_got_from_local_cache


class ConanProxy(object):
    def __init__(self, conan_app):
        # collaborators
        self._cache = conan_app.cache
        self._remote_manager = conan_app.remote_manager
        self._conan_app = conan_app

    def get_recipe(self, ref):

        # TODO: cache2.0 check editables
        # if isinstance(layout, PackageEditableLayout):
        #     conanfile_path = layout.conanfile()
        #     status = RECIPE_EDITABLE
        #     # TODO: log_recipe_got_from_editable(reference)
        #     # TODO: recorder.recipe_fetched_as_editable(reference)
        #     return conanfile_path, status, None, ref

        # TODO: cache2.0 Check with new locks
        # with layout.conanfile_write_lock(self._out):
        result = self._get_recipe(ref)
        conanfile_path, status, remote, new_ref = result

        if status not in (RECIPE_DOWNLOADED, RECIPE_UPDATED):
            log_recipe_got_from_local_cache(new_ref)

        return conanfile_path, status, remote, new_ref

    def _get_recipe(self, reference):
        scoped_output = ScopedOutput(str(reference), ConanOutput())

        conanfile_path = self._cache.editable_path(reference)
        if conanfile_path is not None:
            return conanfile_path, RECIPE_EDITABLE, None, reference

        # check if it there's any revision of this recipe in the local cache
        ref = self._cache.get_latest_rrev(reference)

        # NOT in disk, must be retrieved from remotes
        if not ref:
            # we will only check all servers for latest revision if we did a --update
            remote, new_ref = self._download_recipe(reference, scoped_output)
            recipe_layout = self._cache.ref_layout(new_ref)
            status = RECIPE_DOWNLOADED
            conanfile_path = recipe_layout.conanfile()
            return conanfile_path, status, remote, new_ref

        # TODO: cache2.0: check with new --update flows
        recipe_layout = self._cache.ref_layout(ref)
        conanfile_path = recipe_layout.conanfile()
        selected_remote = self._conan_app.selected_remote

        if self._conan_app.check_updates or self._conan_app.update:

            remote, latest_rrev, remote_time = self._get_rrev_from_remotes(reference)
            if latest_rrev:
                # check if we already have the latest in local cache
                # TODO: cache2.0 here if we already have a revision in the cache but we add the
                #  --update argument and we find that same revision in server, we will not
                #  download anything but we will UPDATE the date of that revision in the
                #  local cache and WE ARE ALSO UPDATING THE REMOTE
                #  Check if this is the flow we want to follow
                cache_time = self._cache.get_recipe_timestamp(ref)
                if latest_rrev.revision != ref.revision:
                    if cache_time < remote_time:
                        # the remote one is newer
                        if self._conan_app.update:
                            scoped_output.info("Retrieving from remote '%s'..." % remote.name)
                            remote, new_ref = self._download_recipe(latest_rrev, scoped_output)
                            new_recipe_layout = self._cache.ref_layout(new_ref)
                            new_conanfile_path = new_recipe_layout.conanfile()
                            status = RECIPE_UPDATED
                            return new_conanfile_path, status, remote, new_ref
                        else:
                            status = RECIPE_UPDATEABLE
                    else:
                        status = RECIPE_NEWER
                else:
                    # TODO: cache2.0 we are returning RECIPE_UPDATED just because we are updating
                    #  the date
                    if cache_time >= remote_time:
                        status = RECIPE_INCACHE
                    else:
                        selected_remote = remote
                        self._cache.set_recipe_timestamp(ref, timestamp=remote_time)
                        status = RECIPE_INCACHE_DATE_UPDATED
                return conanfile_path, status, selected_remote, ref
            else:
                status = RECIPE_NOT_IN_REMOTE
                return conanfile_path, status, selected_remote, ref
        else:
            status = RECIPE_INCACHE
            return conanfile_path, status, None, ref

    def _get_rrev_from_remotes(self, reference):
        scoped_output = ScopedOutput(str(reference), ConanOutput())

        results = []
        for remote in self._conan_app.enabled_remotes:
            scoped_output.info(f"Checking remote: {remote.name}")
            try:
                rrev, rrev_time = self._remote_manager.get_latest_recipe_revision_with_time(reference,
                                                                                            remote)
            except NotFoundException:
                pass
            else:
                results.append({'remote': remote,
                                'reference': rrev,
                                'time': rrev_time})
            if len(results) > 0 and not self._conan_app.update and not self._conan_app.check_updates:
                break

        if len(results) == 0:
            return None, None, None

        remotes_results = sorted(results, key=lambda k: k['time'], reverse=True)
        # get the latest revision from all remotes
        found_rrev = remotes_results[0]
        return found_rrev.get("remote"), found_rrev.get("reference"), found_rrev.get("time")

    # searches in all the remotes and downloads the latest from all of them
    # TODO: refactor this, it's confusing
    #  get the recipe selection with _get_rrev_from_remotes out from here if possible
    def _download_recipe(self, ref, scoped_output):
        def _retrieve_from_remote(the_remote, reference):
            scoped_output.info("Trying with '%s'..." % the_remote.name)
            # If incomplete, resolve the latest in server
            _ref, _ref_time = self._remote_manager.get_recipe(reference, the_remote)
            self._cache.set_recipe_timestamp(_ref, _ref_time)
            scoped_output.info("Downloaded recipe revision %s" % _ref.revision)
            return _ref

        if self._conan_app.selected_remote:
            remote = self._conan_app.selected_remote
            scoped_output.info("Retrieving from server '%s' " % remote.name)
            try:
                new_ref = _retrieve_from_remote(remote, ref)
                return remote, new_ref
            except NotFoundException:
                msg = "%s was not found in remote '%s'" % (str(ref), remote.name)
                raise NotFoundException(msg)
            except RequestException as exc:
                raise exc

        scoped_output.info("Not found in local cache, looking in remotes...")
        remotes = self._conan_app.enabled_remotes
        if not remotes:
            raise ConanException("No remote defined")

        remote, latest_rrev, _ = self._get_rrev_from_remotes(ref)

        if not latest_rrev:
            msg = "Unable to find '%s' in remotes" % ref.full_str()
            raise NotFoundException(msg)

        new_ref = _retrieve_from_remote(remote, latest_rrev)
        return remote, new_ref
