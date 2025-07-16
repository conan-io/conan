import fnmatch
import json
import os
from json import JSONDecodeError

from conan.api.model import RecipeReference, PkgReference
from conan.errors import ConanException
from conan.internal.errors import NotFoundException
from conan.internal.model.version_range import VersionRange
from conan.internal.graph.graph import RECIPE_EDITABLE, RECIPE_CONSUMER, RECIPE_PLATFORM, \
    RECIPE_VIRTUAL, BINARY_SKIP, BINARY_MISSING, BINARY_INVALID
from conan.internal.util.files import load


class MultiPackagesList:
    def __init__(self):
        self.lists = {}

    def __getitem__(self, name):
        try:
            return self.lists[name]
        except KeyError:
            raise ConanException(f"'{name}' doesn't exist in package list")

    def add(self, name, pkg_list):
        self.lists[name] = pkg_list

    def add_error(self, remote_name, error):
        self.lists[remote_name] = {"error": error}

    def serialize(self):
        return {k: v.serialize() if isinstance(v, PackagesList) else v
                for k, v in self.lists.items()}

    def merge(self, other):
        for k, v in other.lists.items():
            self.lists.setdefault(k, PackagesList()).merge(v)

    def keep_outer(self, other):
        for namespace, other_pkg_list in other.lists.items():
            self.lists.get(namespace, PackagesList()).keep_outer(other_pkg_list)

    @staticmethod
    def load(file):
        try:
            content = json.loads(load(file))
        except JSONDecodeError as e:
            raise ConanException(f"Package list file invalid JSON: {file}\n{e}")
        except Exception as e:
            raise ConanException(f"Package list file missing or broken: {file}\n{e}")
        # Check if input json is not a graph file
        if "graph" in content:
            base_path = os.path.basename(file)
            raise ConanException(
                'Expected a package list file but found a graph file. You can create a "package list" JSON file by running:\n\n'
                f"\tconan list --graph {base_path} --format=json > pkglist.json\n\n"
                "More Info at 'https://docs.conan.io/2/examples/commands/pkglists.html"
            )
        result = {}
        for remote, pkglist in content.items():
            if "error" in pkglist:
                result[remote] = pkglist
            else:
                result[remote] = PackagesList.deserialize(pkglist)
        pkglist = MultiPackagesList()
        pkglist.lists = result
        return pkglist

    @staticmethod
    def load_graph(graphfile, graph_recipes=None, graph_binaries=None, context=None):
        if not os.path.isfile(graphfile):
            raise ConanException(f"Graph file not found: {graphfile}")
        try:
            base_context = context.split("-")[0] if context else None
            graph = json.loads(load(graphfile))
            # Check if input json is a graph file
            if "graph" not in graph:
                raise ConanException(
                    'Expected a graph file but found an unexpected JSON file format. You can create a "graph" JSON file by running:\n\n'
                    f"\tconan [ graph-info | create | export-pkg | install | test ] --format=json > graph.json\n\n"
                    "More Info at 'https://docs.conan.io/2/reference/commands/formatters/graph_info_json_formatter.html"
                )

            mpkglist =  MultiPackagesList._define_graph(graph, graph_recipes, graph_binaries,
                                                        context=base_context)
            if context == "build-only":
                host = MultiPackagesList._define_graph(graph, graph_recipes, graph_binaries,
                                                       context="host")
                mpkglist.keep_outer(host)
            elif context == "host-only":
                build = MultiPackagesList._define_graph(graph, graph_recipes, graph_binaries,
                                                        context="build")
                mpkglist.keep_outer(build)
            return mpkglist
        except JSONDecodeError as e:
            raise ConanException(f"Graph file invalid JSON: {graphfile}\n{e}")
        except KeyError as e:
            raise ConanException(f'Graph file {graphfile} is missing the required "{e}" key in its contents.\n'
                                 "Note that the graph file should not be filtered "
                                 "if you expect to use it with the list command.")
        except ConanException as e:
            raise e
        except Exception as e:
            raise ConanException(f"Graph file broken: {graphfile}\n{e}")

    @staticmethod
    def _define_graph(graph, graph_recipes=None, graph_binaries=None, context=None):
        pkglist = MultiPackagesList()
        cache_list = PackagesList()
        if graph_recipes is None and graph_binaries is None:
            recipes = ["*"]
            binaries = ["*"]
        else:
            recipes = [r.lower() for r in graph_recipes or []]
            binaries = [b.lower() for b in graph_binaries or []]

        pkglist.lists["Local Cache"] = cache_list
        for node in graph["graph"]["nodes"].values():
            if context and node['context'] != context:
                continue

            # We need to add the python_requires too
            python_requires = node.get("python_requires")
            if python_requires is not None:
                for pyref, pyreq in python_requires.items():
                    pyrecipe = pyreq["recipe"]
                    if pyrecipe == RECIPE_EDITABLE:
                        continue
                    pyref = RecipeReference.loads(pyref)
                    if any(r == "*" or r == pyrecipe for r in recipes):
                        cache_list.add_refs([pyref])
                    pyremote = pyreq["remote"]
                    if pyremote:
                        remote_list = pkglist.lists.setdefault(pyremote, PackagesList())
                        remote_list.add_refs([pyref])

            recipe = node["recipe"]
            if recipe in (RECIPE_EDITABLE, RECIPE_CONSUMER, RECIPE_VIRTUAL, RECIPE_PLATFORM):
                continue

            ref = node["ref"]
            ref = RecipeReference.loads(ref)
            ref.timestamp = node["rrev_timestamp"]
            recipe = recipe.lower()
            if any(r == "*" or r == recipe for r in recipes):
                cache_list.add_refs([ref])

            remote = node["remote"]
            if remote:
                remote_list = pkglist.lists.setdefault(remote, PackagesList())
                remote_list.add_refs([ref])
            pref = PkgReference(ref, node["package_id"], node["prev"], node["prev_timestamp"])
            binary_remote = node["binary_remote"]
            if binary_remote:
                remote_list = pkglist.lists.setdefault(binary_remote, PackagesList())
                remote_list.add_refs([ref])  # Binary listed forces recipe listed
                remote_list.add_prefs(ref, [pref])

            binary = node["binary"]
            if binary in (BINARY_SKIP, BINARY_INVALID, BINARY_MISSING):
                continue

            binary = binary.lower()
            if any(b == "*" or b == binary for b in binaries):
                cache_list.add_refs([ref])  # Binary listed forces recipe listed
                cache_list.add_prefs(ref, [pref])
                cache_list.add_configurations({pref: node["info"]})
        return pkglist


