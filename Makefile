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
WORKING_DIR		  := $(dir $(THIS_MAKEFILE) )
PACKAGE_DIR       := $(WORKING_DIR).
TEST_DIR          := $(WORKING_DIR)test
DOCKER_BUILD_ARGS := --rm --force-rm
PYVERSION         ?= ${PYVERSION:-"3.8"}
PYTHON            := python${PYVERSION}
VENVDIR           := venv
TESTVENVDIR       := ${VENVDIR}-test
EXVENVDIR         := ${VENVDIR}-examples

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


venv: $(PACKAGE_DIR)/requirements.txt $(VENVDIR)/.built

venv-sudo: $(PACKAGE_DIR)/requirements.txt $(VENVDIR)/.built
	if [ "$$(realpath ${VENVDIR}/bin/python)" != "${PWD}/${VENVDIR}/bin/python" ]; then \
     mv ${VENVDIR}/bin/python ${VENVDIR}/bin/python.old && \
     cp $$(realpath ${VENVDIR}/bin/python.old) ${VENVDIR}/bin/python && \
     sudo setcap cap_net_raw,cap_net_admin,cap_sys_admin,cap_dac_override=eip ${VENVDIR}/bin/python; fi

venv-test: $(TEST_DIR)/requirements.txt $(TESTVENVDIR)/.built
	@ echo "TEST_DIR is ${TEST_DIR}"

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

docker:
	@ docker build $(DOCKER_BUILD_ARGS) -t pyrawsocket:latest -f Dockerfile .

run-as-root: # pipdocker
	docker run -i --name=twisted_raw --rm -v ${PWD}:/pyrawsocket --privileged pyrawsocket:latest env PYTHONPATH=/pyrawsocket python /pyrawsocket/examples/twisted_raw.py

$(VENVDIR)/.built:
	@ ${PYTHON} -m venv ${VENVDIR}
	@ (source ${VENVDIR}/bin/activate && \
	    if python -m pip install --disable-pip-version-check -r $(PACKAGE_DIR)/requirements.txt; \
	    then \
	        uname -s > ${VENVDIR}/.built; \
	    fi)

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

$(TESTVENVDIR)/.built:
	@ ${PYTHON} -m venv ${TESTVENVDIR}
	@ (source ${TESTVENVDIR}/bin/activate && \
	    if python -m  pip install --disable-pip-version-check -r ${TEST_DIR}/requirements.txt; \
	    then \
	        python -m pip install --disable-pip-version-check pylint; \
	        uname -s > ${TESTVENVDIR}/.built; \
	    fi)

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
