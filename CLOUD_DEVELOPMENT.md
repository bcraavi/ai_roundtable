# Cloud development — AI Roundtable

This development environment supplies Linux tools and development dependencies.
Source is mounted at `/workspace`; the image build copies no source, secrets,
raw records, local caches, or production credentials. Production Dockerfiles keep
their existing purpose.

## Local container / Codespaces

Open `.devcontainer/devcontainer.json` with a dev-container client, or run:

```bash
docker build -f .devcontainer/Dockerfile -t cloud-dev .
docker run --rm -it --mount type=bind,source="$PWD",target=/workspace cloud-dev bash
bash .codex/setup.sh
bash .codex/check.sh
```

Use a clean clone so host dependencies and personal files are not mounted into a
remote workspace. Container runs can create dependency/build files in that clone.
Install runs with network access; default checks use no production credentials.
The Dockerfile pins the runtime family; committed dependency locks pin packages.
Refresh image digests and dependencies through reviewed updates.

## Codex cloud

Create an environment and select this GitHub repository. During setup, request the
runtime in `.codex/cloud.json`, run `bash .codex/setup.sh`, then
`bash .codex/check.sh`. Review the setup report and Publish the environment before
starting remote tasks. For the legacy environment, use the same setup script in
the setup/maintenance fields. A devcontainer file alone does not publish or
configure a Codex cloud environment. Installation and startup are separate.

[Official cloud environment guide](https://learn.chatgpt.com/docs/environments/cloud-environments)

Enable the package-manager network preset and add hosts listed in
`.codex/cloud.json` as needed. Add personal values through the environment's
vault/configuration; never copy local `.env`, cloud SDK accounts, browser cookies,
health records, model weights, or private SSH keys into images.

## Check coverage and limitations

Configured checks:

- `python -m unittest discover -s tests -v`
- `.codex/verify.py`: offline Python AST, shell, JSON, JavaScript syntax and Apple XML configuration checks. This is a smoke check, not an application test.

Application test scope: Existing unittest suite; provider CLIs are mocked.

- Live multi-agent reviews require separately installed/authenticated provider CLIs.

## New codebases and packages

Carry this container/setup/check contract into each new repository. Keep runtime
versions, dependency locks, local service instructions, and CI synchronized. Add
a real isolated test suite for new behavior. Cloud setup must never start
deployments, trading, outreach, or other live actions automatically. Native SDK
restrictions must remain explicit. Run the workflow after dependency changes.