class PackagesList:
    def __init__(self):
        self.recipes = {}

    def merge(self, other):
        def recursive_dict_update(d, u):  # TODO: repeated from conandata.py
            for k, v in u.items():
                if isinstance(v, dict):
                    d[k] = recursive_dict_update(d.get(k, {}), v)
                else:
                    d[k] = v
            return d
        recursive_dict_update(self.recipes, other.recipes)

    def keep_outer(self, other):
        if not self.recipes:
            return

        for ref, info in other.recipes.items():
            if self.recipes.get(ref, {}) == info:
                self.recipes.pop(ref)

    def split(self):
        """
        Returns a list of PackageList, splitted one per reference.
        This can be useful to parallelize things like upload, parallelizing per-reference
        """
        result = []
        for r, content in self.recipes.items():
            subpkglist = PackagesList()
            subpkglist.recipes[r] = content
            result.append(subpkglist)
        return result

    def only_recipes(self):
        result = {}
        for ref, ref_dict in self.recipes.items():
            for rrev_dict in ref_dict.get("revisions", {}).values():
                rrev_dict.pop("packages", None)
        return result

    def add_refs(self, refs):
        # RREVS alreday come in ASCENDING order, so upload does older revisions first
        for ref in refs:
            ref_dict = self.recipes.setdefault(str(ref), {})
            if ref.revision:
                revs_dict = ref_dict.setdefault("revisions", {})
                rev_dict = revs_dict.setdefault(ref.revision, {})
                if ref.timestamp:
                    rev_dict["timestamp"] = ref.timestamp

    def add_prefs(self, rrev, prefs):
        # Prevs already come in ASCENDING order, so upload does older revisions first
        revs_dict = self.recipes[str(rrev)]["revisions"]
        rev_dict = revs_dict[rrev.revision]
        packages_dict = rev_dict.setdefault("packages", {})

        for pref in prefs:
            package_dict = packages_dict.setdefault(pref.package_id, {})
            if pref.revision:
                prevs_dict = package_dict.setdefault("revisions", {})
                prev_dict = prevs_dict.setdefault(pref.revision, {})
                if pref.timestamp:
                    prev_dict["timestamp"] = pref.timestamp

    def add_configurations(self, confs):
        for pref, conf in confs.items():
            rev_dict = self.recipes[str(pref.ref)]["revisions"][pref.ref.revision]
            try:
                rev_dict["packages"][pref.package_id]["info"] = conf
            except KeyError:  # If package_id does not exist, do nothing, only add to existing prefs
                pass

    def refs(self):
        result = {}
        for ref, ref_dict in self.recipes.items():
            for rrev, rrev_dict in ref_dict.get("revisions", {}).items():
                t = rrev_dict.get("timestamp")
                recipe = RecipeReference.loads(f"{ref}#{rrev}")  # TODO: optimize this
                if t is not None:
                    recipe.timestamp = t
                result[recipe] = rrev_dict
        return result

    @staticmethod
    def prefs(ref, recipe_bundle):
        result = {}
        for package_id, pkg_bundle in recipe_bundle.get("packages", {}).items():
            prevs = pkg_bundle.get("revisions", {})
            for prev, prev_bundle in prevs.items():
                t = prev_bundle.get("timestamp")
                pref = PkgReference(ref, package_id, prev, t)
                result[pref] = prev_bundle
        return result

    def serialize(self):
        return self.recipes

    @staticmethod
    def deserialize(data):
        result = PackagesList()
        result.recipes = data
        return result


