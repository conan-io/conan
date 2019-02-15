from six.moves.urllib.parse import urlencode

from conans.model.ref import ConanFileReference
from conans.model.rest_routes import RestRoutes
from conans.paths import CONAN_MANIFEST, CONANINFO


def _format_ref(url, ref):
    url = url.format(name=ref.name, version=ref.version, username=ref.user,
                     channel=ref.channel, revision=ref.revision)
    return url


def _format_pref(url, pref):
    ref = pref.ref
    url = url.format(name=ref.name, version=ref.version, username=ref.user,
                     channel=ref.channel, revision=ref.revision, package_id=pref.id,
                     p_revision=pref.revision)
    return url


routes = RestRoutes()


class ClientCommonRouter(object):
    """Search urls shared between v1 and v2"""

    def ping(self):
        return self.base_url + routes.ping

    def search(self, pattern, ignorecase):
        """URL search recipes"""
        query = ''
        if pattern:
            if isinstance(pattern, ConanFileReference):
                pattern = pattern.full_repr()
            params = {"q": pattern}
            if not ignorecase:
                params["ignorecase"] = "False"
            query = "?%s" % urlencode(params)
        return self.base_url + "%s%s" % (routes.common_search, query)

    def search_packages(self, ref, query=None):
        """URL search packages for a recipe"""
        route = routes.common_search_packages_revision \
            if ref.revision else routes.common_search_packages
        url = _format_ref(route, ref)
        if query:
            url += "?%s" % urlencode({"q": query})
        return self.base_url + url

    def common_authenticate(self):
        return self.base_url + routes.common_authenticate

    def common_check_credentials(self):
        return self.base_url + routes.common_check_credentials


class ClientV1Router(ClientCommonRouter):
    """Builds urls for v1"""

    def __init__(self, base_url):
        self.base_url = "{}/v1/".format(base_url)

    def search_packages(self, ref, query=None):
        ref = ref.copy_clear_rev()
        return super(ClientV1Router, self).search_packages(ref, query)

    def remove_recipe(self, ref):
        """Remove recipe"""
        return self.base_url + self._for_recipe(ref.copy_clear_rev())

    def remove_recipe_files(self, ref):
        """Removes files from the recipe"""
        return self.base_url + _format_ref(routes.v1_remove_recipe_files, ref.copy_clear_rev())

    def remove_packages(self, ref):
        """Remove files from a package"""
        return self.base_url + _format_ref(routes.v1_remove_packages, ref.copy_clear_rev())

    def recipe_snapshot(self, ref):
        """get recipe manifest url"""
        return self.base_url + self._for_recipe(ref.copy_clear_rev())

    def package_snapshot(self, pref):
        """get recipe manifest url"""
        return self.base_url + self._for_package(pref.copy_clear_rev())

    def recipe_manifest(self, ref):
        """get recipe manifest url"""
        return self.base_url + _format_ref(routes.v1_recipe_digest, ref.copy_clear_rev())

    def package_manifest(self, pref):
        """get manifest url"""
        return self.base_url + _format_pref(routes.v1_package_digest, pref.copy_clear_rev())

    def recipe_download_urls(self, ref):
        """ urls to download the recipe"""
        return self.base_url + _format_ref(routes.v1_recipe_download_urls,
                                           ref.copy_clear_rev())

    def package_download_urls(self, pref):
        """ urls to download the package"""
        pref = pref.copy_with_revs(None, None)
        return self.base_url + _format_pref(routes.v1_package_download_urls, pref)

    def recipe_upload_urls(self, ref):
        """ urls to upload the recipe"""
        return self.base_url + _format_ref(routes.v1_recipe_upload_urls, ref.copy_clear_rev())

    def package_upload_urls(self, pref):
        """ urls to upload the package"""
        pref = pref.copy_with_revs(None, None)
        return self.base_url + _format_pref(routes.v1_package_upload_urls, pref)

    @staticmethod
    def _for_recipe(ref):
        return _format_ref(routes.recipe, ref.copy_clear_rev())

    @staticmethod
    def _for_package(pref):
        pref = pref.copy_with_revs(None, None)
        return _format_pref(routes.package, pref)


