""" The cyclic garbage collector (GC) in the "conan" command

Almost all the objects that a "conan" command creates live until it ends: the graph, its nodes,
their conanfiles, settings and requirements. So the GC freed almost nothing, but every full
collection traverses all the tracked objects, and Python runs one every time they grow by 25%:
while a graph is computed, it was traversed again and again, up to half of the time of the command.

The "conan" command (conans/conan.py) disables it, before importing Conan. The Python API doesn't,
the processes that use it keep the GC. With the GC disabled:

- The builds (generators, recipes, hooks) create garbage with reference cycles, so the installer
  enables it while it installs the packages, after freezing the existing objects (the graph), so
  it doesn't traverse them again, not even in the collection of the interpreter shutdown, which
  runs although the GC is disabled.
- A command can compute several graphs (test_package, the workspace commands, the custom commands
  that run other commands). Without the GC, a graph no longer used is not freed, its nodes and
  their conanfiles reference each other. So before computing a new graph, a collection frees the
  previous ones, if one of them is no longer used: the DepsGraph object is freed by reference
  counting, its nodes are not. A graph with an error is not, the traceback of its error references
  it, so in that case it collects anyway.
"""
import gc
import weakref
from contextlib import contextmanager

# Set by the "conan" command (conans/conan.py), that disables the GC
CLI_DISABLED_GC = False
# The graphs computed with the GC disabled, that were alive in the last collection
_graphs = []


def new_graph(graph):
    """ Called with each new graph, before computing it """
    if not CLI_DISABLED_GC:
        return
    if any(g() is None or g().error for g in _graphs):
        gc.unfreeze()  # The installer froze them
        gc.collect()
        _graphs[:] = [g for g in _graphs if g() is not None]
    _graphs.append(weakref.ref(graph))


@contextmanager
def enabled_for_builds():
    """ While installing the packages, with the existing objects (the graph) frozen """
    if not CLI_DISABLED_GC or gc.isenabled():
        yield
        return
    gc.freeze()
    gc.enable()
    try:
        yield
    finally:
        gc.disable()
