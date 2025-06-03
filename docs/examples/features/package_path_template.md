# Custom Package Path Template

The Conan package cache contains binary packages in a structure that looks like this by default:

```
~/.conan2/p/b/<folder>/<files>
```

Where `<folder>` is a combination of the package name and a hash.

Starting in Conan 2.x, you can define a custom template for package paths using the `core.cache:package_path_template` configuration option. This allows you to create more organized folder structures, for example to include package names in the folder structure.

## Configuration

Set the `core.cache:package_path_template` in your global.conf file as follows:

```
core.cache:package_path_template = {pkgname}/{version}
```

You can use the following variables in your template:
- `{pkgname}`: The name of the package (without version)
- `{version}`: The version of the package

## Examples

### Add package name subfolder

To create a structure where each package's files are in a subfolder with the package name:

```
core.cache:package_path_template = {pkgname}
```

This will create a structure like:
```
~/.conan2/p/b/libev554a87e87d87d87/libev/<files>
```

### Add package name and version

To create a structure with both package name and version:

```
core.cache:package_path_template = {pkgname}-{version}
```

This will create a structure like:
```
~/.conan2/p/b/libev554a87e87d87d87/libev-1.0/<files>
```

## Important Notes

1. Changing this configuration will only affect newly built or downloaded packages
2. You should run `conan cache clean --output` after changing this configuration to avoid having packages with mixed structures
3. This configuration option is global and cannot be set per-package
4. Remote packages are still stored in the standard format on the server - the template is applied only in the local cache
