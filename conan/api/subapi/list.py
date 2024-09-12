import os
from collections import OrderedDict
from typing import Dict

from conan.api.model import PackagesList
from conan.api.output import ConanOutput, TimedOutput
from conan.internal.api.list.query_parse import filter_package_configs
from conan.internal.conan_app import ConanApp
from conan.internal.paths import CONANINFO
from conans.errors import ConanException, NotFoundException
from conans.model.info import load_binary_info
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference, ref_matches
from conans.util.dates import timelimit
from conans.util.files import load


class ListAPI:
    """
    Get references from the recipes and packages in the cache or a remote
    """

    def __init__(self, conan_api):
        self.conan_api = conan_api

    def latest_recipe_revision(self, ref: RecipeReference, remote=None):
        assert ref.revision is None, "latest_recipe_revision: ref already have a revision"
        app = ConanApp(self.conan_api)
        if remote:
            ret = app.remote_manager.get_latest_recipe_reference(ref, remote=remote)
        else:
            ret = app.cache.get_latest_recipe_reference(ref)

        return ret

    def recipe_revisions(self, ref: RecipeReference, remote=None):
        assert ref.revision is None, "recipe_revisions: ref already have a revision"
        app = ConanApp(self.conan_api)
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
        app = ConanApp(self.conan_api)
        if remote:
            ret = app.remote_manager.get_latest_package_reference(pref, remote=remote)
        else:
            ret = app.cache.get_latest_package_reference(pref)
        return ret

    def package_revisions(self, pref: PkgReference, remote=None):
        assert pref.ref.revision is not None, "package_revisions requires a recipe revision, " \
                                              "check latest first if needed"
        app = ConanApp(self.conan_api)
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
            app = ConanApp(self.conan_api)
            prefs = app.cache.get_package_references(ref)
            packages = _get_cache_packages_binary_info(app.cache, prefs)
        else:
            app = ConanApp(self.conan_api)
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
        if query is None:
            return pkg_configurations
        try:
            if "!" in query:
                raise ConanException("'!' character is not allowed")
            if "~" in query:
                raise ConanException("'~' character is not allowed")
            if " not " in query or query.startswith("not "):
                raise ConanException("'not' operator is not allowed")
            return filter_package_configs(pkg_configurations, query)
        except Exception as exc:
            raise ConanException("Invalid package query: %s. %s" % (query, exc))

    @staticmethod
    def filter_packages_profile(packages, profile, ref):
        result = {}
        profile_settings = profile.processed_settings.serialize()
        # Options are those for dependencies, like *:shared=True
        profile_options = profile.options._deps_package_options
        for pref, data in packages.items():
            settings = data.get("settings", {})
            settings_match = options_match = True
            for k, v in settings.items():  # Only the defined settings that don't match
                value = profile_settings.get(k)
                if value is not None and value != v:
                    settings_match = False
                    break
            options = data.get("options", {})
            for k, v in options.items():
                for pattern, pattern_options in profile_options.items():
                    # Accept &: as referring to the current package being listed,
                    # even if it's not technically a "consumer"
                    if ref_matches(ref, pattern, True):
                        value = pattern_options.get_safe(k)
                        if value is not None and value != v:
                            options_match = False
                            break

            if settings_match and options_match:
                result[pref] = data

        return result

    def select(self, pattern, package_query=None, remote=None, lru=None, profile=None):
        if package_query and pattern.package_id and "*" not in pattern.package_id:
            raise ConanException("Cannot specify '-p' package queries, "
                                 "if 'package_id' is not a pattern")
        if remote and lru:
            raise ConanException("'--lru' cannot be used in remotes, only in cache")

        select_bundle = PackagesList()
        # Avoid doing a ``search`` of recipes if it is an exact ref and it will be used later
        search_ref = pattern.search_ref
        app = ConanApp(self.conan_api)
        limit_time = timelimit(lru) if lru else None
        out = ConanOutput()
        remote_name = "local cache" if not remote else remote.name
        if search_ref:
            refs = self.conan_api.search.recipes(search_ref, remote=remote)
            refs = pattern.filter_versions(refs)
            refs = sorted(refs)  # Order alphabetical and older versions first
            pattern.check_refs(refs)
            out.info(f"Found {len(refs)} pkg/version recipes matching {search_ref} in {remote_name}")
        else:
            refs = [RecipeReference(pattern.name, pattern.version, pattern.user, pattern.channel)]

        # Show only the recipe references
        if pattern.package_id is None and pattern.rrev is None:
            select_bundle.add_refs(refs)
            return select_bundle

        def msg_format(msg, item, total):
            return msg + f" ({total.index(item)}/{len(total)})"

        trefs = TimedOutput(5, msg_format=msg_format)
        for r in refs:  # Older versions first
            trefs.info(f"Listing revisions of {r} in {remote_name}", r, refs)
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

            trrevs = TimedOutput(5, msg_format=msg_format)
            for rrev in rrevs:
                trrevs.info(f"Listing binaries of {rrev.repr_notime()} in {remote_name}", rrev, rrevs)
                prefs = []
                if "*" not in pattern.package_id and pattern.prev is not None:
                    prefs.append(PkgReference(rrev, package_id=pattern.package_id))
                    packages = {}
                else:
                    packages = self.packages_configurations(rrev, remote)
                    if package_query is not None:
                        packages = self.filter_packages_configurations(packages, package_query)
                    if profile is not None:
                        packages = self.filter_packages_profile(packages, profile, rrev)
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

    def explain_missing_binaries(self, ref, conaninfo, remotes):
        ConanOutput().info(f"Missing binary: {ref}")
        ConanOutput().info(f"With conaninfo.txt (package_id):\n{conaninfo.dumps()}")
        conaninfo = load_binary_info(conaninfo.dumps())
        # Collect all configurations
        candidates = []
        ConanOutput().info(f"Finding binaries in the cache")
        pkg_configurations = self.packages_configurations(ref)
        candidates.extend(_BinaryDistance(pref, data, conaninfo)
                          for pref, data in pkg_configurations.items())

        for remote in remotes:
            try:
                ConanOutput().info(f"Finding binaries in remote {remote.name}")
                pkg_configurations = self.packages_configurations(ref, remote=remote)
            except Exception as e:
                ConanOutput(f"ERROR IN REMOTE {remote.name}: {e}")
            else:
                candidates.extend(_BinaryDistance(pref, data, conaninfo, remote)
                                  for pref, data in pkg_configurations.items())

        candidates.sort()
        pkglist = PackagesList()
        pkglist.add_refs([ref])
        # Return the closest matches, stop adding when distance is increased
        candidate_distance = None
        for candidate in candidates:
            if candidate_distance and candidate.distance != candidate_distance:
                break
            candidate_distance = candidate.distance
            pref = candidate.pref
            pkglist.add_prefs(ref, [pref])
            pkglist.add_configurations({pref: candidate.binary_config})
            # Add the diff data
            rev_dict = pkglist.recipes[str(pref.ref)]["revisions"][pref.ref.revision]
            rev_dict["packages"][pref.package_id]["diff"] = candidate.serialize()
            remote = candidate.remote.name if candidate.remote else "Local Cache"
            rev_dict["packages"][pref.package_id]["remote"] = remote
        return pkglist


