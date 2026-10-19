# Dotfiles Bash startup and CLI dependency chain

Repository: `dotfiles`. Scope: interactive shell behavior and missing-tool diagnosis.

## Bash initialization

The root `.bashrc` delegates to `.config/bash/bashrc`. That configuration returns immediately
for noninteractive shells. It establishes environment defaults and PATH entries, then sources
aliases, functions, and completions. Optional integrations are enabled only when their binaries
are available. Consequently an interactive terminal, CI shell, and container command can have
different PATH, aliases, and hooks even under the same user.

Aqua's global configuration points at the dotfiles checkout by default; relocation requires
checking that path. User-local binaries, language toolchains, Aqua shims, and optional Krew
plugins are additional PATH layers. For a missing command, inspect `command -v`, the effective
PATH, Aqua config location, and whether the shell was restarted after installation.

## Tool ownership

The Aqua catalog includes cloud/Kubernetes CLI tools, AWS CLI for S3, uv, PostgreSQL client
binaries including psql, and terminal utilities. Versions remain in `aqua.yaml`. Do not infer
that Go Task, 1Password CLI, WezTerm, fonts, or OS packages are provisioned merely because a
downstream repository uses them; inspect the catalog and install prerequisites separately.

Completion definitions are generated for available Kubernetes tools. Starship initializes the
prompt; direnv manages directory-specific environment hooks. A prompt showing a package version
is presentation, not the source of a Sentinel release version. Project virtual environments and
Python dependencies are still managed by each project's setup.

## Alias and function effects

Aliases can replace `cat` with bat and `ls` with eza/exa. Use `command cat` or an explicit binary
when exact noninteractive output matters. Git/Kubernetes abbreviations are conveniences, not
an API contract for scripts or agents. Functions include directory helpers, file backup/copy,
commit helpers, and a yazi launcher that changes the parent shell's working directory.

Some helpers stage all files, amend commits, restore working-tree changes, or force-push main.
Never use them blindly during automation. Inspect `type <name>` and the function/alias source
before execution; use explicit non-destructive Git commands for investigation.

Sources: `.config/bash/bashrc`, `.config/bash/aliases.sh`, `.config/bash/functions.sh`,
`.config/bash/completions.sh`, `.config/starship.toml`, `aqua.yaml`.
