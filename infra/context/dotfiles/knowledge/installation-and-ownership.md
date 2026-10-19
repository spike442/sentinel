# Dotfiles installation and configuration ownership

Repository: `dotfiles`. Scope: user workstation configuration, not cluster desired state.

## Repository layout

The root `.bashrc` loads `.config/bash/bashrc`. `.config/` holds Bash, Git, WezTerm, Starship,
bat, and k9s configuration. `aqua.yaml` pins user CLI dependencies. `install.sh` coordinates
configuration linking and Aqua installation; `sync.sh` owns symlink/backup behavior.

This repository is distinct from Homelab's host automation and Sentinel's container configuration.
Installing personal shell aliases does not configure a Kubernetes service account or make
tools available in a worker image. User Git identity and signing keys are not bot credentials.

## Link and backup semantics

`sync.sh` traverses regular files in `.config/` and creates individual absolute symlinks under
the user's configuration directory. It also links the root `.bashrc`. Existing conflicting
files, directories, or links are moved into a timestamped backup directory in HOME, preserving
their relative paths. Already-correct symlinks are left alone. Parent directories are created
as necessary; the whole `.config/` directory is not replaced by one symlink.

The script also backs up a legacy tmux configuration location. Moving the checkout can break
absolute links; rerunning sync repairs ownership at the new location but can create new backups.
Do not delete backup directories without checking whether they contain unique configuration.

## Installation boundaries

`install.sh` invokes synchronization before provisioning tools. If Aqua is missing, it downloads
the pinned Aqua installer, establishes its data/config paths, and runs Aqua installation.
Failure after sync can leave links already updated even when tools were not installed.

The script does not install every OS application, terminal font, or credential manager. Bash,
basic shell utilities, and network access are prerequisites. Treat the installer as code that
changes the user's home directory and downloads executables, not a read-only validation step.
Review the current scripts and existing backups before running it on an unfamiliar machine.

Sources: `install.sh`, `sync.sh`, `.bashrc`, `.config/`, `aqua.yaml`.
