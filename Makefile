ENV_DIR := $(shell pwd)/_env
ENV_PYTHON := ${ENV_DIR}/bin/python
PYTHON_BIN := $(shell which python)

DEB_COMPONENT := clearwater-etcd
DEB_MAJOR_VERSION := 1.0${DEB_VERSION_QUALIFIER}
DEB_NAMES := clearwater-etcd clearwater-cluster-manager clearwater-config-manager clearwater-management
DEB_ARCH := all

# The build has been seen to fail on Mac OSX when trying to build on i386. Enable this to build for x86_64 only
X86_64_ONLY=0

.DEFAULT_GOAL = deb

.PHONY: test
test: setup.py env
	${PYTHON_BIN} setup.py test -v

${ENV_DIR}/bin/flake8: env
	${ENV_DIR}/bin/pip install flake8

${ENV_DIR}/bin/coverage: env
	${ENV_DIR}/bin/pip install coverage

verify: ${ENV_DIR}/bin/flake8
	${ENV_DIR}/bin/flake8 --select=E10,E11,E9,F src/

style: ${ENV_DIR}/bin/flake8
	${ENV_DIR}/bin/flake8 --select=E,W,C,N --max-line-length=100 src/

explain-style: ${ENV_DIR}/bin/flake8
	${ENV_DIR}/bin/flake8 --select=E,W,C,N --show-pep8 --first --max-line-length=100 src/

.PHONY: coverage
coverage: ${ENV_DIR}/bin/coverage setup.py
	rm -rf htmlcov/
	${ENV_DIR}/bin/coverage erase
	${ENV_DIR}/bin/coverage run --source src --omit "**/test/**"  setup.py test
	${ENV_DIR}/bin/coverage report -m
	${ENV_DIR}/bin/coverage html

.PHONY: env
env: setup.py $(ENV_DIR)/bin/python build-eggs install-eggs

$(ENV_DIR)/bin/python:
	# Set up the virtual environment
	virtualenv --setuptools --python=$(PYTHON_BIN) $(ENV_DIR)
	$(ENV_DIR)/bin/easy_install "setuptools>0.7"
	$(ENV_DIR)/bin/easy_install distribute

include build-infra/cw-deb.mk

.PHONY: build-eggs
build-eggs: setup.py common/setup.py src
	# Generate .egg files
	${ENV_DIR}/bin/python setup.py bdist_egg -d eggs
	cd common && ${ENV_DIR}/bin/python setup.py bdist_egg -d ../eggs

	# Download the egg files they depend upon
	${ENV_DIR}/bin/easy_install -zmaxd eggs/ eggs/*.egg

.PHONY: install-eggs
install-eggs: eggs/
	# Install the downloaded egg files (this should match the Debian postinst)
	${ENV_DIR}/bin/easy_install --allow-hosts=None -f eggs/ eggs/*.egg

.PHONY: deb
deb: env build-eggs deb-only

.PHONY: clean
clean: envclean pyclean

.PHONY: pyclean
pyclean:
	find src -name \*.pyc -exec rm -f {} \;
	rm -rf src/*.egg-info dist
	rm -f .coverage
	rm -rf htmlcov/

.PHONY: envclean
envclean:
	rm -rf bin eggs develop-eggs parts .installed.cfg bootstrap.py .downloads .buildout_downloads *.egg .eggs *.egg-info
	rm -rf distribute-*.tar.gz
	rm -rf $(ENV_DIR)

