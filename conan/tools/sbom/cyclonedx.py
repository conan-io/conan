from conan import conan_version
from conan.errors import ConanException
from conan.internal.model.recipe_ref import ref_matches


def cyclonedx_1_4(conanfile, name=None, add_build=False, add_tests=False, cpes=None, **kwargs):
    """
    (Experimental) Generate cyclone 1.4 SBOM with JSON format

    Creates a CycloneDX 1.4 Software Bill of Materials (SBOM) from a given dependency graph.



    Parameters:
        conanfile: The conanfile instance.
        name (str, optional): Custom name for the metadata field.
        add_build (bool, optional, default=False): Include build dependencies.
        add_tests (bool, optional, default=False): Include test dependencies.
        cpes (dict, optional): Mapping of reference patterns (as understood by
            ``RecipeReference.matches()``, e.g. ``"openssl/*"``) to CPE 2.3/2.2 strings, used to
            override or provide the ``cpe`` field of matching components. A value of ``None``
            for a matching pattern suppresses any ``cpe`` declared in the recipe.

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
                "dependsOn": [_calculate_bomref(d.dst) for d in graph.root.edges
                              if should_add_node(d.dst, add_build, add_tests)]}
        dependencies.append(deps)
    for c in nodes:
        deps = {"ref": _calculate_bomref(c)}
        dep = [d for d in c.edges if should_add_node(d.dst, add_build, add_tests)]

        depends_on = [_calculate_bomref(d.dst) for d in dep
                      if should_add_node(d.dst, add_build, add_tests)]
        if depends_on:
            deps["dependsOn"] = depends_on
        dependencies.append(deps)

    sbom_cyclonedx_1_4 = {
        **({"components": [{
            "author": node.conanfile.author or "Unknown",
            "bom-ref": _calculate_bomref(node),
            **_cpe_field(node.ref, node.conanfile, cpes),
            **({"description": node.conanfile.description} if node.conanfile.description else {}),
            **({"externalReferences": [{
                "type": "website",
                "url": node.conanfile.homepage
            }]} if node.conanfile.homepage else {}),
            **({"licenses": _calculate_licenses(node)} if node.conanfile.license else {}),
            "name": node.name,
            **({"publisher": node.conanfile.publisher} if getattr(node.conanfile, "publisher",
                                                                  None) else {}),
            "purl": f"pkg:conan/{node.name}@{node.ref.version}",
            **({"supplier": {"name": node.conanfile.supplier}}
               if getattr(node.conanfile, "supplier", None) else {}),
            "type": "application" if node.conanfile.package_type == "application" else "library",
            "version": str(node.ref.version),
        } for node in nodes]} if nodes else {}),
        **({"dependencies": dependencies} if dependencies else {}),
        "metadata": {
            "component": {
                "author": conanfile.author or "Unknown",
                "bom-ref": special_id if has_special_root_node else _calculate_bomref(conanfile),
                **(_cpe_field(conanfile.ref, conanfile, cpes) if not has_special_root_node else {}),
                "name": name if name else name_default,
                **({"publisher": conanfile.publisher} if getattr(conanfile, "publisher", None)
                   else {}),
                **({"supplier": {"name": conanfile.supplier}}
                   if getattr(conanfile, "supplier", None) else {}),
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


def cyclonedx_1_6(conanfile, name=None, add_build=False, add_tests=False, cpes=None, **kwargs):
    """
    (Experimental) Generate cyclone 1.6 SBOM with JSON format

    Creates a CycloneDX 1.6 Software Bill of Materials (SBOM) from a given dependency graph.



    Parameters:
        conanfile: The conanfile instance.
        name (str, optional): Custom name for the metadata field.
        add_build (bool, optional, default=False): Include build dependencies.
        add_tests (bool, optional, default=False): Include test dependencies.
        cpes (dict, optional): Mapping of reference patterns (as understood by
            ``RecipeReference.matches()``, e.g. ``"openssl/*"``) to CPE 2.3/2.2 strings, used to
            override or provide the ``cpe`` field of matching components. A value of ``None``
            for a matching pattern suppresses any ``cpe`` declared in the recipe.

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
                "dependsOn": [_calculate_bomref(d.dst)
                              for d in graph.root.edges
                              if should_add_node(d.dst, add_build, add_tests)]}
        dependencies.append(deps)
    for c in nodes:
        deps = {"ref": _calculate_bomref(c)}
        dep = [d for d in c.edges if should_add_node(d.dst, add_build, add_tests)]

        depends_on = [_calculate_bomref(d.dst) for d in dep
                      if should_add_node(d.dst, add_build, add_tests)]
        if depends_on:
            deps["dependsOn"] = depends_on
        dependencies.append(deps)

    sbom_cyclonedx_1_6 = {
        **({"components": [{
            **({"authors": [{"name": node.conanfile.author}]} if node.conanfile.author else {}),
            "bom-ref": _calculate_bomref(node),
            **_cpe_field(node.ref, node.conanfile, cpes),
            **({"description": node.conanfile.description} if node.conanfile.description else {}),
            **({"externalReferences": [{
                "type": "website",
                "url": node.conanfile.homepage
            }]} if node.conanfile.homepage else {}),
            **({"licenses": _calculate_licenses(node)} if node.conanfile.license else {}),
            "name": node.name,
            **({"publisher": node.conanfile.publisher} if getattr(node.conanfile, "publisher",
                                                                  None) else {}),
            "purl": f"pkg:conan/{node.name}@{node.ref.version}",
            **({"supplier": {"name": node.conanfile.supplier}}
               if getattr(node.conanfile, "supplier", None) else {}),
            "type": "application" if node.conanfile.package_type == "application" else "library",
            "version": str(node.ref.version),
        } for node in nodes]} if nodes else {}),
        **({"dependencies": dependencies} if dependencies else {}),
        "metadata": {
            "component": {
                **({"authors": [{"name": conanfile.author}]} if conanfile.author else {}),
                "bom-ref": special_id if has_special_root_node else _calculate_bomref(conanfile),
                **(_cpe_field(conanfile.ref, conanfile, cpes) if not has_special_root_node else {}),
                "name": name if name else name_default,
                **({"publisher": conanfile.publisher} if getattr(conanfile, "publisher", None)
                   else {}),
                **({"supplier": {"name": conanfile.supplier}}
                   if getattr(conanfile, "supplier", None) else {}),
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


def _is_expr(license_value):
     v = license_value.upper()
     return " AND " in v or " OR " in v or " WITH " in v


def _calculate_licenses(component):
    from conan.tools.sbom.spdx_licenses import NORMALIZED_VALID_SPDX_LICENSES

    licenses = component.conanfile.license
    if isinstance(licenses, str):
        licenses = [licenses]

    result = []
    for lic in licenses:
        if lic.lower() in NORMALIZED_VALID_SPDX_LICENSES:
            field = "id"
        elif _is_expr(lic):
            field = "expression"
        else:
            field = "name"
        result.append({"license": {field: lic}})
    return result


def _cpe_field(ref, conanfile, cpes):
    cpe = _calculate_cpe(ref, conanfile, cpes)
    return {"cpe": cpe} if cpe else {}


def _calculate_cpe(ref, conanfile, cpes):
    matched = False
    cpe = None
    if cpes:
        for pattern, value in cpes.items():
            if ref_matches(ref, pattern, is_consumer=False):
                matched = True
                cpe = value
                break
    if not matched:
        cpe = getattr(conanfile, "cpe", None)
    if not cpe:
        return None
    return _normalize_cpe(cpe, ref.version, ref)


def _normalize_cpe(cpe, version, ref):
    if not isinstance(cpe, str):
        raise ConanException(f"Invalid 'cpe' for '{ref}': expected a string, "
                              f"got '{type(cpe).__name__}'")
    if cpe.startswith("cpe:2.3:"):
        parts = cpe.split(":")
        if len(parts) != 13:
            raise ConanException(f"Invalid CPE 2.3 string for '{ref}': '{cpe}' must have "
                                  "13 colon-separated components "
                                  "('cpe:2.3:part:vendor:product:version:update:edition:"
                                  "language:sw_edition:target_sw:target_hw:other')")
        if parts[5] == "*":
            parts[5] = _cpe_escape(str(version))
        return ":".join(parts)
    if cpe.startswith("cpe:/"):
        return cpe
    raise ConanException(f"Invalid 'cpe' for '{ref}': '{cpe}' must start with "
                          "'cpe:2.3:' or 'cpe:/'")


def _cpe_escape(value):
    return "".join(c if (c.isalnum() or c in "._-") else f"\\{c}" for c in value)


def _calculate_bomref(component):
    user = f"&user={component.ref.user}" if component.ref.user else ""
    channel = f"&channel={component.ref.channel}" if component.ref.channel else ""
    return f"pkg:conan/{component.name}@{component.ref.version}?rrev={component.ref.revision}{user}{channel}"


def should_add_node(node, add_build, add_tests):
    return (node.context == "host" or add_build) and (not node.test or add_tests)
