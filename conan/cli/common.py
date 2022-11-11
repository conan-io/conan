def get_profiles_from_args(conan_api, args):
    build = [
        conan_api.profiles.get_default_build()] if not args.profile_build else args.profile_build
    host = [conan_api.profiles.get_default_host()] if not args.profile_host else args.profile_host

    profile_build = conan_api.profiles.get_profile(profiles=build, settings=args.settings_build,
                                                   options=args.options_build, conf=args.conf_build)
    profile_host = conan_api.profiles.get_profile(profiles=host, settings=args.settings_host,
                                                  options=args.options_host, conf=args.conf_host)
    return profile_host, profile_build


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
