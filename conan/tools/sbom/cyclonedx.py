

def cyclonedx_1_4(conanfile, name=None, add_build=False, add_tests=False, **kwargs):
    """
    (Experimental) Generate cyclone 1.4 SBOM with JSON format

    Creates a CycloneDX 1.4 Software Bill of Materials (SBOM) from a given dependency graph.



    Parameters:
        conanfile: The conanfile instance.
        name (str, optional): Custom name for the metadata field.
        add_build (bool, optional, default=False): Include build dependencies.
        add_tests (bool, optional, default=False): Include test dependencies.

    Returns:
        The generated CycloneDX 1.4 document as a string.

    Example usage:
    ```
    cyclonedx(conanfile, name="custom_name", add_build=True, add_test=True, **kwargs)
    ```

    """
    import uuid
    import time
    from datetime import datetime, timezone
    graph = conanfile.subgraph

    has_special_root_node = not (getattr(graph.root.ref, "name", False) and getattr(graph.root.ref, "version", False) and getattr(graph.root.ref, "revision", False))
    special_id = str(uuid.uuid4())

    name_default = getattr(graph.root.ref, "name", False) or "conan-sbom"
    name_default += f"/{graph.root.ref.version}" if bool(getattr(graph.root.ref, "version", False)) else ""
    nodes = [node for node in graph.nodes if (node.context == "host" or add_build) and (not node.test or add_tests)]
    if has_special_root_node:
        nodes = nodes[1:]

    dependencies = []
    if has_special_root_node:
        deps = {"ref": special_id,
                "dependsOn": [f"pkg:conan/{d.dst.name}@{d.dst.ref.version}?rref={d.dst.ref.revision}"
                              for d in graph.root.dependencies]}
        dependencies.append(deps)
    for c in nodes:
        deps = {"ref": f"pkg:conan/{c.name}@{c.ref.version}?rref={c.ref.revision}"}
        dep = [d for d in c.dependencies if (d.dst.context == "host" or add_build) and (not d.dst.test or add_tests)]

        depends_on = [f"pkg:conan/{d.dst.name}@{d.dst.ref.version}?rref={d.dst.ref.revision}" for d in dep]
        if depends_on:
            deps["dependsOn"] = depends_on
        dependencies.append(deps)

    def _calculate_licenses(component):
        if isinstance(component.conanfile.license, str): # Just one license
            return [{"license": {
                        "id": component.conanfile.license
                    }}]
        return [{"license": {
                    "id": l
                }} for l in component.conanfile.license]

    sbom_cyclonedx_1_4 = {
        **({"components": [{
            "author": node.conanfile.author or "Unknown",
            "bom-ref": special_id if has_special_root_node else f"pkg:conan/{node.name}@{node.ref.version}?rref={node.ref.revision}",
            "description": node.conanfile.description,
            **({"externalReferences": [{
                "type": "website",
                "url": node.conanfile.homepage
            }]} if node.conanfile.homepage else {}),
            **({"licenses": _calculate_licenses(node)} if node.conanfile.license else {}),
            "name": node.name,
            "purl": f"pkg:conan/{node.name}@{node.ref.version}",
            "type": "library",
            "version": str(node.ref.version),
        } for node in nodes]} if nodes else {}),
        **({"dependencies": dependencies} if dependencies else {}),
        "metadata": {
            "component": {
                "author": conanfile.author or "Unknown",
                "bom-ref": special_id if has_special_root_node else f"pkg:conan/{conanfile.name}@{conanfile.ref.version}?rref={conanfile.ref.revision}",
                "name": name if name else name_default,
                "type": "library"
            },
            "timestamp": f"{datetime.fromtimestamp(time.time(), tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
            "tools": [{
                "externalReferences": [{
                    "type": "website",
                    "url": "https://github.com/conan-io/conan"
                }],
                "name": "Conan-io"
            }],
        },
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "bomFormat": "CycloneDX",
        "specVersion": "1.4",
        "version": 1,
    }
    return sbom_cyclonedx_1_4
