from conan.api.output import ConanOutput
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

    def get_recipe(self, ref, remotes, update, check_update):
        # TODO: cache2.0 Check with new locks
        self._update = update
        self._check_update = check_update  # TODO: Dirty, improve it
        # with layout.conanfile_write_lock(self._out):
        result = self._get_recipe(ref, remotes)
        conanfile_path, status, remote, new_ref = result

        if status not in (RECIPE_DOWNLOADED, RECIPE_UPDATED):
            log_recipe_got_from_local_cache(new_ref)

        return conanfile_path, status, remote, new_ref

    # return the remote where the recipe was found or None if the recipe was not found
    def _get_recipe(self, reference, remotes):
        output = ConanOutput(scope=str(reference))

        conanfile_path = self._cache.editable_packages.get_path(reference)
        if conanfile_path is not None:
            return conanfile_path, RECIPE_EDITABLE, None, reference

        # check if it there's any revision of this recipe in the local cache
        ref = self._cache.get_latest_recipe_reference(reference)

        # NOT in disk, must be retrieved from remotes
        if not ref:
            # we will only check all servers for latest revision if we did a --update
            remote, new_ref = self._download_recipe(reference, remotes, output)
            recipe_layout = self._cache.ref_layout(new_ref)
            status = RECIPE_DOWNLOADED
            conanfile_path = recipe_layout.conanfile()
            return conanfile_path, status, remote, new_ref

        # TODO: cache2.0: check with new --update flows
        recipe_layout = self._cache.ref_layout(ref)
        conanfile_path = recipe_layout.conanfile()

        # TODO: If the revision is given, then we don't need to check for updates?
        if self._check_update or self._update:

            remote, remote_ref = self._find_newest_recipe_in_remotes(reference, remotes)
            if remote_ref:
                # check if we already have the latest in local cache
                # TODO: cache2.0 here if we already have a revision in the cache but we add the
                #  --update argument and we find that same revision in server, we will not
                #  download anything but we will UPDATE the date of that revision in the
                #  local cache and WE ARE ALSO UPDATING THE REMOTE
                #  Check if this is the flow we want to follow
                cache_time = self._cache.get_recipe_timestamp(ref)
                if remote_ref.revision != ref.revision:
                    if cache_time < remote_ref.timestamp:
                        # the remote one is newer
                        if self._update:
                            output.info("Retrieving from remote '%s'..." % remote.name)
                            remote, new_ref = self._download_recipe(remote_ref, remotes, output)
                            new_recipe_layout = self._cache.ref_layout(new_ref)
                            new_conanfile_path = new_recipe_layout.conanfile()
                            status = RECIPE_UPDATED
                            return new_conanfile_path, status, remote, new_ref
                        else:
                            status = RECIPE_UPDATEABLE
                    else:
                        status = RECIPE_NEWER
                        # If your recipe in cache is newer it does not make sense to return a remote?
                        remote = None
                else:
                    # TODO: cache2.0 we are returning RECIPE_UPDATED just because we are updating
                    #  the date
                    if cache_time >= remote_ref.timestamp:
                        status = RECIPE_INCACHE
                    else:
                        self._cache.update_recipe_timestamp(remote_ref)
                        status = RECIPE_INCACHE_DATE_UPDATED
                return conanfile_path, status, remote, ref
            else:
                status = RECIPE_NOT_IN_REMOTE
                return conanfile_path, status, None, ref
        else:
            status = RECIPE_INCACHE
            return conanfile_path, status, None, ref

    def _find_newest_recipe_in_remotes(self, reference, remotes):
        output = ConanOutput(scope=str(reference))

        results = []
        for remote in remotes:
            output.info(f"Checking remote: {remote.name}")
            if not reference.revision:
                try:
                    ref = self._remote_manager.get_latest_recipe_reference(reference, remote)
                    results.append({'remote': remote, 'ref': ref})
                except NotFoundException:
                    pass
            else:
                try:
                    ref = self._remote_manager.get_recipe_revision_reference(reference, remote)
                    results.append({'remote': remote, 'ref': ref})
                except NotFoundException:
                    pass

            if len(results) > 0 and not self._update and not self._check_update:
                break

        if len(results) == 0:
            return None, None

        remotes_results = sorted(results, key=lambda k: k['ref'].timestamp, reverse=True)
        # get the latest revision from all remotes
        found_rrev = remotes_results[0]
        return found_rrev.get("remote"), found_rrev.get("ref")

    # searches in all the remotes and downloads the latest from all of them
    def _download_recipe(self, ref, remotes, scoped_output):
        def _retrieve_from_remote(the_remote, reference):
            scoped_output.info("Trying with '%s'..." % the_remote.name)
            # If incomplete, resolve the latest in server
            if not reference.revision:
                reference = self._remote_manager.get_latest_recipe_reference(ref, remote)
            self._remote_manager.get_recipe(reference, the_remote)
            self._cache.update_recipe_timestamp(reference)
            scoped_output.info("Downloaded recipe revision %s" % reference.revision)
            return reference

        scoped_output.info("Not found in local cache, looking in remotes...")
        if not remotes:
            raise ConanException("No remote defined")

        remote, latest_rref = self._find_newest_recipe_in_remotes(ref, remotes)

        if not latest_rref:
            msg = "Unable to find '%s' in remotes" % repr(ref)
            raise NotFoundException(msg)

        new_ref = _retrieve_from_remote(remote, latest_rref)
        return remote, new_ref
