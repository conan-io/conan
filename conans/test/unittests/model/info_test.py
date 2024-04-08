from conans.model.info import ConanInfo, RequirementsInfo, PythonRequiresInfo
from conans.model.options import Options
from conans.model.settings import Settings


def test_false_values_affect_none():
    """ False value do become part of conaninfo.txt and package_id
    Only "None" Python values are discarded from conaninfo.txt
    """
    reqs = RequirementsInfo({})
    build_reqs = RequirementsInfo({})
    python_reqs = PythonRequiresInfo({}, default_package_id_mode=None)
    options = Options({"shared": [True, False], "other": [None, "1"]}, {"shared": False})
    settings = Settings({"mysetting": [1, 2, 3]})
    c = ConanInfo(settings, options, reqs, build_reqs, python_reqs)
    conaninfo = c.dumps()
    assert "shared=False" in conaninfo
    assert "other" not in conaninfo
    assert "mysetting" not in conaninfo

    settings.mysetting = 1
    conaninfo = c.dumps()
    assert "mysetting=1" in conaninfo
