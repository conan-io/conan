import os

from jinja2 import Environment, StrictUndefined

from conan.errors import ConanException
from conan.internal import check_duplicated_generator
from conan.internal.model.dependencies import get_transitive_requires
from conan.internal.model.pkg_type import PackageType
from conan.tools.files import save

# cpp_info fields Zig's build system has no injection point for: a dependency cannot push
# compiler or linker flags onto sources the consumer owns (Module.addCSourceFile applies
# flags only to files added through it, and there is no raw-linker-arg API on Module).
# They are still emitted as data so a consumer can apply them deliberately.
_UNAPPLIABLE_FLAGS = ("cflags", "cxxflags", "sharedlinkflags", "exelinkflags")


def _zigstr(value):
    """ Escape a value so it can be embedded in a Zig double-quoted string literal """
    result = []
    for ch in str(value):
        if ch == "\\":
            result.append("\\\\")
        elif ch == '"':
            result.append('\\"')
        elif ch == "\n":
            result.append("\\n")
        elif ch == "\r":
            result.append("\\r")
        elif ch == "\t":
            result.append("\\t")
        elif ord(ch) < 0x20:
            result.append("\\x%02x" % ord(ch))
        else:
            result.append(ch)
    return "".join(result)


class ZigDeps:
    """
    Generates ``conan_deps.zig``, a comptime map of dependency information (include dirs,
    library locations, defines, system libs, frameworks), and ``conan_setup.zig``, a set of
    helper functions to consume it from a user ``build.zig``.

    Every requirable "thing" (a package root, or one of its components) becomes a target keyed
    as ``"pkgname::targetname"``, mirroring ``CMakeConfigDeps``: a target only carries its own
    (unmerged) information, and depends on other targets through an explicit ``requires`` list,
    since Zig's build system does not propagate this information transitively on its own.

    Executables from ``tool_requires`` (and application dependencies) are exposed separately as
    a path map, since there is nothing to link for those.

    This covers build time only. Making a shared dependency loadable at run time is left to
    Conan's own ``conanrun`` environment (or a deployer) rather than handled here - see the
    note in the generated ``conan_setup.zig``.
    """

    def __init__(self, conanfile):
        self._conanfile = conanfile

    def generate(self):
        """
        This method will save the generated files to the ``conanfile.generators_folder`` folder
        """
        self._conanfile.output.warning("ZigDeps is experimental, and might get "
                                       "breaking changes in future releases",
                                       warn_tag="experimental")
        check_duplicated_generator(self, self._conanfile)
        generator_files = self._content()
        for generator_file, content in generator_files.items():
            save(self._conanfile, os.path.join("conan_zig_deps", generator_file), content)

    def get_transitive_requires(self, dep):
        # Resolved from the consumer's perspective, as requirement traits (visible,
        # transitive_headers/libs, replace_requires) live on the require edge, not on ``dep``
        return get_transitive_requires(self._conanfile, dep)

    def _content(self):
        targets = {}
        exes = {}
        flag_deps = set()
        host_req = self._conanfile.dependencies.host
        test_req = self._conanfile.dependencies.test

        for require, dep in list(host_req.items()) + list(test_req.items()):
            full_cpp_info = dep.cpp_info.deduce_full_cpp_info(dep)
            self._add_package_targets(require, dep, full_cpp_info, targets, flag_deps)
            self._add_package_exes(dep, full_cpp_info, exes)
        # tool_requires: nothing to link, but a build.zig needs to be able to find the
        # executables. Most tool recipes do not declare cpp_info.exe, so their bindirs are
        # what is actually available - Conan itself relies on those, via PATH.
        tool_dirs = {}
        for _, dep in self._conanfile.dependencies.build.items():
            full_cpp_info = dep.cpp_info.deduce_full_cpp_info(dep)
            self._add_package_exes(dep, full_cpp_info, exes)
            bindirs = [d.replace("\\", "/")
                       for d in full_cpp_info.aggregated_components().bindirs]
            if bindirs:
                tool_dirs[dep.ref.name] = bindirs

        # A "requires" entry can point at something that was deliberately never turned into a
        # target (e.g. an executable-only component - there's nothing to link there). Prune
        # those instead of leaving a dangling reference that would silently resolve to nothing.
        for target in targets.values():
            target["requires"] = [r for r in target["requires"] if r in targets]

        direct_targets = [f"{dep.ref.name}::{dep.ref.name}"
                          for _, dep in self._conanfile.dependencies.direct_host.items()
                          if dep.package_type is not PackageType.APP]
        direct_targets = [t for t in direct_targets if t in targets]

        if flag_deps:
            self._conanfile.output.warning(
                "ZigDeps: Zig's build system has no way to apply a dependency's compiler or "
                "linker flags to sources it does not own, so these are exposed in "
                "conan_deps.zig for you to pass explicitly: " + ", ".join(sorted(flag_deps)),
                warn_tag="experimental")

        env = Environment(trim_blocks=True, lstrip_blocks=True, undefined=StrictUndefined)
        env.filters["zigstr"] = _zigstr
        deps_template = env.from_string(_CONAN_DEPS_TEMPLATE)
        context = {"targets": dict(sorted(targets.items())),
                   "exes": dict(sorted(exes.items())),
                   "tool_dirs": dict(sorted(tool_dirs.items())),
                   "direct_targets": direct_targets}
        return {"conan_deps.zig": deps_template.render(context),
                "conan_setup.zig": _CONAN_SETUP_ZIG}

    @staticmethod
    def _add_package_exes(dep, full_cpp_info, exes):
        pkg_name = dep.ref.name
        components = full_cpp_info.components if full_cpp_info.has_components \
            else {pkg_name: full_cpp_info}
        for comp_name, info in components.items():
            if info.exe or info.type is PackageType.APP:
                if info.location:
                    exes[f"{pkg_name}::{comp_name}"] = info.location.replace("\\", "/")

    def _add_package_targets(self, require, dep, full_cpp_info, targets, flag_deps):
        pkg_name = dep.ref.name
        has_components = full_cpp_info.has_components
        components = full_cpp_info.components if has_components else {pkg_name: full_cpp_info}

        all_target_names = []
        for comp_name, info in components.items():
            if info.exe or not (info.frameworks or info.package_framework or info.includedirs
                                or info.libs or info.objects or info.system_libs or info.defines
                                or info.requires):
                continue  # Nothing this target actually contributes
            if any(getattr(info, f, None) for f in _UNAPPLIABLE_FLAGS):
                flag_deps.add(f"{pkg_name}::{comp_name}")
            target_key = f"{pkg_name}::{comp_name}"
            targets[target_key] = self._target_data(require, dep, info, has_components)
            all_target_names.append(target_key)

        root_key = f"{pkg_name}::{pkg_name}"
        if root_key not in targets and all_target_names:
            if full_cpp_info.default_components is not None:
                # A default component may itself have been skipped (exe-only or empty)
                requires = [f"{pkg_name}::{c}" for c in full_cpp_info.default_components]
                requires = [r for r in requires if r in targets]
            else:
                # Every contributing component, not only the ones producing a library:
                # a header-only component still carries includedirs, defines and its own
                # requires, and would otherwise be unreachable from the package root.
                # This is what CMakeConfigDeps' _add_root_lib_target does too.
                requires = all_target_names
            targets[root_key] = self._interface_target(requires)

    @staticmethod
    def _empty_target():
        return {"type": "interface", "include_paths": [], "defines": [], "system_libs": [],
                "frameworks": [], "framework_paths": [], "objects": [], "cflags": [],
                "cxxflags": [], "link_flags": [], "lib": None, "link_libc": False,
                "link_cpp": False, "requires": []}

    @classmethod
    def _interface_target(cls, requires):
        result = cls._empty_target()
        result["requires"] = requires
        return result

    @staticmethod
    def _is_cpp(dep, info):
        """ Whether a dependency needs the C++ runtime linked into its consumer.

        ``languages`` is authoritative when the recipe declares it, so a package saying
        ``languages = "C"`` never gets the C++ runtime. It is a newer attribute that most
        packages still leave unset, and C++ is the assumption for those, because the two
        mistakes are not equally bad: linking the C++ runtime into something that turns out to
        be pure C only adds a library that is never used, while leaving it out of a C++
        dependency fails the consumer's link with undefined ``std::`` symbols.

        CMakeConfigDeps emits nothing at all when ``languages`` is unset and lets CMake infer
        linkage from the consumer's own ``project()`` languages, which Zig has no equivalent
        of. A C package that has not adopted ``languages`` yet can still opt out per
        dependency in the consumer's ``build.zig``.
        """
        languages = info.languages or dep.languages or []
        return "C++" in languages if languages else True

    def _target_data(self, require, dep, info, has_components):
        result = self._empty_target()
        result["requires"] = self._requires(dep, info, has_components)
        # Every Conan C/C++ package is built against libc, and Zig does not infer that from
        # an object file - without it the dependency's own headers fail on things like
        # malloc. (Zig only auto-detects libc from system_libs named "m", "pthread", ...)
        result["link_libc"] = True
        # Not gated on there being a library: the C++ runtime is needed to compile against a
        # header-only C++ dependency too
        result["link_cpp"] = self._is_cpp(dep, info)
        result["system_libs"] = list(info.system_libs)
        result["frameworks"] = list(info.frameworks)
        result["framework_paths"] = [p.replace("\\", "/") for p in info.frameworkdirs]
        result["cflags"] = list(info.cflags)
        result["cxxflags"] = list(info.cxxflags)
        result["link_flags"] = list(info.sharedlinkflags) + list(info.exelinkflags)
        # ``headers`` says whether this consumer may use the dependency's headers at all;
        # when it is False, its include dirs and defines must not leak in
        if require.headers:
            result["include_paths"] = [p.replace("\\", "/") for p in info.includedirs]
            result["defines"] = self._defines(info.defines)
        if info.package_framework:
            # An Apple .framework bundle: link it by name, with its parent as search path
            path = info.package_framework.replace("\\", "/")
            result["framework_paths"].append(os.path.dirname(path))
            name = os.path.basename(path)
            result["frameworks"].append(name[:-len(".framework")]
                                        if name.endswith(".framework") else name)
        if require.libs:
            result["objects"] = [o.replace("\\", "/") for o in info.objects]
            if info.libs:
                assert info.location, f"{dep}: cpp_info.location missing for {info.libs}"
                is_shared = info.type is PackageType.SHARED
                # ``link_location`` is only set when it differs from ``location`` - on
                # Windows, where a shared library links against its import lib, not the .dll
                link_path = info.link_location or info.location
                result["type"] = "shared" if is_shared else "static"
                result["lib"] = link_path.replace("\\", "/")
        return result

    @staticmethod
    def _defines(defines):
        # A list of pairs rather than a dict: duplicate names are legal and must not be
        # silently collapsed, and the emitted order is the order the recipe declared
        result = []
        for define in defines:
            if "=" in define:
                name, value = define.split("=", 1)
            else:
                name, value = define, "1"
            result.append((name, value))
        return result

    def _requires(self, dep, info, has_components):
        requires = info.parsed_requires()
        pkg_name = dep.ref.name
        transitive_reqs = self.get_transitive_requires(dep)

        if not requires and not has_components:
            # No explicit requires: link against all of this package's own direct dependencies
            return [f"{d.ref.name}::{d.ref.name}" for d in transitive_reqs.values()
                    if d.package_type is not PackageType.APP]

        result = []
        for req_pkg, req_comp in requires:
            if req_pkg is None:  # Points to a component of the same package
                result.append(f"{pkg_name}::{req_comp}")
                continue
            try:
                _, req_dep = transitive_reqs.of(req_pkg)
            except KeyError:
                continue  # The transitive dep might have been skipped
            if req_dep.package_type is PackageType.APP:
                continue  # It doesn't make sense to link a package that is an App
            # Key off the *resolved* dependency, not the name the recipe wrote: under
            # ``replace_requires`` those differ, and targets are always created from the
            # resolved name, so using req_pkg here would dangle (and then be pruned away)
            req_name = req_dep.ref.name
            if req_dep.cpp_info.components.get(req_comp) is not None:
                result.append(f"{req_name}::{req_comp}")
            elif req_pkg != req_comp:
                # Not a component of that package, and not the "pkg::pkg" root form either,
                # so the recipe is referring to something that does not exist
                raise ConanException(f"{dep} cpp_info requires '{req_pkg}::{req_comp}', but "
                                     f"component '{req_comp}' was not found in '{req_pkg}'")
            else:  # It must be the interface pkgname::pkgname target
                result.append(f"{req_name}::{req_name}")
        return result


