# Conan Cache

## Considerations
 * In the codebase I want to use objects like `recipe_layout`
   or `package_layout`, I don't want to carry always the `cache` object
   together with the `ConanFileReference` or `PackageReference`.

   + **Consequence**: the lock is not adquired at the momento of getting
     the `RecipeLayout` or `PackageLayout` but when it is going to be used.

## Alternatives

 1. Before using anything from a layout, you need to indicate the ownership
   you want

 1. All operations run inside the layout (read files, write,...)

 1. Return a lock-object together with the information and let the user decide
   what to do with it.


## SQlite3

According to docs, it is safe to use SQlite3 from different processes in a
concurrent way. It manages several readers at the same time and only one
writter at the same time ([info](https://sqlite.org/faq.html#q5),
[more info](https://www.sqlite.org/lockingv3.html)).

According to [Python docs](https://docs.python.org/3/library/sqlite3.html),
it is also safe:

> When a database is accessed by multiple connections, and one of the
> processes modifies the database, the SQLite database is locked until
> that transaction is committed. The timeout parameter specifies how
> long the connection should wait for the lock to go away until raising
> an exception. The default for the timeout parameter is 5.0 (five seconds).

For the sake of the operations we will be running the time spent by the
read-write operations is not worth considered (TBD) taking into account other
Conan operations.


## Cache folders

For each reference we need the following folders. Some folders are needed
before we know the final destination, if we want a deterministic cache layout
we need to move them **after** being used (is this a time issue?).

Some folders can't be deterministic as they depend on things that aren't,
like folders that encode the `prev`. Only when using a lockfile we will
know the `prev` in advance (or downloading from remotes).

### [tmp]/export

It is needed in order to compute the _recipe revision_.

### [rrev]/export

The place where `conanfile.py` and other exported files are located.

### [rrev]/export_source

Source files exported after the recipe.

### [rrev]/source

Resulting files after running `source()` function. Conan v2 should forbid
usage of `settings` or `options`. This folder is shared for all the
packages.

### [tmp]/build

Needed to build the package. It should be associated to the generated
`prev` (non deterministic builds), but the `prev` is not known yet.

### [tmp]/package

A place to put the generated files in order to compute the _package revision_

### [prev]/build

Final place for the _build_ folder. BIG ISSUE: if we move the files here
after the build, maybe you are no longer capable of debugging packages
you've built locally!

### [prev]/package

Final place for the package.

### [rrev]/dl

Place for downloaded `conan_export.tgz` and `conan_sources.tgz` files

### [prev]/dl

Place for downloaded `conan_package.tgz` files.



 * We need some temporal folder to compute the recipe-revision, then
   we can move everything to the final destination (`export` folder).

 *
