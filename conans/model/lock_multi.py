import json
import os

from conans.model.graph_lock import GraphLockFile
from conans.util.files import load, save


class LockMulti(object):

    def __init__(self):
        self.nodes = {}

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

        result = LockMulti()
        for lockfile_name in lockfiles:
            lockfile_abs = os.path.normpath(os.path.join(cwd, lockfile_name))
            lockfile = GraphLockFile.load(lockfile_abs, revisions_enabled)

            lock = lockfile.graph_lock
            for id_, node in lock.nodes.items():
                ref_str = node.ref.full_str()
                ref_str = ref_convert(ref_str)
                ref_node = result.nodes.setdefault(ref_str, {})
                pids_node = ref_node.setdefault("package_id", {})
                pid_node = pids_node.setdefault(node.package_id, {})
                # TODO: Handle multiple repeated refs in same lockfile
                ids = pid_node.setdefault("lockfiles", {})
                # TODO: Add check that this prev is always the same
                pid_node["prev"] = node.prev
                pid_node["modified"] = node.modified
                ids.setdefault(lockfile_name, []).append(id_)
                for require in node.requires:
                    require_node = lock.nodes[require]
                    ref = require_node.ref.full_str()
                    ref = ref_convert(ref)
                    requires = ref_node.setdefault("requires", [])
                    if ref not in requires:
                        requires.append(ref)

        return result

    def dumps(self):
        return json.dumps(self.nodes, indent=4)

    def loads(self, text):
        nodes_json = json.loads(text)
        self.nodes = nodes_json

    def build_order(self):
        # First do a topological order by levels, the ids of the nodes are stored
        levels = []
        opened = list(self.nodes.keys())
        while opened:
            current_level = []
            for o in opened:
                node = self.nodes[o]
                requires = node.get("requires", [])
                if not any(n in opened for n in requires):
                    current_level.append(o)

            current_level.sort()
            levels.append(current_level)
            # now initialize new level
            opened = set(opened).difference(current_level)

        return levels

    @staticmethod
    def update_multi(multi_lock_path, revisions_enabled):
        lock_multi = LockMulti()
        lock_multi.loads(load(multi_lock_path))
        for ref, packages in lock_multi.nodes.items():
            for package_id, lock_info in packages["package_id"].items():
                # First, update all prev, modified in the multi.lock
                for lockfile, nodes_ids in lock_info["lockfiles"].items():
                    graph_lock_conf = GraphLockFile.load(lockfile, revisions_enabled)
                    graph_lock = graph_lock_conf.graph_lock
                    for node_id in nodes_ids:
                        lock_info["prev"] = lock_info["prev"] or graph_lock.nodes[node_id].prev
                        lock_info["modified"] = lock_info["modified"] or graph_lock.nodes[
                            node_id].modified

                # Then, update all prev of all config lockfiles
                for lockfile, nodes_ids in lock_info["lockfiles"].items():
                    graph_lock_conf = GraphLockFile.load(lockfile, revisions_enabled)
                    graph_lock = graph_lock_conf.graph_lock
                    for node_id in nodes_ids:
                        if graph_lock.nodes[node_id].prev is None:
                            graph_lock.nodes[node_id].prev = lock_info["prev"]
                    graph_lock_conf.save(lockfile)

        save(multi_lock_path, lock_multi.dumps())
