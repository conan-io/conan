from conans.client.remote_registry import RemoteRegistry
from conans.client.proxy import ConanProxy
from conans.search.search import DiskSearchManager
from conans.client.remote_manager import RemoteManager


def _search_recipes_all(pattern, ignorecase):

    reg = RemoteRegistry(self._client_cache.registry, self._user_io.out)
    references = {}
    for remote in reg.remotes:
        remote_proxy = ConanProxy(self._client_cache, self._user_io, self._remote_manager, remote.name)
        result = remote_proxy.search(pattern, ignorecase)
        if result:
            references[remote.name] = result
    return references


def search_recipes(pattern, remote, ignorecase):
    if not remote:
        return DiskSearchManager(client_cache).search_recipes(pattern, ignorecase)
    
    if remote == 'all':
        return self.search_recipes_all(pattern, ignorecase)
    
    return RemoteManager(client_cache, remote_client, output).search_recipes(remote, pattern, ignorecase)

    references = self._get_search_adapter(remote).search(pattern, ignorecase)
    return references


def search_packages(reference=None, remote=None, packages_query=None, outdated=False):
    """ Return the single information saved in conan.vars about all the packages
        or the packages which match with a pattern

        Attributes:
            pattern = string to match packages
            remote = search on another origin to get packages info
            packages_pattern = String query with binary
                               packages properties: "arch=x86 AND os=Windows"
    """
    packages_props = self._get_search_adapter(remote).search_packages(reference, packages_query)
    ordered_packages = OrderedDict(sorted(packages_props.items()))
    if remote:
        remote_proxy = ConanProxy(self._client_cache, self._user_io, self._remote_manager, remote)
        remote = remote_proxy.registry.remote(remote)
        manifest = self._remote_manager.get_conan_digest(reference, remote)
        recipe_hash = manifest.summary_hash
    else:
        try:
            recipe_hash = self._client_cache.load_manifest(reference).summary_hash
        except IOError:  # It could not exist in local
            recipe_hash = None
    if outdated and recipe_hash:
        ordered_packages = filter_outdated(ordered_packages, recipe_hash)

    return ordered_packages, reference, recipe_hash, packages_query
