from conan.api.output import ConanOutput
from conan.internal.cache.conan_reference_layout import BasicLayout
from conan.internal.graph.graph import (RECIPE_DOWNLOADED, RECIPE_INCACHE, RECIPE_NEWER,
                                        RECIPE_NOT_IN_REMOTE, RECIPE_UPDATED, RECIPE_EDITABLE,
                                        RECIPE_INCACHE_DATE_UPDATED, RECIPE_UPDATEABLE)
from conan.internal.errors import NotFoundException, ConanReferenceAlreadyExistsInDB
from conan.errors import ConanException


class ConanProxy:
    def __init__(self, conan_app, editable_packages, legacy_update=None):
        # collaborators
        self._editable_packages = editable_packages
        self._cache = conan_app.cache
        self._remote_manager = conan_app.remote_manager
        self._resolved = {}  # Cache of the requested recipes to optimize calls
        self._legacy_update = legacy_update

    def get_recipe(self, ref, remotes, update, check_update):
        """
        :return: Tuple (layout, status, remote)
        """
        resolved = self._resolved.get(ref)
        if resolved is None:
            resolved = self._get_recipe(ref, remotes, update, check_update)
            self._resolved[ref] = resolved
        return resolved

    # return the remote where the recipe was found or None if the recipe was not found
    def _get_recipe(self, reference, remotes, update, check_update):
        output = ConanOutput(scope=str(reference))

        conanfile_path = self._editable_packages.get_path(reference)
        if conanfile_path is not None:
            return BasicLayout(reference, conanfile_path), RECIPE_EDITABLE, None

        # check if it there's any revision of this recipe in the local cache
        try:
            # Just do 1 call to the DB, not 2
            if reference.revision is None:
                recipe_layout = self._cache.recipe_layout_latest(reference)
            else:
                recipe_layout = self._cache.recipe_layout(reference)
            ref = recipe_layout.reference  # latest revision if it was not defined
        except ConanException:
            # NOT in disk, must be retrieved from remotes
            # we will only check all servers for latest revision if we did a --update
            layout, remote = self._download_recipe(reference, remotes, output, update, check_update)
            status = RECIPE_DOWNLOADED
            return layout, status, remote

        # If the revision is given, then we don't need to check for updates
        if not (check_update or should_update_reference(reference, update)):
            # Wait for extraction to complete in case another process is extracting
            with recipe_layout.conanfile_write_lock(output):
                pass  # Lock released, extraction complete
            status = RECIPE_INCACHE
            return recipe_layout, status, None

        # PERFORMANCE OPTIMIZATION: Double-checked locking pattern
        # Instead of holding the lock while querying remotes (slow network I/O),
        # we query remotes first without the lock, then only lock if update is needed.
        #
        # Benefits:
        # - Processes that don't need updates can query remotes in parallel
        # - Only processes that actually download updates serialize on the lock
        # - Reduces lock contention with many concurrent processes
        #
        # Pattern:
        # 1. Query remotes WITHOUT lock (parallel remote queries)
        # 2. Check if update needed WITHOUT lock
        # 3. If no update needed, return early (no lock acquired)
        # 4. If update needed, acquire lock and double-check

        # Step 1: Query remotes without holding the lock (allows parallel queries)
        remote, remote_ref = self._find_newest_recipe_in_remotes(reference, remotes,
                                                                 update, check_update)
        if remote_ref is None:  # Nothing found in remotes
            # Wait for extraction to complete in case another process is extracting
            with recipe_layout.conanfile_write_lock(output):
                pass  # Lock released, extraction complete
            status = RECIPE_NOT_IN_REMOTE
            return recipe_layout, status, None

        # Step 2: Check if update is needed (without lock, using cached state)
        assert ref.timestamp
        cache_time = ref.timestamp
        update_needed = False

        if remote_ref.revision != ref.revision:
            if cache_time < remote_ref.timestamp:
                # Remote one is newer, check if we should update
                if should_update_reference(remote_ref, update):
                    update_needed = True
                else:
                    # Update available but not requested
                    # Wait for extraction to complete in case another process is extracting
                    with recipe_layout.conanfile_write_lock(output):
                        pass  # Lock released, extraction complete
                    status = RECIPE_UPDATEABLE
                    return recipe_layout, status, remote
            else:
                # Cache is newer than remote
                # Wait for extraction to complete in case another process is extracting
                with recipe_layout.conanfile_write_lock(output):
                    pass  # Lock released, extraction complete
                status = RECIPE_NEWER
                return recipe_layout, status, None
        else:
            # Same revision, just check timestamp
            if cache_time >= remote_ref.timestamp:
                # Wait for extraction to complete in case another process is extracting
                with recipe_layout.conanfile_write_lock(output):
                    pass  # Lock released, extraction complete
                status = RECIPE_INCACHE
                return recipe_layout, status, None
            # Need to update timestamp
            update_needed = True

        # Step 3: Update is needed, acquire lock for actual update
        # This serializes only the processes that actually need to download/update
        with self._cache.recipe_lock(ref):
            # Step 4: Double-check inside the lock to handle race conditions
            # Another process might have updated while we were waiting for the lock
            try:
                if reference.revision is None:
                    recipe_layout_recheck = self._cache.recipe_layout_latest(reference)
                else:
                    recipe_layout_recheck = self._cache.recipe_layout(reference)
                ref_recheck = recipe_layout_recheck.reference
                # CRITICAL: Wait for file extraction to complete before using this layout
                # Another process might be extracting files for this recipe right now
                with recipe_layout_recheck.conanfile_write_lock(output):
                    pass  # Lock released, extraction complete
            except ConanException:
                # Recipe was removed by another process, fall through to download
                ref_recheck = ref
                recipe_layout_recheck = recipe_layout

            # Re-check if we still need to update
            if ref_recheck.timestamp != ref.timestamp:
                # Another process updated the cache while we waited for the lock
                # Re-evaluate if we still need to update
                cache_time_recheck = ref_recheck.timestamp

                if remote_ref.revision != ref_recheck.revision:
                    if cache_time_recheck < remote_ref.timestamp:
                        # Still need to update
                        pass  # Continue to download
                    else:
                        # Another process updated to same or newer version
                        if cache_time_recheck > remote_ref.timestamp:
                            status = RECIPE_NEWER
                        else:
                            status = RECIPE_INCACHE
                        return recipe_layout_recheck, status, None
                else:
                    # Same revision now, just check timestamp
                    if cache_time_recheck >= remote_ref.timestamp:
                        status = RECIPE_INCACHE
                        return recipe_layout_recheck, status, None
                    # Need to update timestamp only
                    self._cache.update_recipe_timestamp(remote_ref)
                    status = RECIPE_INCACHE_DATE_UPDATED
                    return recipe_layout_recheck, status, remote

            # Actually perform the update
            if remote_ref.revision != ref_recheck.revision:
                output.info(f"Updating to latest from remote '{remote.name}'...")
                try:
                    new_recipe_layout = self._download(remote_ref, remote)
                except ConanReferenceAlreadyExistsInDB:
                    # When updating to a newer revision in the server, but it already exists
                    # in the cache with an older timestamp (another process might be extracting it)
                    output.info(f"Latest from '{remote.name}' was found in "
                                "the cache, using it and updating its timestamp")
                    new_recipe_layout = self._cache.recipe_layout(remote_ref)
                    # Wait for extraction to complete if another process is extracting files
                    # This prevents "conanfile.py not found" errors in concurrent updates
                    with new_recipe_layout.conanfile_write_lock(output):
                        pass  # Lock released, extraction complete
                    self._cache.update_recipe_timestamp(remote_ref)  # make it latest
                status = RECIPE_UPDATED
                return new_recipe_layout, status, remote
            else:
                # Just update the timestamp
                self._cache.update_recipe_timestamp(remote_ref)
                status = RECIPE_INCACHE_DATE_UPDATED
                return recipe_layout_recheck, status, remote

    def _find_newest_recipe_in_remotes(self, reference, remotes, update, check_update):
        output = ConanOutput(scope=str(reference))

        results = []
        need_update = should_update_reference(reference, update) or check_update
        for remote in remotes:
            if remote.allowed_packages and not any(reference.matches(f, is_consumer=False)
                                                   for f in remote.allowed_packages):
                output.debug(f"Excluding remote {remote.name} because recipe is filtered out")
                continue
            output.info(f"Checking remote: {remote.name}")
            try:
                if self._legacy_update and need_update and reference.revision is None:
                    if not getattr(ConanProxy, "update_policy_legacy_warning", None):
                        ConanProxy.update_policy_legacy_warning = True
                        ConanOutput().warning("The 'core:update_policy' conf is deprecated and will "
                                              "be removed in future versions", warn_tag="deprecated")
                    refs = self._remote_manager.get_recipe_revisions(reference, remote)
                    results.extend([{'remote': remote, 'ref': ref} for ref in refs])
                    continue
                if not reference.revision:
                    ref = self._remote_manager.get_latest_recipe_revision(reference, remote)
                else:
                    ref = self._remote_manager.get_recipe_revision(reference, remote)
                if not need_update:
                    return remote, ref
                results.append({'remote': remote, 'ref': ref})
            except NotFoundException:
                pass

        if len(results) == 0:
            return None, None

        if self._legacy_update and need_update:
            # Use only the first occurence of each revision in the remotes
            filtered_results = []
            revisions = set()
            for r in results:
                ref = r["ref"]
                if ref.revision not in revisions:
                    revisions.add(ref.revision)
                    filtered_results.append(r)
            results = filtered_results

        remotes_results = sorted(results, key=lambda k: k['ref'].timestamp, reverse=True)
        # get the latest revision from all remotes
        found_rrev = remotes_results[0]
        return found_rrev.get("remote"), found_rrev.get("ref")

    def _download_recipe(self, ref, remotes, scoped_output, update, check_update):
        # When a recipe doesn't exist in local cache, it is retrieved from servers
        scoped_output.info("Not found in local cache, looking in remotes...")
        if not remotes:
            raise ConanException("No remote defined")

        remote, latest_rref = self._find_newest_recipe_in_remotes(ref, remotes, update, check_update)
        if not latest_rref:
            msg = "Unable to find '%s' in remotes" % repr(ref)
            raise NotFoundException(msg)

        # Acquire lock to prevent concurrent downloads of the same recipe
        # This prevents "conanfile.py not found" errors when multiple processes
        # try to download the same new recipe simultaneously
        from conan.internal.errors import ConanReferenceAlreadyExistsInDB
        with self._cache.recipe_lock(latest_rref):
            # Double-check if another process downloaded it while we waited for the lock
            try:
                if ref.revision is None:
                    recipe_layout = self._cache.recipe_layout_latest(ref)
                else:
                    recipe_layout = self._cache.recipe_layout(latest_rref)
                # Recipe was downloaded by another process, use it
                # Wait for extraction to complete if still in progress
                with recipe_layout.conanfile_write_lock(scoped_output):
                    pass  # Lock released, extraction complete
                return recipe_layout, remote
            except ConanException:
                # Recipe still not in cache, we need to download it
                try:
                    recipe_layout = self._download(latest_rref, remote)
                except ConanReferenceAlreadyExistsInDB:
                    # Another process created DB entry while we were preparing to download
                    # Get the layout and wait for extraction to complete
                    if ref.revision is None:
                        recipe_layout = self._cache.recipe_layout_latest(ref)
                    else:
                        recipe_layout = self._cache.recipe_layout(latest_rref)
                    with recipe_layout.conanfile_write_lock(scoped_output):
                        pass  # Lock released, extraction complete
                return recipe_layout, remote

    def _download(self, ref, remote):
        assert ref.revision
        assert ref.timestamp
        recipe_layout = self._remote_manager.get_recipe(ref, remote)
        output = ConanOutput(scope=str(ref))
        output.info("Downloaded recipe revision %s" % ref.revision)
        return recipe_layout


def should_update_reference(reference, update):
    if update is None:
        return False
    # Old API usages only ever passed a bool
    if isinstance(update, bool):
        return update
    # Legacy syntax had --update without pattern, it manifests as a "*" pattern
    return any(name == "*" or reference.name == name for name in update)
