from typing import Dict

from conan.api.model import Remote, SelectBundle
from conan.internal.conan_app import ConanApp
from conans.errors import ConanException, NotFoundException
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.search.search import get_cache_packages_binary_info, filter_packages


class ListAPI:
    """
    Get references from the recipes and packages in the cache or a remote
    """

    def __init__(self, conan_api):
        self.conan_api = conan_api

    def latest_recipe_revision(self, ref: RecipeReference, remote=None):
        assert ref.revision is None, "latest_recipe_revision: ref already have a revision"
        app = ConanApp(self.conan_api.cache_folder)
        if remote:
            ret = app.remote_manager.get_latest_recipe_reference(ref, remote=remote)
        else:
            ret = app.cache.get_latest_recipe_reference(ref)

        return ret

    def recipe_revisions(self, ref: RecipeReference, remote=None):
        assert ref.revision is None, "recipe_revisions: ref already have a revision"
        app = ConanApp(self.conan_api.cache_folder)
        if remote:
            results = app.remote_manager.get_recipe_revisions_references(ref, remote=remote)
        else:
            results = app.cache.get_recipe_revisions_references(ref, only_latest_rrev=False)

        return results

    def latest_package_revision(self, pref: PkgReference, remote=None):
        # TODO: This returns None if the given package_id is not existing. It should probably
        #  raise NotFound, but to keep aligned with the above ``latest_recipe_revision`` which
        #  is used as an "exists" check too in other places, lets respect the None return
        assert pref.revision is None, "latest_package_revision: ref already have a revision"
        assert pref.package_id is not None, "package_id must be defined"
        app = ConanApp(self.conan_api.cache_folder)
        if remote:
            ret = app.remote_manager.get_latest_package_reference(pref, remote=remote)
        else:
            ret = app.cache.get_latest_package_reference(pref)
        return ret

    def package_revisions(self, pref: PkgReference, remote: Remote=None):
        assert pref.ref.revision is not None, "package_revisions requires a recipe revision, " \
                                              "check latest first if needed"
        app = ConanApp(self.conan_api.cache_folder)
        if remote:
            results = app.remote_manager.get_package_revisions_references(pref, remote=remote)
        else:
            refs = app.cache.get_package_revisions_references(pref, only_latest_prev=False)
            results = []
            for ref in refs:
                # TODO: Why another call, and why get_package_revisions_references doesn't return
                #  already the timestamps?
                timestamp = app.cache.get_package_timestamp(ref)
                ref.timestamp = timestamp
                results.append(ref)
        return results

    def packages_configurations(self, ref: RecipeReference,
                                remote=None) -> Dict[PkgReference, dict]:
        assert ref.revision is not None, "packages: ref should have a revision. " \
                                         "Check latest if needed."
        if not remote:
            app = ConanApp(self.conan_api.cache_folder)
            prefs = app.cache.get_package_references(ref)
            packages = get_cache_packages_binary_info(app.cache, prefs)
        else:
            app = ConanApp(self.conan_api.cache_folder)
            if ref.revision == "latest":
                ref.revision = None
                ref = app.remote_manager.get_latest_recipe_reference(ref, remote=remote)
            packages = app.remote_manager.search_packages(remote, ref)
        return packages

    def filter_packages_configurations(self, pkg_configurations, query):
        """
        :param pkg_configurations: Dict[PkgReference, PkgConfiguration]
        :param query: str like "os=Windows AND (arch=x86 OR compiler=gcc)"
        :return: Dict[PkgReference, PkgConfiguration]
        """
        return filter_packages(query, pkg_configurations)

    # TODO: could it be possible to merge this with subapi.search.select?
    def select(self, pattern, package_query=None, remote=None):
        if package_query and pattern.package_id and "*" not in pattern.package_id:
            raise ConanException("Cannot specify '-p' package queries, "
                                 "if 'package_id' is not a pattern")
        select_bundle = SelectBundle()
        # Avoid doing a ``search`` of recipes if it is an exact ref and it will be used later
        if "*" in pattern.ref or not pattern.version or \
                (pattern.package_id is None and pattern.rrev is None):
            refs = self.conan_api.search.recipes(pattern.ref, remote=remote)
            pattern.check_refs(refs)
        else:
            refs = [RecipeReference(pattern.name, pattern.version, pattern.user, pattern.channel)]

        # Show only the recipe references
        if pattern.package_id is None and pattern.rrev is None:
            select_bundle.add_refs(refs)
            return select_bundle

        for r in refs:
            if pattern.is_latest_rrev or pattern.rrev is None:
                rrevs = [self.conan_api.list.latest_recipe_revision(r, remote)]
            else:
                rrevs = self.conan_api.list.recipe_revisions(r, remote)
                rrevs = pattern.filter_rrevs(rrevs)
            select_bundle.add_refs(rrevs)

            if pattern.package_id is None:  # Stop if not displaying binaries
                continue

            for rrev in rrevs:
                prefs = []
                if "*" not in pattern.package_id and pattern.prev is not None:
                    prefs.append(PkgReference(rrev, package_id=pattern.package_id))
                else:
                    packages = self.conan_api.list.packages_configurations(rrev, remote)
                    if package_query is not None:
                        packages = self.conan_api.list.filter_packages_configurations(packages,
                                                                                      package_query)
                    prefs = packages.keys()
                    prefs = pattern.filter_prefs(prefs)
                    select_bundle.add_configurations(packages)

                if pattern.prev is not None:
                    new_prefs = []
                    for pref in prefs:
                        # Maybe the package_configurations returned timestamp
                        if pattern.is_latest_prev or pattern.prev is None:
                            prev = self.conan_api.list.latest_package_revision(pref, remote)
                            if prev is None:
                                raise NotFoundException(f"Binary package not found: '{pref}")
                            new_prefs.append(prev)
                        else:
                            prevs = self.conan_api.list.package_revisions(pref, remote)
                            prevs = pattern.filter_prevs(prevs)
                            new_prefs.extend(prevs)
                    prefs = new_prefs

                select_bundle.add_prefs(prefs)
        return select_bundle
