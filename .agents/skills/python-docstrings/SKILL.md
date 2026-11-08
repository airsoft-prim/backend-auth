---
name: python-docstrings
description: >-
  Write and review Python documentation using Google-style docstrings. Use when
  documenting Python code or adding, editing, or reviewing docstrings for packages,
  classes, methods, and functions.
---

# Python Docstrings

All Python docstrings must use Google Style, regardless of the documented object.
Write documentation in the language used by the overwhelming majority of the
project's existing documentation. Inspect representative README files, project
docs, and existing docstrings before choosing the language; do not infer it from
the language of this skill, the current conversation, or one isolated file.
If there is no clear predominant language, follow an explicit project convention
or ask the user when the choice remains ambiguous.

Preserve API names and established technical terms. Keep Google-style section
headings such as `Args:`, `Returns:`, and `Raises:` in English. Examples in `examples/`
illustrate structure, not a required language for project documentation.

## Using this skill

Read [writing style and shared conventions](references/style.md) for every task.
Documentation must be an independent, precise technical reference, never a replay
of the conversation. Verify claims against code and relevant usage; investigate
uncertainty and ask the user when material facts remain unresolved. Keep literals
and inline code in prose in single backticks. Preserve runtime behavior when
working on documentation and update docstrings when behavior changes.

Read only the additional references applicable to the documented objects:

- [Packages](references/packages.md): package placement in `__init__.py` and the
  required summary, extended description, and architectural role.
- [Classes](references/classes.md): required summary and detailed description.
- [Functions and methods](references/callables.md): sections and types, escaping
  directly raised exceptions, async/generator behavior, visibility, constructors,
  properties, class/static methods, and overloads. Apply the constructor and
  property rules exactly as specified there.

References link to the relevant micro-examples in `examples/`. Consult them when
writing the corresponding object; do not load unrelated examples. For editing
wording, use [concise phrasing examples](examples/wording.md).

## Review

Verify the documentation language against the predominant project language and
check Google Style throughout. For packages, verify placement in `__init__.py`
and all three prose blocks. Verify behavioral claims against the code. For classes, check
that a detailed description is present. For callables, check that the level of
detail fits their visibility and complexity, and that applicable sections contain
accurate value types and semantics. Check that summaries, descriptions, and sections
add distinct information. For async functions and generators, verify resolved or
yielded types and any material execution timing. Include only directly raised
exceptions that can escape; exclude internally handled and merely propagated errors.
For properties, allow only a one-line summary. For class methods, omit `cls`;
for overloads, keep documentation on the implementation only. Preserve the fixed
constructor summary and its no-description rule. Check terminology consistency
and update descriptions affected by behavior changes.
Check that literal values and inline code in prose use single backticks while
Google-style structural labels retain their normal format. Confirm that changes
stay within scope.

Read the result as an independent technical reference: can a maintainer understand
it without the chat? Remove conversation traces and any phrase that adds no fact,
clarifies no contract, and explains no necessary constraint. Preserve required
structure and essential technical detail while tightening the wording.
