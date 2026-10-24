# Building the paper from one command.
#
#   make            regenerate every number, then typeset the PDF
#   make numbers    regenerate only (needs the Python environment)
#   make pdf        typeset only, from the committed .tex tree
#   make check      structural checks that do not need TeX
#   make arxiv      build the tarball arXiv takes, and prove it compiles alone
#   make clean      remove intermediates, keeping the PDF
#
# Every number in the paper comes from studies/make_paper_tex.py, which reads only
# committed outputs, so this target is reproducible from a clean checkout.
#
# The generator runs from the repository root, not from this directory: it imports
# the `studies` package, which is not importable from paper/. The TeX commands run
# here, where main.tex is.

REPO := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)

PYTHON ?= python
TEX ?= pdflatex
LATEXMK ?= latexmk

.PHONY: all numbers pdf check arxiv clean

all: numbers pdf

numbers:
	cd "$(REPO)" && $(PYTHON) -m studies.make_paper_tex

pdf:
	@if command -v $(LATEXMK) >/dev/null 2>&1; then \
		$(LATEXMK) -pdf -interaction=nonstopmode -halt-on-error main.tex; \
	elif command -v $(TEX) >/dev/null 2>&1; then \
		$(TEX) -interaction=nonstopmode -halt-on-error main.tex && \
		bibtex main && \
		$(TEX) -interaction=nonstopmode -halt-on-error main.tex && \
		$(TEX) -interaction=nonstopmode -halt-on-error main.tex; \
	else \
		echo "No TeX installation found: neither $(LATEXMK) nor $(TEX) is on PATH." >&2; \
		echo "Install TeX Live or MiKTeX, then run 'make -C paper pdf' again." >&2; \
		echo "The .tex tree needs no generator to build; see paper/SUBMISSION.md." >&2; \
		exit 1; \
	fi

check:
	cd "$(REPO)" && $(PYTHON) -m studies.check_paper
	cd "$(REPO)" && $(PYTHON) -m studies.make_paper_tex --check

# arXiv takes one .tar.gz containing main.tex, refs.bib, generated/ and figures/.
# build_arxiv.sh assembles it from a scratch copy rather than from this directory,
# so a file the paper needs but the archive omits fails here instead of on arXiv's
# compiler, and compiles it on its own where TeX is available. The recipe is a
# script rather than make syntax because a five-stage TeX run inside a make `if`
# is where the first version of this target broke on CI without saying why.
arxiv:
	bash build_arxiv.sh

clean:
	rm -f main.aux main.bbl main.blg main.log main.out main.toc main.fls main.fdb_latexmk
	rm -rf build
