from conans.client.graph.graph_error import GraphError
from conans.model.recipe_ref import RecipeReference


def check_graph_provides(dep_graph):
    if dep_graph.error:
        return
    for node in dep_graph.nodes:
        provides = {}
        current_provides = node.conanfile.provides
        for dep in node.transitive_deps.values():
            dep_node = dep.node
            dep_require = dep.require

            dep_provides = dep_node.conanfile.provides
            if dep_provides is None:
                continue
            if isinstance(dep_provides, str):
                dep_provides = dep_provides,  # convert to tuple to iterate
            for provide in dep_provides:
                # First check if collides with current node
                if current_provides is not None and provide in current_provides:
                    raise GraphError.provides(node, dep_node)

                # Then, check if collides with other requirements
                new_req = dep_require.copy_requirement()
                new_req.ref = RecipeReference(provide, new_req.ref.version, new_req.ref.user,
                                              new_req.ref.channel)
                existing = node.transitive_deps.get(new_req)
                if existing is not None:
                    raise GraphError.provides(existing.node, dep_node)
                else:
                    existing_provide = provides.get(new_req)
                    if existing_provide is not None:
                        raise GraphError.provides(existing_provide, dep_node)
                    else:
                        provides[new_req] = dep_node
