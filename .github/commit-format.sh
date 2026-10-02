#!/bin/sh
#
# Refuses a subject that is not in the form CONTRIBUTING describes, and a branch whose name is not
# either. The rule has this one home: `.github/workflows/commits.yml` runs this file over every
# commit of a pull request, and a contributor can run the same file at the commit by calling it from
# a commit-msg hook of their own (CONTRIBUTING says how).
#
# The branch is the second argument because a hook reads it off HEAD, while the workflow checks out
# a detached merge commit and has to say which branch it means. An empty second argument checks no
# branch at all, which is what the workflow passes for every commit after the first so the same
# complaint is not printed once per commit.
#
#     sh .github/commit-format.sh <message-file> [branch]

set -eu

# Deliberately not a whitelist of scopes: a scope names a tree of code and the trees move. This asks
# only that a scope look like one.
types='feat|fix|perf|refactor|docs|test|build|ci|chore'
subject_re="^($types)(\([a-z0-9-]+\))?!?: [a-z].*[^.]$"
# `release` is a branch prefix and not a commit type: what lands from such a branch is the version
# bump, which is a `build`. The version is the whole name, so this is the one branch carrying dots.
# Three numbers, then either `-alpha`, or `-beta`, or nothing: a counted pre-release is refused here
# rather than at the tag, where the repair costs a branch already pushed under the wrong name.
branch_re="^(($types)/[a-z0-9]+(-[a-z0-9]+)*|release/[0-9]+\.[0-9]+\.[0-9]+(-(alpha|beta))?)$"

die() {
	echo "commit-format: $1" >&2
	echo >&2
	echo "  <type>(<scope>)!: what the commit does" >&2
	echo "  <type>/what-the-branch-does" >&2
	echo >&2
	echo "  type    feat fix perf refactor docs test build ci chore" >&2
	echo "  scope   optional, a tree of code" >&2
	echo "  !       marks a change that breaks something that used to work" >&2
	echo "  subject imperative, lower case, no full stop, 72 columns for the whole line" >&2
	echo >&2
	echo "The whole of it is in CONTRIBUTING.md, under Branches and Commits." >&2
	exit 1
}

# What git will store, rather than what the file holds: it drops the comment lines an editor
# template leaves behind and the blank lines above the subject, so the check has to drop them too.
stored=$(sed '/^#/d' "$1" | sed '/./,$!d')
subject=$(printf '%s\n' "$stored" | head -n 1)
second=$(printf '%s\n' "$stored" | sed -n '2p')

if [ -z "$subject" ]; then
	die "the message is empty."
fi

if [ "${#subject}" -gt 72 ]; then
	die "the subject is ${#subject} columns, and the limit is 72."
fi

if ! printf '%s' "$subject" | grep -Eq "$subject_re"; then
	die "the subject is not in the form this repository uses: $subject"
fi

if [ -n "$second" ]; then
	die "line 2 has to be blank, since it is what separates a subject from its body."
fi

# Absent under `git rebase` and anywhere else HEAD is detached, and there is nothing to check then.
if [ "$#" -ge 2 ]; then
	branch=$2
else
	branch=$(git symbolic-ref --short -q HEAD || true)
fi

case "$branch" in
	'' | main | dev) ;;
	*)
		if ! printf '%s' "$branch" | grep -Eq "$branch_re"; then
			die "the branch is not named the way this repository names one: $branch"
		fi
		;;
esac
