#!/usr/bin/env bash
# Build the tarball arXiv takes, and compile it on its own.
#
#   ./paper/build_arxiv.sh              build, and compile if TeX is on PATH
#   ./paper/build_arxiv.sh --no-compile build only
#
# The archive is assembled in a scratch directory rather than from paper/ itself,
# because the point of the exercise is to find a file the paper needs that is not
# in the archive. Building in place would find nothing: every file is already
# there.
#
# On a compile failure the TeX error lines are printed as GitHub workflow commands
# when running under Actions, so the failure is readable from the run page rather
# than only from a log that needs authentication to download.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$HERE/build"
SCRATCH="$OUT/arxiv"
TARBALL="$OUT/hawkes-engine-paper.tar.gz"

fail() {
    echo "::error title=arXiv archive::$*" 2>/dev/null || echo "ERROR: $*" >&2
    echo "$*" >&2
    exit 1
}

announce() {
    # ::error:: is only meaningful under Actions; printing it elsewhere is noise.
    if [ -n "${GITHUB_ACTIONS:-}" ]; then
        echo "::error title=arXiv archive::$*"
    fi
    echo "$*" >&2
}

rm -rf "$SCRATCH"
mkdir -p "$SCRATCH"

for required in main.tex refs.bib generated figures; do
    [ -e "$HERE/$required" ] || fail "paper/$required is missing from the repository"
    cp -r "$HERE/$required" "$SCRATCH/"
done

# The archive is exactly what SUBMISSION.md says arXiv receives.
( cd "$SCRATCH" && tar czf "$TARBALL" main.tex refs.bib generated figures ) \
    || fail "could not create the tarball"

if ! command -v pdflatex >/dev/null 2>&1; then
    echo "no pdflatex on PATH: archive built, not test-compiled"
    echo "wrote $TARBALL"
    exit 0
fi

echo "compiling the archive in isolation..."
cd "$SCRATCH" || fail "cannot enter $SCRATCH"

run() {
    local label="$1"
    shift
    if ! "$@" > "$label.out" 2>&1; then
        announce "the archive does not compile on its own: $label failed"
        # A TeX error is the line beginning with '!' and the 'l.N' line after it.
        grep -n -E '^!' -A 4 main.log 2>/dev/null | head -40 >&2
        grep -n -E '^! ' bibtex.out 2>/dev/null | head -20 >&2
        exit 1
    fi
}

run pass1 pdflatex -interaction=nonstopmode -halt-on-error main.tex
run bibtex bibtex main || true
run pass2 pdflatex -interaction=nonstopmode -halt-on-error main.tex
run pass3 pdflatex -interaction=nonstopmode -halt-on-error main.tex

[ -f main.pdf ] || fail "compiled without error but produced no PDF"

echo "archive compiles on its own: $(wc -c < main.pdf) bytes"
echo "wrote $TARBALL"
