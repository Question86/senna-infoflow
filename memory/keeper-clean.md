# keeper-clean Bridge

Observed repository:

- Owner/repo: `Question86/keeper-clean`
- Branch: `master`
- Purpose from README: code-first Keeper rebuild with a strict clean structure.
- Top-level structure observed:
  - `core_rules/`
  - `core_runtime/`
  - `python/`

## Intended role for Senna

`keeper-clean` becomes the long-term GitHub-backed memory layer for:

- monitor findings worth retaining
- AXI0M / User Yps project development history
- repo decisions and commit references
- infrastructure expansion vectors
- known issues and unresolved gaps
- future automation notes

## Integration stance

Do not dump noisy raw monitor output into long-term memory.

Store distilled state:

1. What changed?
2. Why does it matter?
3. Risk, chance, or structural observation?
4. Recommended next action.
5. What should be remembered later?

## Current link state

As of 2026-06-17, `keeper-clean` was inspected through the GitHub API. It is not copied as a submodule or subtree by this commit because the available GitHub Contents API cannot create gitlinks/submodules and full git clone/subtree operations are outside this connector.

Recommended local/GitHub-runner integration options once shell/git write access is available:

```bash
# Submodule option
git submodule add -b master https://github.com/Question86/keeper-clean.git memory/keeper-clean
git commit -m "Add keeper-clean as Senna memory submodule"

# Or subtree option
git remote add keeper-clean https://github.com/Question86/keeper-clean.git
git fetch keeper-clean master
git subtree add --prefix memory/keeper-clean keeper-clean master --squash
git commit -m "Import keeper-clean as Senna memory subtree"
```

Until then, this bridge documents the relationship and keeps the memory boundary explicit.
