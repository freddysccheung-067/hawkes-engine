# Building the paper from one command.
#
#   make            regenerate every number, then typeset the PDF
#   make numbers    regenerate only (needs the Python environment)
#   make pdf        typeset only, from the committed .tex tree
#   make check      structural checks that do not need TeX
#   make clean      remove intermediates, keeping the PDF
#
# `make` is the command the paper is built with. Every number in it comes from
# studies/make_paper_tex.py, which reads only committed outputs, so this target is
# reproducible from a clean checkout.

PYTHON ?= python
TEX ?= pdflatex
LATEXMK ?= latexmk

.PHONY: all numbers pdf check clean

all: numbers pdf

numbers:
	$(PYTHON) -m studies.make_paper_tex

pdf:
	@if command -v $(LATEXMK) >/dev/null 2>&1; then \
		$(LATEXMK) -pdf -interaction=nonstopmode -halt-on-error main.tex; \
	else \
		$(TEX) -interaction=nonstopmode -halt-on-error main.tex && \
		bibtex main && \
		$(TEX) -interaction=nonstopmode -halt-on-error main.tex && \
		$(TEX) -interaction=nonstopmode -halt-on-error main.tex; \
	fi

check:
	$(PYTHON) -m studies.check_paper
	$(PYTHON) -m studies.make_paper_tex --check

clean:
	rm -f main.aux main.bbl main.blg main.log main.out main.toc main.fls main.fdb_latexmk
