from conan import conan_version


def cyclonedx_1_4(conanfile, name=None, add_build=False, add_tests=False, namespace=None, qualifiers=None, **kwargs):
    """
    (Experimental) Generate cyclone 1.4 SBOM with JSON format

    Creates a CycloneDX 1.4 Software Bill of Materials (SBOM) from a given dependency graph.



    Parameters:
        conanfile: The conanfile instance.
        name (str, optional): Custom name for the metadata field.
        add_build (bool, optional, default=False): Include build dependencies.
        add_tests (bool, optional, default=False): Include test dependencies.
        namespace (str, optional): Custom namespace show in PURL.
        qualifiers (list[str], optional): Qualifiers show in PURL.

    Returns:
        The generated CycloneDX 1.4 document as a string.

    Example usage:
    ```
    cyclonedx_1_4(conanfile, name="custom_name", add_build=True, add_test=True, **kwargs)
    ```

    """
    import uuid
    import time
    from datetime import datetime, timezone
    graph = conanfile.subgraph
    qualifiers = qualifiers or []

    has_special_root_node = not (getattr(graph.root.ref, "name", False)
                                 and getattr(graph.root.ref, "version", False)
                                 and getattr(graph.root.ref, "revision", False))
    special_id = str(uuid.uuid4())

    name_default = getattr(graph.root.ref, "name", False) or "conan-sbom"
    name_default += f"/{graph.root.ref.version}" if getattr(graph.root.ref, "version", False) else ""

    nodes = [node for node in graph.nodes if should_add_node(node, add_build, add_tests)]
    if has_special_root_node:
        nodes = nodes[1:]

    dependencies = []
    if has_special_root_node:
        deps = {"ref": special_id,
                "dependsOn": [_calculate_bomref(d.dst, namespace, qualifiers) for d in graph.root.edges
                              if should_add_node(d.dst, add_build, add_tests)]}
        dependencies.append(deps)
    for c in nodes:
        deps = {"ref": _calculate_bomref(c, namespace, qualifiers)}
        dep = [d for d in c.edges if should_add_node(d.dst, add_build, add_tests)]

        depends_on = [_calculate_bomref(d.dst, namespace, qualifiers) for d in dep
                      if should_add_node(d.dst, add_build, add_tests)]
        if depends_on:
            deps["dependsOn"] = depends_on
        dependencies.append(deps)

    sbom_cyclonedx_1_4 = {
        **({"components": [{
            "author": node.conanfile.author or "Unknown",
            "bom-ref": _calculate_bomref(node, namespace, qualifiers),
            "description": node.conanfile.description,
            **({"externalReferences": [{
                "type": "website",
                "url": node.conanfile.homepage
            }]} if node.conanfile.homepage else {}),
            **({"licenses": _calculate_licenses(node)} if node.conanfile.license else {}),
            "name": node.name,
            "purl": _calculate_bomref(node, namespace, qualifiers),
            "type": "application" if node.conanfile.package_type == "application" else "library",
            "version": str(node.ref.version),
        } for node in nodes]} if nodes else {}),
        **({"dependencies": dependencies} if dependencies else {}),
        "metadata": {
            "component": {
                "author": conanfile.author or "Unknown",
                "bom-ref": special_id if has_special_root_node else _calculate_bomref(conanfile, namespace, qualifiers),
                "name": name if name else name_default,
                "type": "application" if conanfile.package_type == "application" else "library",
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


def cyclonedx_1_6(conanfile, name=None, add_build=False, add_tests=False, namespace=None, qualifiers=None, **kwargs):
    """
    (Experimental) Generate cyclone 1.6 SBOM with JSON format

    Creates a CycloneDX 1.6 Software Bill of Materials (SBOM) from a given dependency graph.



    Parameters:
        conanfile: The conanfile instance.
        name (str, optional): Custom name for the metadata field.
        add_build (bool, optional, default=False): Include build dependencies.
        add_tests (bool, optional, default=False): Include test dependencies.
        namespace (str, optional): Custom namespace show in PURL.
        qualifiers (list[str], optional): Qualifiers show in PURL.

    Returns:
        The generated CycloneDX 1.6 document as a string.

    Example usage:
    ```
    cyclonedx_1_6(conanfile, name="custom_name", add_build=True, add_test=True, **kwargs)
    ```

    """
    import uuid
    import time
    from datetime import datetime, timezone
    graph = conanfile.subgraph
    qualifiers = qualifiers or []

    has_special_root_node = not (getattr(graph.root.ref, "name", False)
                                 and getattr(graph.root.ref, "version", False)
                                 and getattr(graph.root.ref, "revision", False))
    special_id = str(uuid.uuid4())

    name_default = getattr(graph.root.ref, "name", False) or "conan-sbom"
    name_default += f"/{graph.root.ref.version}" if getattr(graph.root.ref, "version", False) else ""

    nodes = [node for node in graph.nodes if should_add_node(node, add_build, add_tests)]
    if has_special_root_node:
        nodes = nodes[1:]

    dependencies = []
    if has_special_root_node:
        deps = {"ref": special_id,
                "dependsOn": [_calculate_bomref(d.dst, namespace, qualifiers)
                              for d in graph.root.edges
                              if should_add_node(d.dst, add_build, add_tests)]}
        dependencies.append(deps)
    for c in nodes:
        deps = {"ref": _calculate_bomref(c, namespace, qualifiers)}
        dep = [d for d in c.edges if should_add_node(d.dst, add_build, add_tests)]

        depends_on = [_calculate_bomref(d.dst, namespace, qualifiers) for d in dep
                      if should_add_node(d.dst, add_build, add_tests)]
        if depends_on:
            deps["dependsOn"] = depends_on
        dependencies.append(deps)

    sbom_cyclonedx_1_6 = {
        **({"components": [{
            **({"authors": [{"name": node.conanfile.author}]} if node.conanfile.author else {}),
            "bom-ref": _calculate_bomref(node, namespace, qualifiers),
            "description": node.conanfile.description,
            **({"externalReferences": [{
                "type": "website",
                "url": node.conanfile.homepage
            }]} if node.conanfile.homepage else {}),
            **({"licenses": _calculate_licenses(node)} if node.conanfile.license else {}),
            "name": node.name,
            "purl": _calculate_bomref(node, namespace, qualifiers),
            "type": "application" if node.conanfile.package_type == "application" else "library",
            "version": str(node.ref.version),
        } for node in nodes]} if nodes else {}),
        **({"dependencies": dependencies} if dependencies else {}),
        "metadata": {
            "component": {
                **({"authors": [{"name": conanfile.author}]} if conanfile.author else {}),
                "bom-ref": special_id if has_special_root_node else _calculate_bomref(conanfile, namespace, qualifiers),
                "name": name if name else name_default,
                "type": "application" if conanfile.package_type == "application" else "library"
            },
            "timestamp": f"{datetime.fromtimestamp(time.time(), tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
            "tools": {
                "components": [{
                    "type": "application",
                    "name": "Conan-io",
                    "version": str(conan_version),
                }]
            },
        },
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "version": 1,
    }
    return sbom_cyclonedx_1_6


def _calculate_licenses(component):
    from conan.tools.sbom.spdx_licenses import NORMALIZED_VALID_SPDX_LICENSES
    licenses = component.conanfile.license

    if isinstance(licenses, str):  # Just one license
        field = "id" if licenses.lower() in NORMALIZED_VALID_SPDX_LICENSES else "name"
        return [{"license": {field: licenses}}]

    return [
        # More than one license
        {"license": {
            "id" if lic.lower() in NORMALIZED_VALID_SPDX_LICENSES else "name": lic
        }}
        for lic in licenses
    ]


def _calculate_bomref(component, namespace, qualifiers):
    namespace = f"{namespace}/" if namespace else ""
    user = f"&user={component.ref.user}" if component.ref.user else ""
    channel = f"&channel={component.ref.channel}" if component.ref.channel else ""
    purl_qualifier = ""
    if hasattr(component, "conanfile"):
        purl_qualifier = "".join(f"&{qualifier}={component.conanfile.settings.get_safe(qualifier)}" for qualifier in qualifiers)
    return (f"pkg:conan/{namespace}{component.name}@{component.ref.version}"
            f"?rref={component.ref.revision}&pref={component.pref.package_id}"
            f"{user}{channel}{purl_qualifier}")


def should_add_node(node, add_build, add_tests):
    return (node.context == "host" or add_build) and (not node.test or add_tests)
