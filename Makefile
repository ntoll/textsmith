XARGS := xargs -0 $(shell test $$(uname) = Linux && echo -r)
GREP_T_FLAG := $(shell test $$(uname) = Linux && echo -T)
export PYFLAKES_BUILTINS=_

all:
	@echo "\nThere is no default Makefile target right now. Try:\n"
	@echo "make run - run the local development version of TextSmith."
	@echo "make clean - reset the project and remove auto-generated assets."
	@echo "make flake8 - run the PyFlakes code checker."
	@echo "make mypy - run the static type checker."
	@echo "make test - run the test suite."
	@echo "make coverage - view a report on test coverage."
	@echo "make tidy - tidy code with the 'black' formatter."
	@echo "make check - run all the checkers and tests."
	@echo "make docs - use Sphinx to create project documentation."

clean:
	rm -rf .coverage
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf docs/_build
	rm -rf .eggs
	rm -rf build
	rm -rf dist
	find . \( -name '*.py[co]' -o -name dropin.cache \) -delete
	find . \( -name '*.bak' -o -name dropin.cache \) -delete
	find . \( -name '*.tgz' -o -name dropin.cache \) -delete
	find . | grep -E "(__pycache__)" | xargs rm -rf

run: clean
ifeq ($(VIRTUAL_ENV),)
	@echo "\n\nCannot run TextSmith. Your Python virtualenv is not activated."
else
	hypercorn textsmith.app:app	
endif

flake8:
	flake8 --ignore=E231,W503 --exclude=docs,textsmith/script/parser.py

mypy:
	find . \( -name _build -o -name var -o -path ./docs -o -path ./integration -o -path ./textsmith/mdx -o -path ./textsmith/script \) -type d -prune -o -name '*.py' -print0 | $(XARGS) mypy

test: clean
	pytest --random-order --disable-pytest-warnings

coverage: clean
	pytest --random-order --disable-pytest-warnings --cov-config .coveragerc --cov-report term-missing --cov=textsmith tests/

tidy: clean
	@echo "\nTidying code with black..."
	black -l 79 textsmith
	black -l 79 tests

check: clean tidy flake8 mypy coverage

docs: clean
	$(MAKE) -C docs html
	@echo "\nDocumentation can be found here:"
	@echo file://`pwd`/docs/_build/html/index.html
	@echo "\n"
