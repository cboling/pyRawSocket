# Copyright 2020, Boling Consulting Solutions
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Configure shell
SHELL = bash -eu -o pipefail

include setup.mk

# Variables
VERSION           ?= $(shell cat ../VERSION)
DOCKER_BUILD_ARGS := --rm --force-rm
VENVDIR           := venv
TESTVENVDIR       := ${VENVDIR}-tests
EXVENVDIR         := ${VENVDIR}-examples
VENV_BIN          ?= virtualenv
VENV_OPTS         ?= --python=python3.6 -v

# ignore these directories
.PHONY: test dist examples

default: help

# This should to be the first and default target in this Makefile
help:
	@echo "Usage: make [<target>]"
	@echo "where available targets are:"
	@echo
	@echo "help                 : Print this help"
	@echo "dist                 : Create source distribution of the python package"
	@echo "upload               : Upload test version of python package to test.pypi.org"
	@echo
	@echo "test                 : Run all unit test"
	@echo "lint                 : Run pylint on packate"
	@echo "venv                 : Create virtual environment for package"
	@echo "venv-examples        : Create virtual environment for local examples"
	@echo
	@echo "clean                : Remove all temporary files except virtual environments"
	@echo "distclean            : Remove all temporary files includig virtual environments"
	@echo

dist:
	@ echo "Creating python source distribution"
	rm -rf dist/
	python setup.py sdist

upload: dist
	@ echo "Uploading sdist to test.pypi.org"
	twine upload --repository-url https://test.pypi.org/legacy/ dist/*

venv: distclean
	virtualenv --python=python3.6 ${VENVDIR};\
    source ./${VENVDIR}/bin/activate ; set -u ;\
    pip install -r requirements.txt

clean:
	@ -rm -rf .tox *.egg-info
	@ -find . -name '*.pyc' | xargs rm -f
	@ -find . -name '__pycache__' | xargs rm -rf
	@ -find . -name '__pycache__' | xargs rm -rf
	@ -find . -name 'htmlcov' | xargs rm -rf
	@ -find . -name 'junit-report.xml' | xargs rm -rf
	@ -find . -name 'pylint.out.*' | xargs rm -rf

distclean: clean
	@ -rm -rf ${VENVDIR} ${EXVENVDIR} ${TESTVENVDIR}

######################################################################
# Example venv support

venv-examples:
	@ $(VENV_BIN) ${VENV_OPTS} ${EXVENVDIR};\
        source ./${EXVENVDIR}/bin/activate ; set -u ;\
        pip install -r examples/requirements.txt

######################################################################
# Test support

COVERAGE_OPTS=--with-xcoverage --with-xunit --cover-package=rawsocket\
              --cover-html --cover-html-dir=tmp/cover

venv-test:
	@ $(VENV_BIN) ${VENV_OPTS} ${TESTVENVDIR};\
        source ./${TESTVENVDIR}/bin/activate ; set -u ;\
        pip install -r test/requirements.txt

# TODO: Add support for tox later
#test:
#	@ echo "Executing unit tests w/tox"
#	tox

test: clean run-as-root-tests  # venv-test
	@ echo "Executing all unit tests"
	@ . ${TESTVENVDIR}/bin/activate && echo "TODO: $(MAKE)"

run-as-root-docker:
	@ docker build $(DOCKER_BUILD_ARGS) -t test-as-root:latest -f Dockerfile.run-as-root .

run-as-root-tests: # run-as-root-docker
	docker run -i --rm -v ${PWD}:/pyrawtest --privileged test-as-root:latest env PYTHONPATH=/pyrawtest python /pyrawtest/test/test_as_root.py

lint: clean # venv
	@ echo "Executing all unit tests"
	@ . ${VENVDIR}/bin/activate && echo "TODO: $(MAKE)"

# end file
