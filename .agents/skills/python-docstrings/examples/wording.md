# Wording examples

Use these patterns only when the implementation supports the stated behavior.
The precise form adds verifiable semantics rather than extra adjectives.

| Vague wording                 | Precise wording                                             |
| ----------------------------- | ----------------------------------------------------------- |
| Process users.                | Block users whose access has expired.                       |
| Return the search result.     | Return the user, or `None` if no record matches.            |
| Manage the cache.             | Store public keys in Redis until their TTL expires.         |
| `timeout (float): Timeout.`   | `timeout (float): Response wait duration in seconds.`       |