class _BinaryDistance:
    def __init__(self, pref, binary, expected, remote=None):
        self.remote = remote
        self.pref = pref
        self.binary_config = binary

        # Settings, special handling for os/arch
        binary_settings = binary.get("settings", {})
        expected_settings = expected.get("settings", {})

        platform = {k: v for k, v in binary_settings.items() if k in ("os", "arch")}
        expected_platform = {k: v for k, v in expected_settings.items() if k in ("os", "arch")}
        self.platform_diff = self._calculate_diff(platform, expected_platform)

        binary_settings = {k: v for k, v in binary_settings.items() if k not in ("os", "arch")}
        expected_settings = {k: v for k, v in expected_settings.items() if k not in ("os", "arch")}
        self.settings_diff = self._calculate_diff(binary_settings, expected_settings)

        self.settings_target_diff = self._calculate_diff(binary, expected, "settings_target")
        self.options_diff = self._calculate_diff(binary, expected, "options")
        self.deps_diff = self._requirement_diff(binary, expected, "requires")
        self.build_requires_diff = self._requirement_diff(binary, expected, "build_requires")
        self.python_requires_diff = self._requirement_diff(binary, expected, "python_requires")
        self.confs_diff = self._calculate_diff(binary,  expected, "conf")

    @staticmethod
    def _requirement_diff(binary_requires, expected_requires, item):
        binary_requires = binary_requires.get(item, {})
        expected_requires = expected_requires.get(item, {})
        output = {}
        binary_requires = [RecipeReference.loads(r) for r in binary_requires]
        expected_requires = [RecipeReference.loads(r) for r in expected_requires]
        binary_requires = {r.name: r for r in binary_requires}
        for r in expected_requires:
            existing = binary_requires.get(r.name)
            if not existing or r != existing:
                output.setdefault("expected", []).append(repr(r))
                output.setdefault("existing", []).append(repr(existing))
        expected_requires = {r.name: r for r in expected_requires}
        for r in binary_requires.values():
            existing = expected_requires.get(r.name)
            if not existing or r != existing:
                if repr(existing) not in output.get("expected", ()):
                    output.setdefault("expected", []).append(repr(existing))
                if repr(r) not in output.get("existing", ()):
                    output.setdefault("existing", []).append(repr(r))
        return output

    @staticmethod
    def _calculate_diff(binary_confs, expected_confs, item=None):
        if item is not None:
            binary_confs = binary_confs.get(item, {})
            expected_confs = expected_confs.get(item, {})
        output = {}
        for k, v in expected_confs.items():
            value = binary_confs.get(k)
            if value != v:
                output.setdefault("expected", []).append(f"{k}={v}")
                output.setdefault("existing", []).append(f"{k}={value}")
        for k, v in binary_confs.items():
            value = expected_confs.get(k)
            if value != v:
                if f"{k}={value}" not in output.get("expected", ()):
                    output.setdefault("expected", []).append(f"{k}={value}")
                if f"{k}={v}" not in output.get("existing", ()):
                    output.setdefault("existing", []).append(f"{k}={v}")
        return output

    def __lt__(self, other):
        return self.distance < other.distance

    def explanation(self):
        if self.platform_diff:
            return "This binary belongs to another OS or Architecture, highly incompatible."
        if self.settings_diff:
            return "This binary was built with different settings."
        if self.settings_target_diff:
            return "This binary was built with different settings_target."
        if self.options_diff:
            return "This binary was built with the same settings, but different options"
        if self.deps_diff:
            return "This binary has same settings and options, but different dependencies"
        if self.build_requires_diff:
            return "This binary has same settings, options and dependencies, but different build_requires"
        if self.python_requires_diff:
            return "This binary has same settings, options and dependencies, but different python_requires"
        if self.confs_diff:
            return "This binary has same settings, options and dependencies, but different confs"
        return "This binary is an exact match for the defined inputs"

    @property
    def distance(self):
        return (len(self.platform_diff.get("expected", [])),
                len(self.settings_diff.get("expected", [])),
                len(self.settings_target_diff.get("expected", [])),
                len(self.options_diff.get("expected", [])),
                len(self.deps_diff.get("expected", [])),
                len(self.build_requires_diff.get("expected", [])),
                len(self.python_requires_diff.get("expected", [])),
                len(self.confs_diff.get("expected", [])))

    def serialize(self):
        return {"platform": self.platform_diff,
                "settings": self.settings_diff,
                "settings_target": self.settings_target_diff,
                "options": self.options_diff,
                "dependencies": self.deps_diff,
                "build_requires": self.build_requires_diff,
                "python_requires": self.python_requires_diff,
                "confs": self.confs_diff,
                "explanation": self.explanation()}


def _get_cache_packages_binary_info(cache, prefs) -> Dict[PkgReference, dict]:
    """
    param package_layout: Layout for the given reference
    """

    result = OrderedDict()

    for pref in prefs:
        latest_prev = cache.get_latest_package_reference(pref)
        pkg_layout = cache.pkg_layout(latest_prev)

        # Read conaninfo
        info_path = os.path.join(pkg_layout.package(), CONANINFO)
        if not os.path.exists(info_path):
            raise ConanException(f"Corrupted package '{pkg_layout.reference}' "
                                 f"without conaninfo.txt in: {info_path}")
        conan_info_content = load(info_path)
        info = load_binary_info(conan_info_content)
        pref = pkg_layout.reference
        # The key shoudln't have the latest package revision, we are asking for package configs
        pref.revision = None
        result[pkg_layout.reference] = info

    return result
