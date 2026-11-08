# Writing style and shared conventions

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

### Information density

Give each part a distinct purpose: the summary names the main action, the detailed
description explains significant behavior, and `Args:`, `Returns:`, or `Yields:`
clarify individual values. Do not repeat the same explanation across all parts.
A required block must add relevant information, not padding. Keep essential
constraints even when shortening the text.

## Shared conventions

- Place a docstring directly inside the documented definition (or at the top of
  `__init__.py` for a package), using triple double
  quotes. Start the first line immediately after the opening quotes with a short
  sentence describing the object or action. End it with a period.
- Separate the summary, detailed description, and sections with blank lines.
  For multiline docstrings, put the closing quotes on a separate line aligned
  with the opening quotes. A summary-only docstring fits on one line.
- In docstring prose, wrap literal values and inline code fragments in single
  backticks: `1024`, `None`, `True`, `alias="mama"`, and `is_active=True`.
  Apply this to numbers used as exact code values, string literals, parameter
  references, attribute names, calls, expressions, and type names mentioned in
  prose. Wrap a complete fragment once, rather than each token separately.
  Ordinary prose and quantities that are not code literals need no code styling.
  Keep Google-style section headings and structural entries such as
  `name (type):` and `type:` in their normal format; this rule applies to the
  descriptive text within those entries, not their structural labels.
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

### Uncertain behavior or purpose

When purpose, behavior, or a guarantee cannot be established from the definition,
inspect the relevant implementations, callers, tests, and project documentation.
Treat names, previous docstrings, and conversation statements as clues to verify,
not sufficient evidence for a behavioral claim.

If material uncertainty remains, ask the user a specific question before asserting
that detail. Continue documenting independently verified facts where possible.
Do not fill required descriptions with plausible guesses or generic filler, and
do not put speculation, unresolved questions, or chat history into the docstring.

For concise wording comparisons, read [wording examples](../examples/wording.md).
