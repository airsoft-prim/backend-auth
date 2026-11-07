---
name: python-docstrings
description: >-
  Write and review Python documentation using Google-style docstrings. Use when
  documenting Python code or adding, editing, or reviewing docstrings for packages, classes, methods, and functions.
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
headings such as `Args:`, `Returns:`, and `Raises:` in English. The English examples
below illustrate structure, not a required language for project documentation.

## Editorial principle

Documentation is a standalone technical reference, not a record of the conversation
with the developer or a repetition of the agent's chat messages. Write for a reader
who has only the code and documentation, with no access to the discussion.

Use precise terminology, direct statements, and compact sentences. Convey the most
useful technical information in the fewest words that preserve accuracy and
readability. Remove filler, conversational phrasing, promotional claims, and
repeated explanations. Do not compress away conditions, constraints, or distinctions
needed to understand the contract.

Use discussion context to identify facts to verify, not prose to copy. Document the
resulting behavior and relevant design constraints; omit requests, approvals,
implementation chronology, abandoned approaches, and references to what the agent
or developer said. Include design rationale only when it explains a lasting
technical constraint, expressed without conversational history.

Use one consistent term for each concept throughout the project. Prefer concrete
verbs that identify the action over vague wording such as "handles", "manages", or
"ensures" when a more precise description is available.

## Shared conventions

- Place a docstring directly inside the documented definition (or at the top of
  `__init__.py` for a package), using triple double
  quotes. Start the first line immediately after the opening quotes with a short
  sentence describing the object or action. End it with a period.
- Separate the summary, detailed description, and sections with blank lines.
  For multiline docstrings, put the closing quotes on a separate line aligned
  with the opening quotes. A summary-only docstring fits on one line.
- Follow project indentation and line-length conventions. Use spaces, not tabs.
- Read the implementation and relevant dependencies before writing. Describe actual
  behavior rather than assumptions based on names. Do not invent algorithms,
  guarantees, or security properties.
- Make detailed descriptions explain purpose and operation without repeating the
  summary or narrating the implementation line by line.
- In summaries and detailed descriptions, describe the observable contract rather
  than narrating implementation steps. Where relevant, state valid input ranges,
  units, the meaning of `None`, ordering guarantees, mutations of supplied objects,
  and other side effects. Keep the summary short and put necessary detail in the
  description; do not add a description when the existing rules allow its omission
  and the summary already conveys the relevant behavior.
- When behavior changes, update the affected docstrings in the same change.
  Treat documentation that contradicts current behavior as a documentation defect.
- For documentation tasks, edit only the requested documentation and preserve
  runtime behavior.

## Packages

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

```python
# __init__.py
"""Foundational components of the application.

Provides a cohesive collection of modules responsible for
the project's core functionality and internal abstractions.

The package serves as a central layer for shared logic,
reusable components, and cross-module integration.
"""
```

## Classes

Always provide both a short first-line summary of what the class is and a detailed
explanation of why it is needed and how it works, separated by a blank line.
The detailed description is required for classes, including small ones. Keep it
as short as the actual responsibilities and mechanism allow; the required block
does not justify padding or a narrative of how the class was developed.

Add `Attributes:` only when it provides useful information about public attributes.

```python
class RateLimitingMiddleware:
    """Middleware that limits the number of requests to the server.

    Limits requests from each IP address to reduce server load during bursts
    of traffic. Counts requests within a fixed time window and rejects requests
    that exceed the configured limit.
    """
```

Use this description only if the implementation actually uses a fixed window.

## Functions and methods

Start with a short summary of the action. An additional detailed description is
optional for every function and method, regardless of visibility. Omit it when the
implementation is small and its logic is immediately obvious. Otherwise, use it
to explain behavior that the summary and signature do not make clear.

For public functions and methods, include applicable Google-style sections:

- `Args:`: document each parameter as `name (type): Description.`, including its
  type even when the signature is annotated. Omit implicit `self` and `cls`.
- `Returns:`: use `type: Description.` to describe the returned value, including
  its type even when the signature is annotated. Omit this section when there is
  no meaningful return value.
- `Yields:`: for generators, describe yielded values as `type: Description.`
  instead of describing them as ordinary return values.
- `Raises:`: list only exceptions explicitly raised in the documented function's
  or method's own body, using `ExceptionType: Condition that causes it.` Do not
  list exceptions merely propagated from called functions, methods, or dependencies.
  If a caught exception is explicitly re-raised or translated in this body,
  document the exception raised here and its condition.

Do not add empty sections. Keep documented types consistent with the signature
and implementation. Indent section entries consistently using Google Style.
Describe parameter meaning, return semantics, and failure conditions directly;
omit conversational lead-ins and explanations that merely repeat section labels.

### Constructors

Document `__init__` using the public-method rules for applicable `Args:` and
`Raises:` sections, with these exceptions:

- Always use the exact summary "Инициализация класса." regardless of the project's
  predominant documentation language.
- Do not add a detailed description between the summary and sections.
- Omit `Returns:` because initialization has no meaningful return value.

Use a one-line docstring when no sections apply; do not add padding lines.
Parameter and exception descriptions follow the normal project-language rule.

```python
def __init__(self, a: int) -> None:
    """Инициализация класса.

    Args:
        a (int): Аргумент А.
    """
    ...
```

### Protected and private methods

For protected (`_name`) and private (`__name`) methods, a summary alone is allowed.
Add a detailed description when useful; a full docstring with applicable sections
is also allowed when the situation warrants it, such as a complex internal contract.
Python special methods (`__name__`) are not private merely because they start with
underscores; document them according to their contract.

```python
def _get_process_name(self, pid: int) -> str:
    """Get a process name by its ID."""
    ...
```

### Full callable example

The following assumes the implementation validates the lower bound, finds an open
port, and returns its number. Do not claim that it establishes a connection unless
it actually does so. The example assumes both failures are explicitly raised
in this method rather than merely propagated from the lookup helper.

```python
def connect_to_next_port(self, minimum: int) -> int:
    """Return the next available port at or above the lower bound.

    Validate the minimum port and search for the nearest open port starting
    at that value.

    Args:
        minimum (int): Minimum port number, at least 1024.

    Returns:
        int: The available port number.

    Raises:
        ValueError: If minimum is below 1024.
        ConnectionError: If no available port is found.
    """
    ...
```

## Review

Verify the documentation language against the predominant project language and
check Google Style throughout. For packages, verify placement in `__init__.py`
and all three prose blocks. Verify behavioral claims against the code. For classes, check
that a detailed description is present. For callables, check that the level of
detail fits their visibility and complexity, and that applicable sections contain
accurate types and conditions for exceptions raised directly in the callable.
Check terminology consistency and update descriptions affected by behavior changes.
Confirm that changes stay within scope.

Read the result as an independent technical reference: can a maintainer understand
it without the chat? Remove conversation traces and any phrase that adds no fact,
clarifies no contract, and explains no necessary constraint. Preserve required
structure and essential technical detail while tightening the wording.
