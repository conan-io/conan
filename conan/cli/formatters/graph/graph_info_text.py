import fnmatch
from collections import OrderedDict

from conan.api.output import ConanOutput


def filter_graph(graph, package_filter, field_filter=None):
    if package_filter is not None:
        graph["nodes"] = [n for n in graph["nodes"]
                          if any(fnmatch.fnmatch(n["ref"] or "", p) for p in package_filter)]
    if field_filter is not None:
        if "ref" not in field_filter:
            field_filter.append("ref")
        result = []
        for n in graph["nodes"]:
            new_node = OrderedDict((k, v) for k, v in n.items() if k in field_filter)
            result.append(new_node)
        graph["nodes"] = result
    return graph


def format_graph_info(result):
    """ More complete graph output, including information for every node in the graph
    Used for 'graph info' command
    """
    graph = result["graph"]
    field_filter = result["field_filter"]
    package_filter = result["package_filter"]

    out = ConanOutput()
    out.title("Basic graph information")
    serial = graph.serialize()
    serial = filter_graph(serial, package_filter, field_filter)
    for n in serial["nodes"]:
        out.writeln(f"{n['ref']}:")  # FIXME: This can be empty for consumers and it is ugly ":"
        _serial_pretty_printer(n, indent="  ")
    if graph.error:
        raise graph.error


def _serial_pretty_printer(data, indent=""):
    out = ConanOutput()
    for k, v in data.items():
        if isinstance(v, dict):
            out.writeln(f"{indent}{k}:")
            # TODO: increment color too
            _serial_pretty_printer(v, indent=indent+"  ")
        else:
            out.writeln(f"{indent}{k}: {v}")
