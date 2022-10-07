import os


def load_plugin(server_folder, plugin_type, plugin_name):
    try:
        from pluginbase import PluginBase
        plugin_base = PluginBase(package="plugins/%s" % plugin_type)
        plugins_dir = os.path.join(server_folder, "plugins", plugin_type)
        plugin_source = plugin_base.make_plugin_source(
                        searchpath=[plugins_dir])
        plugin = plugin_source.load_plugin(plugin_name).get_class()
        # it is necessary to keep a reference to the plugin, otherwise it is removed
        # and some imports fail
        plugin.plugin_source = plugin_source
        return plugin
    except Exception:
        print("Error loading %s plugin '%s'" % (plugin_type, plugin_name))
        raise


def load_authentication_plugin(server_folder, plugin_name):
    return load_plugin(server_folder, "authenticator", plugin_name)


def load_authorization_plugin(server_folder, plugin_name):
    return load_plugin(server_folder, "authorizer", plugin_name)
