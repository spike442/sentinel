# Dotfiles maintenance, validation, and releases

Repository: `dotfiles`. Scope: reviewing workstation changes without disrupting the user.

## Validate without installing

Inspect the diff and resolve shell dependencies before running anything. `bash -n` checks Bash
syntax without executing installation, linking files, downloading plugins, or changing shell
state. Review symlink destinations and backup handling separately; syntax success does not
prove an installer is safe or portable. Parse YAML/TOML with appropriate tooling, and validate
Lua/WezTerm behavior in an isolated environment if those tools are available.

Do not execute `install.sh`, `sync.sh`, the user's startup file, or mutating aliases simply to
collect documentation. Do not delete untracked configuration or overwrite local modifications
to obtain a clean baseline. Home-directory state, fonts, credentials, and plugin caches are
outside the repository's declarative files.

## Dependency and configuration changes

Update tool pins in `aqua.yaml` deliberately; the catalog's checksum support does not cover
every remote executable path, such as the terminal plugin. Check whether downstream Sentinel or
Homelab tasks require a new command, and make its installation ownership explicit. Do not add
fallback package managers or silently install privileged system packages to hide missing tools.

For a shell change, consider interactive/noninteractive behavior, duplicate PATH entries,
quoting, filenames with spaces, alias expansion, and source order. Keep scripts explicit about
whether they modify the working tree or HOME. Check that backup recovery is possible before
replacing linked configuration.

## Release semantics

The GitHub release workflow is scheduled and manually triggerable. It creates a calendar-date
Git tag at the workflow commit, skipping an existing date tag. It does not build or publish
Sentinel images and should not be described as Sentinel's semantic-version release process. A tag alone
does not prove the dotfiles were installed or validated on a workstation.

Sources: `.github/workflows/release.yaml`, `install.sh`, `sync.sh`, `aqua.yaml`,
`.config/bash/`, `.config/wezterm/wezterm.lua`.
