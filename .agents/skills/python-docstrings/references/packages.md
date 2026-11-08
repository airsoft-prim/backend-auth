# Packages

Write a package docstring only in that package's `__init__.py`, as its first
statement before imports or other executable code. Do not put package-level
docstrings in other modules or spread the package description across files.

Use three prose blocks in this order, separated by blank lines:

1. **Summary:** a short first-line sentence identifying the package and its purpose.
2. **Extended description:** explain the functionality and responsibilities of
   the modules it brings together.
3. **Architectural role:** explain where the package fits in the application,
   including its relationships with other components when relevant.

These labels describe the content; do not add literal section headings for them.
All three blocks are required. Keep the architectural role specific to the actual
package rather than inventing a central or shared role it does not have.
Make each block add distinct technical information; avoid generic architectural
praise or repeating the same responsibility across all three blocks.

For a package whose modules implement database-backed repositories:

[Example: package responsibilities](../examples/packages.md#package-responsibilities)

Adapt this description to the package's verified responsibilities and dependencies;
do not apply the database role to unrelated packages.
