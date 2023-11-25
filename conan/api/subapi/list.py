from typing import Dict

from conan.api.model import PackagesList
from conan.internal.conan_app import ConanApp
from conans.errors import ConanException, NotFoundException
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference, ref_matches
from conans.search.search import get_cache_packages_binary_info, filter_packages
from conans.util.dates import timelimit


class ListAPI:
    """
    Get references from the recipes and packages in the cache or a remote
    """

    def __init__(self, conan_api):
        self.conan_api = conan_api

    def latest_recipe_revision(self, ref: RecipeReference, remote=None):
        assert ref.revision is None, "latest_recipe_revision: ref already have a revision"
        app = ConanApp(self.conan_api.cache_folder, self.conan_api.config.global_conf)
        if remote:
            ret = app.remote_manager.get_latest_recipe_reference(ref, remote=remote)
        else:
            ret = app.cache.get_latest_recipe_reference(ref)

        return ret

    def recipe_revisions(self, ref: RecipeReference, remote=None):
        assert ref.revision is None, "recipe_revisions: ref already have a revision"
        app = ConanApp(self.conan_api.cache_folder, self.conan_api.config.global_conf)
        if remote:
            results = app.remote_manager.get_recipe_revisions_references(ref, remote=remote)
        else:
            results = app.cache.get_recipe_revisions_references(ref)

        return results

    def latest_package_revision(self, pref: PkgReference, remote=None):
        # TODO: This returns None if the given package_id is not existing. It should probably
        #  raise NotFound, but to keep aligned with the above ``latest_recipe_revision`` which
        #  is used as an "exists" check too in other places, lets respect the None return
        assert pref.revision is None, "latest_package_revision: ref already have a revision"
        assert pref.package_id is not None, "package_id must be defined"
        app = ConanApp(self.conan_api.cache_folder, self.conan_api.config.global_conf)
        if remote:
            ret = app.remote_manager.get_latest_package_reference(pref, remote=remote)
        else:
            ret = app.cache.get_latest_package_reference(pref)
        return ret

    def package_revisions(self, pref: PkgReference, remote=None):
        assert pref.ref.revision is not None, "package_revisions requires a recipe revision, " \
                                              "check latest first if needed"
        app = ConanApp(self.conan_api.cache_folder, self.conan_api.config.global_conf)
        if remote:
            results = app.remote_manager.get_package_revisions_references(pref, remote=remote)
        else:
            results = app.cache.get_package_revisions_references(pref, only_latest_prev=False)
        return results

    def packages_configurations(self, ref: RecipeReference,
                                remote=None) -> Dict[PkgReference, dict]:
        assert ref.revision is not None, "packages: ref should have a revision. " \
                                         "Check latest if needed."
        if not remote:
            app = ConanApp(self.conan_api.cache_folder, self.conan_api.config.global_conf)
            prefs = app.cache.get_package_references(ref)
            packages = get_cache_packages_binary_info(app.cache, prefs)
        else:
            app = ConanApp(self.conan_api.cache_folder, self.conan_api.config.global_conf)
            if ref.revision == "latest":
                ref.revision = None
                ref = app.remote_manager.get_latest_recipe_reference(ref, remote=remote)
            packages = app.remote_manager.search_packages(remote, ref)
        return packages

    @staticmethod
    def filter_packages_configurations(pkg_configurations, query):
        """
        :param pkg_configurations: Dict[PkgReference, PkgConfiguration]
        :param query: str like "os=Windows AND (arch=x86 OR compiler=gcc)"
        :return: Dict[PkgReference, PkgConfiguration]
        """
        return filter_packages(query, pkg_configurations)

    def find_binaries(self, ref, profile=None, remote=None):
        ref = RecipeReference.loads(ref)
        if not ref.revision:
            ref = self.latest_recipe_revision(ref, remote)
            if ref is None:
                raise NotFoundException(f"Recipe '{ref}' not found")

        pkg_configurations = self.packages_configurations(ref, remote)

        profile_settings = profile.settings
        profile_options = profile.options
        profile_pkg_settings = profile.package_settings

        class ConfDistance:
            def __init__(self, pref, data):
                self.pref = pref
                self.data = data
                settings = data.get("settings", {})
                self.platform_diff = {}
                self.settings_diff = {}
                for k, v in settings.items():
                    profile_value = profile_settings.get(k)
                    for pattern, pattern_settings in profile_pkg_settings.items():
                        if ref_matches(ref, pattern, is_consumer=False):
                            profile_value = pattern_settings.get(k) or profile_value
                    if profile_value is not None and profile_value != v:
                        diff = self.platform_diff if k in ("os", "arch") else self.settings_diff
                        diff[k] = profile_value
                self.deps_diff = {}
                self.options_diff = {}
                options = data.get("options", {})
                for k, v in options.items():
                    for pattern, opts in profile_options._deps_package_options.items():
                        if ref_matches(ref, pattern, is_consumer=False):
                            for profile_opt, profile_val in opts.items():
                                if profile_opt == k and profile_val != v:
                                    self.options_diff[k] = profile_val

            def __lt__(self, other):
                return self.distance < other.distance

            def explanation(self):
                if self.platform_diff:
                    return "This binary belongs to another OS or Architecture, highly incompatible."
                if self.settings_diff:
                    return "This binary was built with different settings (compiler, build_type)."
                if self.options_diff:
                    return "This binary was built with the same settings, but different options"
                if self.deps_diff:
                    return "This binary was built with same settings and options, but " \
                           "dependencies are different, so it is not compatible"
                return "This binary is an exact match for the defined inputs"

            @property
            def distance(self):
                return len(self.platform_diff), len(self.settings_diff), \
                       len(self.options_diff), len(self.deps_diff)

            def serialize(self):
                return {"platform": self.platform_diff,
                        "settings": self.settings_diff,
                        "options": self.options_diff,
                        "dependencies": self.deps_diff,
                        "explanation": self.explanation()}

        candidates = [ConfDistance(pref, data) for pref, data in pkg_configurations.items()]
        candidates.sort()
        final_result = PackagesList()
        final_result.add_refs([ref])
        # If there are exact matches, only return the matches
        # else, limit to the number specified
        candidate_distance = None
        for candidate in candidates:
            if candidate_distance and candidate.distance != candidate_distance:
                break
            candidate_distance = candidate.distance
            pref = candidate.pref
            final_result.add_prefs(ref, [pref])
            final_result.add_configurations({pref: candidate.data})
            # Add the diff data
            rev_dict = final_result.recipes[str(pref.ref)]["revisions"][pref.ref.revision]
            rev_dict["packages"][pref.package_id]["diff"] = candidate.serialize()
        return final_result

    def select(self, pattern, package_query=None, remote=None, lru=None):
        if package_query and pattern.package_id and "*" not in pattern.package_id:
            raise ConanException("Cannot specify '-p' package queries, "
                                 "if 'package_id' is not a pattern")
        if remote and lru:
            raise ConanException("'--lru' cannot be used in remotes, only in cache")

        select_bundle = PackagesList()
        # Avoid doing a ``search`` of recipes if it is an exact ref and it will be used later
        search_ref = pattern.search_ref
        app = ConanApp(self.conan_api.cache_folder, self.conan_api.config.global_conf)
        limit_time = timelimit(lru) if lru else None
        if search_ref:
            refs = self.conan_api.search.recipes(search_ref, remote=remote)
            refs = pattern.filter_versions(refs)
            refs = sorted(refs)  # Order alphabetical and older versions first
            pattern.check_refs(refs)
        else:
            refs = [RecipeReference(pattern.name, pattern.version, pattern.user, pattern.channel)]

        # Show only the recipe references
        if pattern.package_id is None and pattern.rrev is None:
            select_bundle.add_refs(refs)
            return select_bundle

        for r in refs:  # Older versions first
            if pattern.is_latest_rrev or pattern.rrev is None:
                rrev = self.latest_recipe_revision(r, remote)
                if rrev is None:
                    raise NotFoundException(f"Recipe '{r}' not found")
                rrevs = [rrev]
            else:
                rrevs = self.recipe_revisions(r, remote)
                rrevs = pattern.filter_rrevs(rrevs)
                rrevs = list(reversed(rrevs))  # Order older revisions first

            if lru and pattern.package_id is None:  # Filter LRUs
                rrevs = [r for r in rrevs if app.cache.get_recipe_lru(r) < limit_time]

            select_bundle.add_refs(rrevs)

            if pattern.package_id is None:  # Stop if not displaying binaries
                continue

            for rrev in rrevs:
                prefs = []
                if "*" not in pattern.package_id and pattern.prev is not None:
                    prefs.append(PkgReference(rrev, package_id=pattern.package_id))
                    packages = {}
                else:
                    packages = self.packages_configurations(rrev, remote)
                    if package_query is not None:
                        packages = self.filter_packages_configurations(packages, package_query)
                    prefs = packages.keys()
                    prefs = pattern.filter_prefs(prefs)
                    packages = {pref: conf for pref, conf in packages.items() if pref in prefs}

                if pattern.prev is not None:
                    new_prefs = []
                    for pref in prefs:
                        # Maybe the package_configurations returned timestamp
                        if pattern.is_latest_prev or pattern.prev is None:
                            prev = self.latest_package_revision(pref, remote)
                            if prev is None:
                                raise NotFoundException(f"Binary package not found: '{pref}")
                            new_prefs.append(prev)
                        else:
                            prevs = self.package_revisions(pref, remote)
                            prevs = pattern.filter_prevs(prevs)
                            prevs = list(reversed(prevs))  # Older revisions first
                            new_prefs.extend(prevs)
                    prefs = new_prefs

                if lru:  # Filter LRUs
                    prefs = [r for r in prefs if app.cache.get_package_lru(r) < limit_time]

                select_bundle.add_prefs(rrev, prefs)
                select_bundle.add_configurations(packages)
        return select_bundle
