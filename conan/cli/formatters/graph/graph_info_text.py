import fnmatch

from conan.api.output import ConanOutput


def format_graph_info(result):
    graph = result["graph"]
    field_filter = result["field_filter"]
    package_filter = result["package_filter"]
    """ More complete graph output, including information for every node in the graph
    Used for 'graph info' command
    """
    out = ConanOutput()
    out.title("Basic graph information")
    serial = graph.serialize()
    for n in serial["nodes"]:
        if package_filter is not None:
            display = False
            for p in package_filter:
                if fnmatch.fnmatch(n["ref"] or "", p):
                    display = True
                    break
            if not display:
                continue
        out.writeln(f"{n['ref']}:")  # FIXME: This can be empty for consumers and it is ugly ":"
        _serial_pretty_printer(n, field_filter, indent="  ")
    if graph.error:
        raise graph.error


def _serial_pretty_printer(data, field_filter, indent=""):
    out = ConanOutput()
    for k, v in data.items():
        if field_filter is not None and k not in field_filter:
            continue
        if isinstance(v, dict):
            out.writeln(f"{indent}{k}:")
            # TODO: increment color too
            _serial_pretty_printer(v, None, indent=indent+"  ")
        else:
            out.writeln(f"{indent}{k}: {v}")
