import os


def load_plugin(conan_folder, plugin_name):
    try:
        from pluginbase import PluginBase
        plugin_base = PluginBase(package="plugins/%s" % plugin_name)
        plugins_dir = os.path.join(conan_folder, "plugins", plugin_name)
        plugin_source = plugin_base.make_plugin_source(
                        searchpath=[plugins_dir])
        plugin_class = plugin_source.load_plugin(plugin_name).get_class()
        # it is necessary to keep a reference to the plugin, otherwise it is removed
        # and some imports fail
        plugin_class.plugin_source = plugin_source
        return plugin_class
    except:
        print("Error loading plugin '%s'" % plugin_name)
        raise
