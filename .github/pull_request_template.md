<!--
Merge with "Rebase and merge" and with nothing else. "Create a merge commit" forks a history that
never forks, and "Squash and merge" collapses the branch into one commit and throws away the bodies,
which is where the reasoning for each step lives. If the rebase button is greyed out, this branch is
behind `dev`; rebase it and force-push rather than merging `dev` into it.

The base is `dev`. A request opened against `main` is a mistake to repair: `main` takes `dev` alone,
at a release, by a fast-forward, and `main-from-dev` refuses anything else.

An issue is closed from the COMMIT that closes it, on a line of its own at the foot of the body,
never from here: a closing keyword written in a request fires against the default branch, which no
ordinary request targets.
-->

## What changes

<!-- One paragraph. What the branch does to the server, not how the diff is arranged. -->

## Why it was not already like that

<!--
The cause, not the symptom. What the code did instead, and what made that the wrong thing: a
default that was never set, a queue that outlived its timeout, a header read against the wrong
scheme. "It is new" is a fine answer for a feature.
-->

## What proves it

<!--
Say which of these the claim rests on. An unticked line is not a failure, it is a scope.

- `make lint` and `make test`, or the four commands under them: `ruff check`, `ruff format --check`,
  `mypy rest` and `pytest` with the coverage floor.
- A request against a running server: the call that was made and what came back. A response or a
  log line carries more than a description.
- Say plainly if the change touches the GPU path and was not run on a card, since CI has none.
-->

## What it leaves owing

<!-- Known gaps, anything a later branch has to finish, or "nothing". -->

---

- [ ] Rebased onto `dev`, so the merge is a fast-forward.
- [ ] `make lint` and `make test` green locally, after the rebase and not before it.
- [ ] `CHANGELOG.md` carries an entry under `Unreleased`, or this changes nothing anybody running
      the server would notice.
- [ ] Every place that states a fact this branch changed now states the new one: `README.md`,
      `CONTRIBUTING.md`, `CLAUDE.md`, `.env.example`, `docs/`, and the comments around the code.
