# Contributing

Talk-Server is a FastAPI speech-to-text server, OpenAI-compatible, running faster-whisper on CUDA.
This says how a change gets in, and what is particular to this repository. The shape of the flow is
the same one its sibling, Talk-Client, follows.

Setting up and running the server is in [README.md](README.md). To have the commit rule checked at
the commit rather than on the pull request, call it from a hook of your own, once per clone:

    printf '#!/bin/sh\nexec sh .github/commit-format.sh "$1"\n' > .git/hooks/commit-msg
    chmod +x .git/hooks/commit-msg

## Branches

Two long-lived branches, and the difference between them is one question: has this been published?

- `dev` is where work lands. It stays green, and it is what a topic branch is opened from and
  rebased onto.
- `main` is what has been released. Every commit on it has been tagged, and nothing reaches it
  except by fast-forward from `dev` at the moment of a release.

So `main` is always an exact prefix of `dev`: whatever `dev` holds beyond `main` is precisely what
is written and not yet published. `prefix.yml` says so out loud when it stops being true.

Every other branch is a topic branch, named for what it does:

    <type>/what-the-branch-does

The type is one of the nine below, whichever the branch mostly is. After the slash, two to five
words in lower case joined by dashes, saying what the branch does rather than which file it opens.
`release/0.2.0` is the one shape that departs from it: such a branch carries the version bump and
nothing else, so the version is the whole of the name, with `-alpha` or `-beta` after it for a
pre-release and nothing after those words.

No name carries a date, an author or an issue number. The commit that does the work names the issue
it closes.

**The history is linear and carries no merge commit.** A topic branch is rebased onto `dev` and
enters by a pull request merged with the rebase button. If that button refuses, the rebase was not
done, and the answer is to rebase rather than to merge.

## Pull requests

**Every batch enters by one**, including one written by whoever owns the repository: the build runs
on `pull_request`, so a batch folded in by hand is built only once it is already in `dev`.

**"Rebase and merge", and neither of the other two buttons.** A merge commit forks a history that
never forks. A squash collapses a branch into one commit and throws away the bodies, which is where
the reasoning for each step lives.

**`dev` reaches `main` by a fast-forward and NOT by that button.** All three buttons rewrite, and
`main` is already an ancestor of `dev`, so replaying `dev` onto it hands `main` a second copy of
every commit under a fresh hash. The request is still the right place for a release, for the record
and for the checks it runs; what merges it is:

    git push origin origin/dev:main

A request carries one label, the type of its branch, which `label.yml` puts on. A release request
carries `release`. The labels are `feat`, `fix`, `perf`, `refactor`, `docs`, `test`, `build`, `ci`,
`chore` and `release`.

**An issue is closed from the commit that closes it**, on a line of its own at the foot of the body,
`Closes #12`. A closing keyword written in a request fires against the default branch, which is
`main`, and no ordinary request targets it.

## Commits

One logical change per commit, and a subject in conventional-commit form:

    <type>(<scope>)!: what the commit does

That form is worth more here than elsewhere, because the rebase button replays every subject
verbatim into the public history instead of collapsing them into the request's title.

| type | what it carries |
| --- | --- |
| `feat` | something the server did not do |
| `fix` | a defect corrected |
| `perf` | the same behaviour for less |
| `refactor` | no change of behaviour at all, dead code removed included |
| `docs` | the docs, the changelog, this file, comments on their own |
| `test` | the tests and what they run over |
| `build` | the Dockerfile, the dependencies, the version bump |
| `ci` | `.github/workflows` and the rule they run |
| `chore` | whatever none of the others is |

The scope is optional and names a tree of code. This repository has not needed one so far, and a
subject without it is the usual shape; where one helps, it is a directory of `rest/` or a guide
under `docs/`, such as `admin` or `endpoints`.

The subject is imperative and starts on a verb, in lower case, and carries no full stop. The whole
line is 72 columns or fewer with the prefix counted in. A body is for the reason, when the reason is
not in the diff.

A `!` before the colon marks a change that breaks something that used to work, such as a route, a
response shape or an environment variable that clients and deployments rely on, and what breaks is
written in the body.

`.github/commit-format.sh` holds the rule for a subject and a branch name, and
`.github/workflows/commits.yml` runs that file over every commit of a pull request. One rule, one
home. The request whose base is `main` is the only one exempt, since it carries commits that have
each already been checked on their way into `dev`.

## Changelog

`CHANGELOG.md` carries an `Unreleased` section, and a change somebody running the server would
notice is written into it **in the same commit that makes the change**, under `Added`, `Changed`,
`Fixed` or `Removed`. A refactor that changes nothing visible gets no entry. Entries are written in
the words of somebody who runs the thing, not of somebody who builds it: why a change was made stays
in the commit that made it. `commits.yml` warns, without failing, when a `feat`, `fix` or `perf`
branch changes no line of the file.

At a release the `Unreleased` heading is renamed after the version and dated.

## Verifying a change

    make lint     # ruff format, ruff check --fix, then mypy on rest/
    make test     # pytest with the coverage floor

CI runs the checking forms of the same gates, on Python 3.11 to 3.13:

    uv run ruff check .
    uv run ruff format --check .
    uv run mypy rest
    uv run pytest --cov=rest --cov-fail-under=80

The floor is 80 percent of `rest/`. The build job also builds the Docker image without pushing it,
which shows that the Dockerfile still resolves against `uv.lock`.

**CI has no GPU.** The suite never loads the model, so it answers for everything except CUDA itself.
A change to the transcription path is checked by starting the image on a card and sending it a
file, and the request says so when that was not done.

## Versions and releasing

A version is three numbers, and after them either `-alpha`, or `-beta`, or nothing at all. Nothing
follows the word, a counter least of all.

The version lives in two files and they move together:

- `pyproject.toml`, under `version`
- `uv.lock`, in the `talk-server` entry, which `uv lock` rewrites after the first edit

There is no published package and no release workflow. A release is a tag on `main`, and the Docker
image is built from the Dockerfile by whoever deploys it. Nothing derives the tag from the version
or compares the two: a human types the tag, and the request template asks for the check.

The path, in order:

1. A branch of its own, `release/<version>`, carrying the bump and the changelog rename and nothing
   else. It enters `dev` by a pull request like every other batch.
2. Once `dev` is green, open the request from `dev` to `main` with its own template:
   `gh pr create --base main --head dev --template release.md`. It is not there to be pressed.
3. `git push origin origin/dev:main`, and the request closes itself as merged.
4. `git tag v<version> origin/main` and push the tag. The tag is the release.

## Encoding and text

UTF-8 without BOM everywhere, accents included, and LF line endings in the repository and the
working tree alike. `.gitattributes` enforces the endings.

Prose uses plain ASCII punctuation and no dash between two spaces. English in code, docstrings,
commits and documentation.
