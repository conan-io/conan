def scope_options(profile, requires, tool_requires):
    """
    Command line helper to scope options when ``command -o myoption=myvalue`` is used,
    that needs to be converted to "-o pkg:myoption=myvalue". The "pkg" value will be
    computed from the given requires/tool_requires
    """
    # FIXME: This helper function here is not great, find a better place
    if requires and len(requires) == 1 and not tool_requires:
        profile.options.scope(requires[0])
    if tool_requires and len(tool_requires) == 1 and not requires:
        profile.options.scope(tool_requires[0])
