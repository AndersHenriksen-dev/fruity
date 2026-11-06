# CLAUDE.md

A food image classifier, trained, deployed and measured as a small production service. The point of this repo is the infrastructure around the model. It is a fork of my DTU MLOps group project: the hand-in is tagged `dtu-2024`. Everything here is public, so write for a reader who has never seen it.

## Run things

```bash
uv sync --all-extras                 # install
uv run pre-commit install            # once: ruff, mypy, line endings and gitleaks on every commit
uv run fruity train experiment=convnext_tiny   # train; Hydra overrides follow
uv run fruity compare                # measure the trained models, choose one, write evals/RESULTS.md
uv run fruity finalize               # fix the final model, score it on the test set once, write evals/FINAL.md
uv run fruity serve                  # serve the model on http://127.0.0.1:8000
uv run fruity predict photo.jpg      # name the food in one image
uv run streamlit run src/fruity/lib/frontend/app.py   # the demo page
uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest   # what CI checks
```

## Index of `.claude/` and related files

| File | Read it when | What it covers |
|---|---|---|
| [.claude/reference/python-style.md](.claude/reference/python-style.md) | **Before writing or editing any `.py` file** | The single source of truth for Python here. |
| [.claude/reference/git-workflow.md](.claude/reference/git-workflow.md) | **Before creating a branch, a commit or a pull request** | Branch names, commit messages, rebasing, pull request bodies, attribution. |
| [.claude/settings.json](.claude/settings.json) | Changing permissions or hooks | Allowed, asked and denied commands, and the style guide hook. |
| [.pre-commit-config.yaml](.pre-commit-config.yaml) and [.github/workflows/ci.yml](.github/workflows/ci.yml) | Changing what runs on commit or in CI | The automatic half of the style guide and the gitleaks secret scan. |

## Rules

- This is a fork. `gh` defaults to the parent, so check that the default repo is `AndersHenriksen-dev/fruity`. Every pull request goes to this repo, never upstream. The `upstream` remote cannot be pushed to.
- Never commit weights, data, keys or Terraform state. They are git-ignored. Never read `.env`.
- Ask before anything that costs money or creates cloud resources: `terraform apply`, a load test against the live service. Say what it does and what it costs first.
- Before any long run, run the same code path end to end on a tiny sample and read what it writes. Give the long run a time limit and a live log.
- Load tests run only against this repo's own service, capped in users and time.
- Every number in a doc traces back to a file in `evals/`. Results tables and charts are generated, never edited by hand.
- Config is what someone could change without changing how the code works. A Python file that needs config has a YAML file at the same path under `config/`, read with `config_for(__name__, ...)`. Training composes its config with Hydra instead, under `config/training/`.

## Attribution: the agent never credits itself

Anders is the only author of commits, pull request bodies, comments and docs from here on. No `Co-Authored-By:` trailer naming a tool, agent or model, no "Generated with" line, and no text that says an AI tool built or helped with the work. Credit the original group by name. Never override `user.name`, `user.email` or `--author`.

## Writing style (everything that is not Python)

- Never use em dashes anywhere. Use commas, colons, full stops or parentheses.
- Plain English, short sentences, numbers instead of adjectives, no hype words. README in first person singular, with what the group built kept apart from what I added.
- Write about the code and the results as they are now, not about how they got there.
- Git: follow [.claude/reference/git-workflow.md](.claude/reference/git-workflow.md). Branches `category/description`, one per task, rebased onto `main`. Commits `tag(scope): Header` with a body that explains why, author `Anders Henriksen <anhenr.dev@gmail.com>`. Squash merge.

## Layout

```text
src/fruity/
|-- cli.py                 the entry point: reads the command line and hands over
|-- lib/                   all other Python
|   |-- training/          training the classifier
|   |-- evaluation/        measuring trained models and choosing one
|   |-- serving/           the HTTP API
|   |-- frontend/          the demo page
|   `-- shared/            what they all use: nothing here imports them
`-- config/                the same subfolders as lib/: serving/api.py reads serving/api.yaml
tests/                     the same subfolders again
```
