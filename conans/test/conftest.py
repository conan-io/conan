import pytest

# More about hooks: https://doc.pytest.org/en/2.7.3/plugins.html?highlight=re#pytest-hook-reference


tools_available = {
    '1cmake': '3.10',
    '1gcc': '7',
    '1autotools': '2.69',
    '1compiler': 'XX',  # Some test need a valid detected compiler in the settings
    '1pkg_config': '0.29.1'
}

tools_keys = tools_available.keys()


def tool_check(mark):
    tool_name = mark.name[5:]
    if tool_name not in tools_keys:
        pytest.skip("required {} not satisfied".format(tool_name))
    else:
        version = mark.kwargs.get('version', None)
        if version:
            if not isinstance(version, str) or version[0] not in ("=", "<", ">"):
                pytest.exit("The version for the specified mark 'tool_{}' "
                            "should start with '=', '<' or '>'".format(mark.name))
            # TODO: Implement version_range, regex,...
            pytest.skip("required version {} {} not satisfied".format(tool_name, version))


def pytest_runtest_setup(item):
    # Every mark is a required tool, some specify a version
    for mark in item.iter_markers():
        if mark.name.startswith("tool_"):
            return tool_check(mark)