class ClientV2Router(ClientCommonRouter):
    """Builds urls for v2"""

    def __init__(self, base_url):
        self.base_url = "{}/v2/".format(base_url)

    def recipe_latest(self, ref, path):
        """Recipe file url"""
        return self.base_url + self._for_recipe(ref, path)

    def recipe_file(self, ref, path):
        """Recipe file url"""
        return self.base_url + self._for_recipe_file(ref, path)

    def package_file(self, pref, path):
        """Package file url"""
        return self.base_url + self._for_package_file(pref, path)

    def remove_recipe(self, ref):
        """Remove recipe url"""
        return self.base_url + self._for_recipe(ref)

    def recipe_revisions(self, ref):
        """Get revisions for a recipe url"""
        return self.base_url + _format_ref(routes.recipe_revisions, ref)

    def remove_package(self, pref):
        """Remove package url"""
        assert pref.revision is not None, "remove_package v2 needs PREV"
        return self.base_url + self._for_package(pref)

    def remove_all_packages(self, ref):
        """Remove package url"""
        return self.base_url + self._for_packages(ref)

    def recipe_manifest(self, ref):
        """Get the url for getting a conanmanifest.txt from a recipe"""
        return self.base_url + self._for_recipe_file(ref, CONAN_MANIFEST)

    def package_manifest(self, pref):
        """Get the url for getting a conanmanifest.txt from a package"""
        return self.base_url + self._for_package_file(pref, CONAN_MANIFEST)

    def package_info(self, pref):
        """Get the url for getting a conaninfo.txt from a package"""
        return self.base_url + self._for_package_file(pref, CONANINFO)

    def recipe_snapshot(self, ref):
        """get recipe manifest url"""
        return self.base_url + self._for_recipe_files(ref)

    def package_snapshot(self, pref):
        """get recipe manifest url"""
        return self.base_url + self._for_package_files(pref)

    def package_revisions(self, pref):
        """get revisions for a package url"""
        return self.base_url + _format_pref(routes.package_revisions, pref)

    def package_latest(self, pref):
        """Get the latest of a package"""
        assert pref.ref.revision is not None, "Cannot get the latest package without RREV"
        return self.base_url + _format_pref(routes.package_revision_latest, pref)

    def recipe_latest(self, ref):
        """Get the latest of a recipe"""
        assert ref.revision is None, "for_recipe_latest shouldn't receive RREV"
        return self.base_url + _format_ref(routes.recipe_latest, ref)

    @staticmethod
    def _for_package_file(pref, path):
        """url for getting a file from a package, with revisions"""
        assert pref.ref.revision is not None, "_for_package_file needs RREV"
        assert pref.revision is not None, "_for_package_file needs PREV"
        return ClientV2Router._format_pref_path(routes.package_revision_file, pref, path)

    @staticmethod
    def _for_package_files(pref):
        """url for getting the recipe list"""
        assert pref.revision is not None, "_for_package_files needs PREV"
        assert pref.ref.revision is not None, "_for_package_files needs RREV"
        return _format_pref(routes.package_revision_files, pref)

    @staticmethod
    def _for_recipe_file(ref, path):
        """url for a recipe file, with or without revisions"""
        assert ref.revision is not None, "for_recipe_file needs RREV"
        return ClientV2Router._format_ref_path(routes.recipe_revision_file, ref, path)

    @staticmethod
    def _for_recipe_files(ref):
        """url for getting the recipe list"""
        assert ref.revision is not None, "for_recipe_files needs RREV"
        return _format_ref(routes.recipe_revision_files, ref)

    @staticmethod
    def _for_recipe(ref):
        """url for a recipe with or without revisions (without rev,
        only for delete the root recipe, or v1)"""
        return _format_ref(routes.recipe_revision, ref)

    @staticmethod
    def _for_packages(ref):
        """url for a recipe with or without revisions"""
        return _format_ref(routes.packages_revision, ref)

    @staticmethod
    def _for_package(pref):
        """url for the package with or without revisions"""
        return _format_pref(routes.package_revision, pref)

    @staticmethod
    def _for_recipe_root(ref):
        return _format_ref(routes.recipe, ref.copy_clear_rev())

    @staticmethod
    def _for_package_root(pref):
        pref = pref.copy_with_revs(None, None)
        return _format_pref(routes.package, pref)

    @staticmethod
    def _format_ref_path(url, ref, path):
        return url.format(name=ref.name, version=ref.version, username=ref.user,
                          channel=ref.channel, revision=ref.revision, path=path)

    @staticmethod
    def _format_pref_path(url, pref, path):
        ref = pref.ref
        return url.format(name=ref.name, version=ref.version, username=ref.user,
                          channel=ref.channel, revision=ref.revision, package_id=pref.id,
                          p_revision=pref.revision, path=path)