class ListPattern:

    def __init__(self, expression, rrev="latest", package_id=None, prev="latest", only_recipe=False):
        def split(s, c, default=None):
            if not s:
                return None, default
            tokens = s.split(c, 1)
            if len(tokens) == 2:
                return tokens[0], tokens[1] or default
            return tokens[0], default

        recipe, package = split(expression, ":")
        self.raw = expression
        self.ref, rrev = split(recipe, "#", rrev)
        ref, user_channel = split(self.ref, "@")
        self.name, self.version = split(ref, "/")
        self.user, self.channel = split(user_channel, "/")
        self.rrev, _ = split(rrev, "%")
        self.package_id, prev = split(package, "#", prev)
        self.prev, _ = split(prev, "%")
        if only_recipe:
            if self.package_id:
                raise ConanException("Do not specify 'package_id' with 'only-recipe'")
        else:
            self.package_id = self.package_id or package_id

    @staticmethod
    def _only_latest(rev):
        return rev in ["!latest", "~latest"]

    @property
    def search_ref(self):
        vrange = self._version_range
        if vrange:
            return str(RecipeReference(self.name, "*", self.user, self.channel))
        if "*" in self.ref or not self.version or (self.package_id is None and self.rrev is None):
            return self.ref

    @property
    def _version_range(self):
        if self.version and self.version.startswith("[") and self.version.endswith("]"):
            return VersionRange(self.version[1:-1])

    def filter_versions(self, refs):
        vrange = self._version_range
        if vrange:
            refs = [r for r in refs if vrange.contains(r.version, None)]
        return refs

    @property
    def is_latest_rrev(self):
        return self.rrev == "latest"

    @property
    def is_latest_prev(self):
        return self.prev == "latest"

    def check_refs(self, refs):
        if not refs and self.ref and "*" not in self.ref:
            raise NotFoundException(f"Recipe '{self.ref}' not found")

    def filter_rrevs(self, rrevs):
        if self._only_latest(self.rrev):
            return rrevs[1:]
        rrevs = [r for r in rrevs if fnmatch.fnmatch(r.revision, self.rrev)]
        if not rrevs:
            refs_str = f'{self.ref}#{self.rrev}'
            if "*" not in refs_str:
                raise ConanException(f"Recipe revision '{refs_str}' not found")
        return rrevs

    def filter_prefs(self, prefs):
        prefs = [p for p in prefs if fnmatch.fnmatch(p.package_id, self.package_id)]
        if not prefs:
            refs_str = f'{self.ref}#{self.rrev}:{self.package_id}'
            if "*" not in refs_str:
                raise ConanException(f"Package ID '{self.raw}' not found")
        return prefs

    def filter_prevs(self, prevs):
        if self._only_latest(self.prev):
            return prevs[1:]
        prevs = [p for p in prevs if fnmatch.fnmatch(p.revision, self.prev)]
        if not prevs:
            refs_str = f'{self.ref}#{self.rrev}:{self.package_id}#{self.prev}'
            if "*" not in refs_str:
                raise ConanException(f"Package revision '{self.raw}' not found")
        return prevs
