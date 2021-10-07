import json
import os

from conans.errors import ConanException
from conans.model.graph_lock import GraphLockFile
from conans.util.files import load, save


class LockBundle(object):
    """ aggregated view of multiple lockfiles, coming from different configurations and also
    different products, that is, completely independent graphs, that could have incompatible
    versions. This bundle is not useful for restoring a state for a configuration, cannot be
    used to lock a graph, but it it useful for computing the build order in CI for multiple
    products. The format is a json with: For every reference, for each "package_id" for that
    reference, list the lockfiles that contain such reference:package_id and the node indexes
    inside that lockfile

    lock_bundle": {
        "app1/0.1@#584778f98ba1d0eb7c80a5ae1fe12fe2": {
            "packages": [
                {
                    "package_id": "3bcd6800847f779e0883ee91b411aad9ddd8e83c",
                    "lockfiles": {
                        "app1_windows.lock": [
                            "1"
                        ]
                    },
                    "prev": null,
                    "modified": null
                },
            ],
            "requires": [
                "pkgb/0.1@#cd8f22d6f264f65398d8c534046e8e20",
                "tool/0.1@#f096d7d54098b7ad7012f9435d9c33f3"
            ]
        },
    """

    def __init__(self):
        self._nodes = {}

    @staticmethod
    def create(lockfiles, revisions_enabled, cwd):
        def ref_convert(r):
            # Necessary so "build-order" output is usable by install
            if "@" not in r:
                if "#" in r:
                    r = r.replace("#", "@#")
                else:
                    r += "@"
            return r

        result = LockBundle()
        for lockfile_name in lockfiles:
            lockfile_abs = os.path.normpath(os.path.join(cwd, lockfile_name))
            lockfile = GraphLockFile.load(lockfile_abs, revisions_enabled)

            lock = lockfile.graph_lock
            for id_, node in lock.nodes.items():
                ref_str = node.ref.full_str()
                ref_str = ref_convert(ref_str)
                ref_node = result._nodes.setdefault(ref_str, {})
                packages_node = ref_node.setdefault("packages", [])
                # Find existing package_id in the list of packages
                # This is the equivalent of a setdefault over a dict, but on a list
                for pkg in packages_node:
                    if pkg["package_id"] == node.package_id:
                        pid_node = pkg
                        break
                else:
                    pid_node = {"package_id": node.package_id}
                    packages_node.append(pid_node)
                ids = pid_node.setdefault("lockfiles", {})
                # TODO: Add check that this prev is always the same
                pid_node["prev"] = node.prev
                pid_node["modified"] = node.modified
                ids.setdefault(lockfile_name, []).append(id_)
                total_requires = node.requires + node.build_requires
                for require in total_requires:
                    require_node = lock.nodes[require]
                    ref = require_node.ref.full_str()
                    ref = ref_convert(ref)
                    requires = ref_node.setdefault("requires", [])
                    if ref not in requires:
                        requires.append(ref)

        return result

    def dumps(self):
        return json.dumps({"lock_bundle": self._nodes}, indent=4)

    def loads(self, text):
        nodes_json = json.loads(text)
        self._nodes = nodes_json["lock_bundle"]

    def build_order(self):
        # First do a topological order by levels, the ids of the nodes are stored
        levels = []
        opened = list(self._nodes.keys())
        while opened:
            current_level = []
            closed = []
            for o in opened:
                node = self._nodes[o]
                requires = node.get("requires", [])
                if not any(n in opened for n in requires):  # Doesn't have an open requires
                    # iterate all packages to see if some has prev=null
                    if any(pkg["prev"] is None for pkg in node["packages"]):
                        current_level.append(o)
                    closed.append(o)

            if current_level:
                current_level.sort()
                levels.append(current_level)
            # now initialize new level
            opened = set(opened).difference(closed)

        return levels

    @staticmethod
    def update_bundle(bundle_path, revisions_enabled):
        """ Update both the bundle information as well as every individual lockfile, from the
        information that was modified in the individual lockfile. At the end, all lockfiles will
        have the same PREV for the binary of same package_id
        """
        bundle = LockBundle()
        bundle.loads(load(bundle_path))
        for node in bundle._nodes.values():
            # Each node in bundle belongs to a "ref", and contains lockinfo for every package_id
            for pkg in node["packages"]:
                # Each package_id contains information of multiple lockfiles

                # First, compute the modified PREV from all lockfiles
                prev = modified = prev_lockfile = None
                for lockfile, nodes_ids in pkg["lockfiles"].items():
                    graph_lock_conf = GraphLockFile.load(lockfile, revisions_enabled)
                    graph_lock = graph_lock_conf.graph_lock

                    for node_id in nodes_ids:
                        # Make sure the PREV from lockfiles is consistent, it cannot be different
                        lock_prev = graph_lock.nodes[node_id].prev
                        if prev is None:
                            prev = lock_prev
                            prev_lockfile = lockfile
                            modified = graph_lock.nodes[node_id].modified
                        elif lock_prev is not None and prev != lock_prev:
                            ref = graph_lock.nodes[node_id].ref
                            msg = "Lock mismatch for {} prev: {}:{} != {}:{}".format(
                                ref, prev_lockfile, prev, lockfile, lock_prev)
                            raise ConanException(msg)
                pkg["prev"] = prev
                pkg["modified"] = modified

                # Then, update all prev of all config lockfiles
                for lockfile, nodes_ids in pkg["lockfiles"].items():
                    graph_lock_conf = GraphLockFile.load(lockfile, revisions_enabled)
                    graph_lock = graph_lock_conf.graph_lock
                    for node_id in nodes_ids:
                        if graph_lock.nodes[node_id].prev is None:
                            graph_lock.nodes[node_id].prev = prev
                    graph_lock_conf.save(lockfile)

        save(bundle_path, bundle.dumps())

    @staticmethod
    def clean_modified(bundle_path, revisions_enabled):
        bundle = LockBundle()
        bundle.loads(load(bundle_path))
        for node in bundle._nodes.values():
            for pkg in node["packages"]:
                pkg["modified"] = None

                for lockfile, nodes_ids in pkg["lockfiles"].items():
                    graph_lock_conf = GraphLockFile.load(lockfile, revisions_enabled)
                    graph_lock_conf.graph_lock.clean_modified()
                    graph_lock_conf.save(lockfile)

        save(bundle_path, bundle.dumps())
