# Repository instructions

<!-- cloud-development:start -->
## Cloud development
Read `CLOUD_DEVELOPMENT.md` before changing setup. Run `bash .codex/setup.sh`
then `bash .codex/check.sh` in a Linux environment with the documented runtimes.
Keep `.devcontainer`, setup/check commands, dependency locks, and cloud CI in sync
when adding packages, services, or new applications. New codebases must include
a development container and a reproducible install/check workflow from day one.
Keep credentials and personal/raw data outside images and Git. Use local emulators
or synthetic fixtures for tests. Setup and checks must not deploy, trade, send
messages, scrape logged-in accounts, or access production services automatically.
Report platform restrictions and failed/missing tests explicitly; source checks
are not application tests. Native Apple builds need a macOS/Xcode runner.
<!-- cloud-development:end -->
