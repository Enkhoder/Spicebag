A patch release that makes hue ranges easier to enter and pastes more predictable.

```bash
pip install --upgrade spicebag
```

- A hyphen typed right after the first hue, as in `60-`, now says "Separate hues with <kbd>SPACE</kbd>." instead of "Hyphen is misplaced." A hue range is two hues separated by a space, like `60 120`.
- A pasted hue range is tidied: `60-120` and `60 - 120` go in as `60 120`, `60 - -120` as `60 -120`, and extra whitespace is trimmed. `60 -120` still means 60 to -120.
- A minus sign must sit right before its number: `-20` works, `- 20` is refused.
- A paste into the hue range, image count or cell size that hits an invalid character goes in up to that character and shows its error, instead of being refused or filtered.