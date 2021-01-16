import json


class LockMulti(object):

    def __init__(self):
        self.nodes = {}

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