_CONAN_DEPS_TEMPLATE = """\
// Generated by Conan, do not edit manually

const std = @import("std");

pub const Define = struct {
    name: []const u8,
    value: []const u8,
};

pub const TargetKind = enum { static, shared, interface };

pub const Target = struct {
    kind: TargetKind,
    include_paths: []const []const u8,
    defines: []const Define,
    system_libs: []const []const u8,
    frameworks: []const []const u8,
    framework_paths: []const []const u8,
    objects: []const []const u8,
    /// Path of the library to link, if this target produces one. For a shared library on
    /// Windows this is the import library, not the runtime .dll.
    lib: ?[]const u8,
    /// Whether the consumer needs libc / the C++ runtime linked in for this target.
    link_libc: bool,
    link_cpp: bool,
    /// Compiler and linker flags the dependency declares. Zig has no injection point for
    /// these - a dependency cannot add flags to sources it does not own - so they are NOT
    /// applied automatically. Pass them yourself, e.g. to Module.addCSourceFile(.flags).
    cflags: []const []const u8,
    cxxflags: []const []const u8,
    link_flags: []const []const u8,
    requires: []const []const u8,
};

pub const direct_targets: []const []const u8 = &.{
{% for name in direct_targets %}
    "{{ name | zigstr }}",
{% endfor %}
};

/// Executables provided by dependencies (tool_requires and application packages), by
/// "pkg::name". There is nothing to link for these - use the path with b.addSystemCommand.
pub const conan_exes = std.StaticStringMap([]const u8).initComptime(.{
{% for name, path in exes.items() %}
    .{ "{{ name | zigstr }}", "{{ path | zigstr }}" },
{% endfor %}
});

/// Directories holding the executables of build-context dependencies (tool_requires), by
/// package name. Conan exposes tools through PATH; this is the same information, so a
/// build.zig can locate one without depending on the ambient environment.
pub const conan_tool_dirs = std.StaticStringMap([]const []const u8).initComptime(.{
{% for name, dirs in tool_dirs.items() %}
    .{ "{{ name | zigstr }}", &.{ {% for d in dirs %}"{{ d | zigstr }}", {% endfor %} } },
{% endfor %}
});

pub const conan_targets = std.StaticStringMap(Target).initComptime(.{
{% for name, t in targets.items() %}
    .{ "{{ name | zigstr }}", Target{
        .kind = .{{ t.type }},
        .include_paths = &.{ {% for p in t.include_paths %}"{{ p | zigstr }}", {% endfor %} },
        .defines = &.{
{% for dname, dvalue in t.defines %}
            .{ .name = "{{ dname | zigstr }}", .value = "{{ dvalue | zigstr }}" },
{% endfor %}
        },
        .system_libs = &.{ {% for l in t.system_libs %}"{{ l | zigstr }}", {% endfor %} },
        .frameworks = &.{ {% for f in t.frameworks %}"{{ f | zigstr }}", {% endfor %} },
        .framework_paths = &.{ {% for f in t.framework_paths %}"{{ f | zigstr }}", {% endfor %} },
        .objects = &.{ {% for o in t.objects %}"{{ o | zigstr }}", {% endfor %} },
{% if t.lib %}
        .lib = "{{ t.lib | zigstr }}",
{% else %}
        .lib = null,
{% endif %}
        .link_libc = {{ "true" if t.link_libc else "false" }},
        .link_cpp = {{ "true" if t.link_cpp else "false" }},
        .cflags = &.{ {% for f in t.cflags %}"{{ f | zigstr }}", {% endfor %} },
        .cxxflags = &.{ {% for f in t.cxxflags %}"{{ f | zigstr }}", {% endfor %} },
        .link_flags = &.{ {% for f in t.link_flags %}"{{ f | zigstr }}", {% endfor %} },
        .requires = &.{ {% for r in t.requires %}"{{ r | zigstr }}", {% endfor %} },
    } },
{% endfor %}
});
"""

