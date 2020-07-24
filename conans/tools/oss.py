from conans.client.tools import oss as tools_oss, default_output
from conans.util.log import logger

args_to_string = tools_oss.args_to_string
detected_architecture = tools_oss.detected_architecture
detected_os = tools_oss.detected_os
OSInfo = tools_oss.OSInfo
cross_building = tools_oss.cross_building
get_cross_building_settings = tools_oss.get_cross_building_settings
get_gnu_triplet = tools_oss.get_gnu_triplet


def cpu_count(conanfile, *args, **kwargs):
    return tools_oss.cpu_count(output=conanfile.output, *args, **kwargs)

# Ready to use objects.
try:
    os_info = OSInfo()
except Exception as exc:
    logger.error(exc)
    output = default_output(None, None)
    output.error("Error detecting os_info")
