

def write_toolchain(conanfile, path, output):
    if hasattr(conanfile, "toolchain"):
        assert callable(conanfile.toolchain), "toolchain should be a callable method"
        # This is the toolchain
        tc = conanfile.toolchain()
        tc.dump(path)

        # TODO: Lets discuss what to do with the environment
