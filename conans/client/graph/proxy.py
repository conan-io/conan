from conan.api.output import ConanOutput
from conans.client.graph.graph import (RECIPE_DOWNLOADED, RECIPE_INCACHE, RECIPE_NEWER,
                                       RECIPE_NOT_IN_REMOTE, RECIPE_UPDATED, RECIPE_EDITABLE,
                                       RECIPE_INCACHE_DATE_UPDATED, RECIPE_UPDATEABLE)
from conans.errors import ConanException, NotFoundException


class ConanProxy:
    def __init__(self, conan_app):
        # collaborators
        self._cache = conan_app.cache
        self._remote_manager = conan_app.remote_manager
        self._resolved = {}  # Cache of the requested recipes to optimize calls

    def get_recipe(self, ref, remotes, update, check_update):
        """
        :return: Tuple (conanfile_path, status, remote, new_ref)
        """
        # TODO: cache2.0 Check with new locks
        # with layout.conanfile_write_lock(self._out):
        resolved = self._resolved.get(ref)
        if resolved is None:
            resolved = self._get_recipe(ref, remotes, update, check_update)
            self._resolved[ref] = resolved
        return resolved

    # return the remote where the recipe was found or None if the recipe was not found
    def _get_recipe(self, reference, remotes, update, check_update):
        output = ConanOutput(scope=str(reference))

        conanfile_path = self._cache.editable_packages.get_path(reference)
        if conanfile_path is not None:
            return conanfile_path, RECIPE_EDITABLE, None, reference

        # check if it there's any revision of this recipe in the local cache
        ref = self._cache.get_latest_recipe_reference(reference)

        # NOT in disk, must be retrieved from remotes
        if not ref:
            # we will only check all servers for latest revision if we did a --update
            remote, new_ref = self._download_recipe(reference, remotes, output, update, check_update)
            recipe_layout = self._cache.ref_layout(new_ref)
            status = RECIPE_DOWNLOADED
            conanfile_path = recipe_layout.conanfile()
            return conanfile_path, status, remote, new_ref

        # TODO: cache2.0: check with new --update flows
        recipe_layout = self._cache.ref_layout(ref)
        conanfile_path = recipe_layout.conanfile()

        # TODO: If the revision is given, then we don't need to check for updates?
        if not (check_update or update):
            status = RECIPE_INCACHE
            return conanfile_path, status, None, ref

        # Need to check updates
        remote, remote_ref = self._find_newest_recipe_in_remotes(reference, remotes,
                                                                 update, check_update)
        if remote_ref is None:  # Nothing found in remotes
            status = RECIPE_NOT_IN_REMOTE
            return conanfile_path, status, None, ref

        # Something found in remotes, check if we already have the latest in local cache
        # TODO: cache2.0 here if we already have a revision in the cache but we add the
        #  --update argument and we find that same revision in server, we will not
        #  download anything but we will UPDATE the date of that revision in the
        #  local cache and WE ARE ALSO UPDATING THE REMOTE
        #  Check if this is the flow we want to follow
        assert ref.timestamp
        cache_time = ref.timestamp
        if remote_ref.revision != ref.revision:
            if cache_time < remote_ref.timestamp:
                # the remote one is newer
                if update:
                    output.info("Retrieving from remote '%s'..." % remote.name)
                    self._download(remote_ref, remote)
                    new_recipe_layout = self._cache.ref_layout(remote_ref)
                    new_conanfile_path = new_recipe_layout.conanfile()
                    status = RECIPE_UPDATED
                    return new_conanfile_path, status, remote, remote_ref
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

    def _find_newest_recipe_in_remotes(self, reference, remotes, update, check_update):
        output = ConanOutput(scope=str(reference))

        results = []
        for remote in remotes:
            output.info(f"Checking remote: {remote.name}")
            try:
                if not reference.revision:
                    ref = self._remote_manager.get_latest_recipe_reference(reference, remote)
                else:
                    ref = self._remote_manager.get_recipe_revision_reference(reference, remote)
                if not update and not check_update:
                    return remote, ref
                results.append({'remote': remote, 'ref': ref})
            except NotFoundException:
                pass

        if len(results) == 0:
            return None, None

        remotes_results = sorted(results, key=lambda k: k['ref'].timestamp, reverse=True)
        # get the latest revision from all remotes
        found_rrev = remotes_results[0]
        return found_rrev.get("remote"), found_rrev.get("ref")

    def _download_recipe(self, ref, remotes, scoped_output, update, check_update):
        # When a recipe doesn't existin local cache, it is retrieved from servers
        scoped_output.info("Not found in local cache, looking in remotes...")
        if not remotes:
            raise ConanException("No remote defined")

        remote, latest_rref = self._find_newest_recipe_in_remotes(ref, remotes, update, check_update)
        if not latest_rref:
            msg = "Unable to find '%s' in remotes" % repr(ref)
            raise NotFoundException(msg)

        self._download(latest_rref, remote)
        return remote, latest_rref

    def _download(self, ref, remote):
        assert ref.revision
        self._remote_manager.get_recipe(ref, remote)
        self._cache.update_recipe_timestamp(ref)
        output = ConanOutput(scope=str(ref))
        output.info("Downloaded recipe revision %s" % ref.revision)
