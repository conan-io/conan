import textwrap
from jinja2 import Template, StrictUndefined


class SetupTemplate:
    def __init__(self, zigdeps, conanfile):
        self._zigdeps = zigdeps
        self._conanfile = conanfile  # The dependency conanfile, not the consumer one

    def content(self):
        t = Template(self._template, trim_blocks=True, lstrip_blocks=True,
                     undefined=StrictUndefined)
        return t.render(self._context)

    @property
    def filename(self):
        return "conan_setup.zig"

    @property
    def _context(self):
        result = {}
        # for dep in self._conanfile.dependencies.host:
        #     result[dep.ref.name] = {
        #
        #     }
        return result

    @property
    def _template(self):
        return textwrap.dedent("""\
            const std = @import("std");
            const deps = @import("conan_deps.zig");

            pub fn linkDependency(step: *std.Build.Step.Compile, dep_name: []const u8) void {
                //std.debug.print("Checking dependency: {s}\\n", .{dep_name});
                if (deps.conan_deps.get(dep_name)) |dep_info| {
                    for (dep_info.include_paths) |include_path| {
                        // std.debug.print("Adding include path: {s}\\n", .{include_path});
                        step.addIncludePath(std.Build.LazyPath{ .cwd_relative = include_path });
                    }
                    for (dep_info.libs) |lib| {
                        // std.debug.print("Linking library: {s}\\n", .{lib});
                        //step.linkSystemLibrary(lib);
                        step.addObjectFile(std.Build.LazyPath{ .cwd_relative = lib});
                    }
                    for (dep_info.system_libs) |lib| {
                        // std.debug.print("Linking system library: {s}\\n", .{lib});
                        step.linkSystemLibrary(lib);
                    }
                    for (dep_info.defines) |define| {
                        //std.debug.print("Adding define: {s}={s}\\n", .{define.name, define.value});
                        step.root_module.addCMacro(define.name, define.value);

                    }
                    for (dep_info.frameworks) |framework| {
                        //std.debug.print("Linking framework: {s}\\n", .{framework});
                        step.linkFramework(framework);
                    }
                }
            }

            pub fn linkDependencies(step: *std.Build.Step.Compile) void {
                for (deps.conan_deps.keys()) |dep_name| {
                    linkDependency(step, dep_name);
                }
            }
            """)