_CONAN_SETUP_ZIG = """\
// Generated by Conan, do not edit manually

const std = @import("std");
const conan_deps = @import("conan_deps.zig");

const Module = std.Build.Module;

/// Targets already applied to a given module, so linking the same dependency twice - whether
/// through a diamond in the requires graph or through two separate calls - applies it once.
var applied: ?std.AutoHashMap(*Module, *std.StringHashMap(void)) = null;

fn visitedFor(module: *Module) *std.StringHashMap(void) {
    const allocator = module.owner.allocator;
    if (applied == null) {
        applied = std.AutoHashMap(*Module, *std.StringHashMap(void)).init(allocator);
    }
    const entry = applied.?.getOrPut(module) catch @panic("OOM");
    if (!entry.found_existing) {
        const set = allocator.create(std.StringHashMap(void)) catch @panic("OOM");
        set.* = std.StringHashMap(void).init(allocator);
        entry.value_ptr.* = set;
    }
    return entry.value_ptr.*;
}

fn linkTarget(module: *Module, target: conan_deps.Target) void {
    for (target.include_paths) |path| {
        // -isystem, not -I: warnings from a dependency's headers are not the consumer's
        module.addSystemIncludePath(.{ .cwd_relative = path });
    }
    for (target.defines) |define| {
        module.addCMacro(define.name, define.value);
    }
    for (target.system_libs) |lib| {
        // Conan already resolved exactly what to link, so don't let Zig second-guess it
        // through pkg-config (which it would do by default, use_pkg_config = .yes).
        module.linkSystemLibrary(lib, .{ .use_pkg_config = .no });
    }
    for (target.framework_paths) |path| {
        module.addFrameworkPath(.{ .cwd_relative = path });
    }
    for (target.frameworks) |framework| {
        module.linkFramework(framework, .{});
    }
    for (target.objects) |object| {
        module.addObjectFile(.{ .cwd_relative = object });
    }
    if (target.lib) |lib| {
        module.addObjectFile(.{ .cwd_relative = lib });
    }
    // Both of these are ?bool, where null means "not decided yet". Only fill them in when
    // the consumer has not said anything, so `mod.link_libcpp = false` opts out regardless
    // of whether it is written before or after linking dependencies.
    if (target.link_libc and module.link_libc == null) {
        module.link_libc = true;
    }
    if (target.link_cpp and module.link_libcpp == null and !isMsvcAbi(module)) {
        // Not on the MSVC ABI: there the C++ runtime comes from MSVC itself, pulled in by
        // the /DEFAULTLIB directives its own objects carry. Zig's bundled libc++ cannot be
        // built against the MSVC headers (it conflicts on std::type_info) and would be the
        // wrong ABI to mix in anyway.
        module.link_libcpp = true;
    }
}

fn isMsvcAbi(module: *Module) bool {
    const resolved = module.resolved_target orelse return false;
    return resolved.result.abi == .msvc;
}

fn linkDependencyVisited(
    module: *Module,
    target_name: []const u8,
    visited: *std.StringHashMap(void),
) void {
    // A "requires" cycle isn't something Conan validates (unlike the package graph itself),
    // so guard against it here rather than risk an unbounded recursion / stack overflow.
    if (visited.contains(target_name)) return;
    visited.put(target_name, {}) catch @panic("OOM");
    const target = conan_deps.conan_targets.get(target_name) orelse return;
    linkTarget(module, target);
    for (target.requires) |req_name| {
        linkDependencyVisited(module, req_name, visited);
    }
}

/// Links a single Conan target (a package root, e.g. "zlib::zlib", or one of its
/// components, e.g. "openssl::ssl") and, transitively, everything it requires.
pub fn linkDependency(module: *Module, target_name: []const u8) void {
    if (conan_deps.conan_targets.get(target_name) == null) {
        // Fail loudly: a typo here would otherwise surface much later as an unrelated
        // undefined-symbol error, with nothing pointing back at this call.
        std.debug.print("conan: unknown target '{s}'. Available targets:\\n", .{target_name});
        for (conan_deps.conan_targets.keys()) |available| {
            std.debug.print("  {s}\\n", .{available});
        }
        @panic("conan: unknown target");
    }
    linkDependencyVisited(module, target_name, visitedFor(module));
}

/// Links every direct dependency declared by the consumer (and, transitively, everything
/// they require).
pub fn linkDependencies(module: *Module) void {
    const visited = visitedFor(module);
    for (conan_deps.direct_targets) |name| {
        linkDependencyVisited(module, name, visited);
    }
}

/// Absolute path of an executable a dependency declares through cpp_info.exe, keyed
/// "pkg::name". Note most tool recipes do not declare it - prefer toolPath() for those.
pub fn exePath(name: []const u8) []const u8 {
    return conan_deps.conan_exes.get(name) orelse {
        std.debug.print("conan: unknown executable '{s}'\\n", .{name});
        @panic("conan: unknown executable");
    };
}

/// Absolute path of a tool_requires executable, e.g.
/// b.addSystemCommand(&.{ conan.toolPath(b, "flex", "flex") }). Resolved inside the
/// package's own bindir rather than through PATH, so the build does not silently pick up a
/// different copy of the tool from the ambient environment. If a package ships more than
/// one bindir, read conan_deps.conan_tool_dirs directly.
pub fn toolPath(b: *std.Build, pkg: []const u8, exe_name: []const u8) []const u8 {
    const dirs = conan_deps.conan_tool_dirs.get(pkg) orelse {
        std.debug.print("conan: '{s}' is not a tool_requires here. Available:\\n", .{pkg});
        for (conan_deps.conan_tool_dirs.keys()) |available| {
            std.debug.print("  {s}\\n", .{available});
        }
        @panic("conan: unknown tool package");
    };
    return b.pathJoin(&.{ dirs[0], exe_name });
}

// NOTE ON RUNTIME DISCOVERY
// This only makes dependencies available at *build* time. Making a shared dependency
// loadable at *run* time is deliberately left to Conan rather than handled here:
// activate the "conanrun" environment Conan generates for exactly this purpose (it sets
// PATH on Windows and (DY)LD_LIBRARY_PATH elsewhere, from every dependency's directories),
// e.g. `self.run("zig build run", env="conanrun")` from a recipe, or by sourcing the
// generated conanrun script directly. `conan install ... --deploy=runtime_deploy` is the
// other option, placing the runtime artifacts in one folder at install time.
//
// Watch out: VirtualRunEnv decides whether to export the library-path variables at all by
// looking at settings.os, so a consumer recipe that declares no `settings` gets a silently
// empty conanrun environment and the libraries stay unfindable.
//
// This differs from a CMake-based consumer, where CMake adds an rpath to build-tree
// binaries by itself, so they run without conanrun (it strips that rpath again on install,
// so installed binaries need the environment either way). Zig has no equivalent behaviour.
// Reproducing it here - emitting rpaths, or copying .dlls next to the executable - was
// intentionally left out of this first version: it duplicates what conanrun already does,
// and neither mechanism has a single obviously-correct form across the platforms Conan
// supports. If real usage shows the environment is not enough, this is the place to
// revisit.
"""
