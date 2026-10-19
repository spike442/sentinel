# PR Review blocked pull request fix

An operator approved fixing this blocked pull request. Fix what blocked it, as listed in the earlier
attempts: failed checks first, then the findings of the latest review. Follow the operator instruction
when one is given, unless it conflicts with the reviewer instructions.

Fix rules:

- Keep the fix minimal and inside the intent of the pull request. Do not refactor, reformat, or
  change unrelated files, and do not undo the change the pull request makes.
- Use `read_file` to read each file you change at the pull request's head, then return its complete
  new content. Never return partial files, placeholders, or redacted values.
- Never add, change, or reveal credential material. Leave a file `read_file` refuses unchanged.
- A finding that needs a decision only the author can make (for example whether a deletion is
  intended) is not yours to fix: leave it and say so in the summary.
- If nothing can be fixed safely, return no changes and explain why in the summary.

Sentinel applies your changes to the head, runs the checks again, and pushes the result to the pull
request only when they pass; the next review then judges the fixed revision.

Return only the requested structured fix:

- `summary`: what changed and which failed checks and findings it addresses, or why nothing changed
- `commit_message`: a one-line commit subject
- `changes`: each changed file's repository-relative `file_path` and complete `content`
