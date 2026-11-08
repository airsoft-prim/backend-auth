# Functions and methods

Start with a short summary of the action. An additional detailed description is
optional for ordinary functions and methods, regardless of visibility. Specialized
rules for constructors and properties below take precedence. Omit it when the
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
  Include an explicitly raised exception only if it can escape this callable.
  Omit exceptions caught and handled internally without escaping. For explicit
  re-raises or translations that can escape, document the outgoing exception type
  and its condition, not a consumed cause. Do not infer `Raises:` entries solely
  from assertions, type annotations, or dependency documentation.

Do not add empty sections. Keep documented types consistent with the signature
and implementation. Indent section entries consistently using Google Style.
Describe parameter meaning, return semantics, and failure conditions directly;
omit conversational lead-ins and explanations that merely repeat section labels.

## Value semantics and types

Repeat types in `Args:`, `Returns:`, and `Yields:` even when annotated. Use concrete
Python type expressions consistent with the signature: `str | None`, `list[User]`,
`dict[str, int]`, `tuple[int, str]`, and `Callable[[int], str]`. Preserve meaningful
project aliases rather than expanding them into less readable expressions. Use
`None` for the value/type, not vague substitutes such as "empty" or "nothing".

Explain what a value represents, not merely its parameter name or type. Where
relevant, state units, inclusive or exclusive bounds, ordering, and the meaning of
sentinel values or an absent result. For example, document a timeout as a duration
in seconds, and distinguish an empty collection from `None` when both are possible.
Do not invent constraints or repeat defaults unless their meaning needs explanation.

For `*args` and `**kwargs`, retain the leading stars and describe the accepted
values and their purpose. Document the per-argument value type from the signature,
not a tuple/dict wrapper solely because Python collects variadic inputs:
`*names (str): Names to include.` or
`**labels (str): Label values keyed by label name.` Explain accepted keyword names
or forwarding behavior when they matter to the contract.

## Async functions and generators

For non-generator `async def`, describe the operation performed when awaited and the resolved
result in `Returns:`. Do not describe the return as a coroutine object merely
because the function is asynchronous.

For synchronous and asynchronous generators, `Yields:` describes each emitted
value, not the iterator or generator object. If iteration has a meaningful natural
end, explain its termination condition. Describe deferred side effects and their
timing when callers need that distinction: for example, an operation performed
on iteration rather than when the generator is created. Do not imply immediate
execution when work is deferred until awaiting or advancing iteration.

The following micro-example documents emitted values rather than the generator
object; work occurs during iteration, and iteration ends after the supplied names.

[Example: generator values](../examples/callables.md#generator-values)

## Constructors

Document `__init__` using the public-method rules for applicable `Args:` and
`Raises:` sections, with these exceptions:

- Always use the exact summary "Initialize the class." regardless of the project's
  predominant documentation language.
- Do not add a detailed description between the summary and sections.
- Omit `Returns:` because initialization has no meaningful return value.

Use a one-line docstring when no sections apply; do not add padding lines.
Parameter and exception descriptions follow the normal project-language rule.

[Example: constructor](../examples/callables.md#constructor)

## Protected and private methods

For protected (`_name`) and private (`__name`) methods, a summary alone is allowed.
Add a detailed description when useful; a full docstring with applicable sections
is also allowed when the situation warrants it, such as a complex internal contract.
Python special methods (`__name__`) are not private merely because they start with
underscores; document them according to their contract.

[Example: protected method](../examples/callables.md#protected-method)

## Properties

For `@property`, write only a one-line summary describing the value or
characteristic exposed by the property. Do not add a detailed description or
`Args:`, `Returns:`, or `Raises:` sections, even when the getter has complex logic.

[Example: property](../examples/callables.md#property)

## Class and static methods

For `@classmethod`, follow ordinary method rules according to visibility: a short
summary, an optional detailed description, and applicable sections. Omit `cls`
from `Args:` and document the actual returned type, including `Self` when used.
Do not describe class binding as though it were a caller-supplied parameter.

[Example: class method](../examples/callables.md#class-method)

For `@staticmethod`, follow ordinary function rules with the existing visibility
conventions for methods. The decorator does not require additional prose.

[Example: static method](../examples/callables.md#static-method)

## Overloads

For `@overload`, put the shared docstring on the implementation only. Leave overload
signatures without docstrings. Describe supported inputs and the corresponding
results together; explain input-dependent output types when they differ. Apply
the same directly-raised-exception rule to the implementation's `Raises:` section.

[Example: overloads](../examples/callables.md#overloads)

## Full callable example

The following assumes the implementation validates the lower bound, finds an open
port, and returns its number. Do not claim that it establishes a connection unless
it actually does so. The example assumes both failures are explicitly raised
in this method rather than merely propagated from the lookup helper.

[Example: public callable](../examples/callables.md#public-callable)
