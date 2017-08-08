ROOT ?= ${PWD}
ENV_DIR := $(shell pwd)/_env
ENV_PYTHON := ${ENV_DIR}/bin/python
PYTHON_BIN := $(shell which python)

DEB_COMPONENT := clearwater-etcd
DEB_MAJOR_VERSION ?= 1.0${DEB_VERSION_QUALIFIER}
DEB_NAMES := clearwater-etcd clearwater-cluster-manager clearwater-queue-manager clearwater-config-manager clearwater-management
DEB_ARCH := all

# The build has been seen to fail on Mac OSX when trying to build on i386. Enable this to build for x86_64 only
X86_64_ONLY=0

.DEFAULT_GOAL = deb

.PHONY: fvtest
fvtest: fvtest_setup.py env
	PYTHONPATH=src:common ${ENV_PYTHON} fvtest_setup.py test -v

.PHONY: test
test: coverage

.PHONY: test_cluster_mgr
test_cluster_mgr: cluster_mgr_setup.py env
	PYTHONPATH=src:common ${ENV_PYTHON} cluster_mgr_setup.py test -v

.PHONY: test_queue_mgr
test_queue_mgr: queue_mgr_setup.py env
	PYTHONPATH=src:common ${ENV_PYTHON} queue_mgr_setup.py test -v

.PHONY: test_config_mgr
test_config_mgr: config_mgr_setup.py env
	PYTHONPATH=src:common ${ENV_PYTHON} config_mgr_setup.py test -v

.PHONY: test_plugins
test_plugins: plugins_setup.py env
	PYTHONPATH=src:common ${ENV_PYTHON} plugins_setup.py test -v

.PHONY: run_test
run_test: queue_mgr_setup.py config_mgr_setup.py cluster_mgr_setup.py env
	PYTHONPATH=src:common ${ENV_PYTHON} cluster_mgr_setup.py test -v && PYTHONPATH=src:common ${ENV_PYTHON} queue_mgr_setup.py test -v && PYTHONPATH=src:common ${ENV_PYTHON} config_mgr_setup.py test -v && PYTHONPATH=src:common ${ENV_PYTHON} plugins_setup.py test -v

${ENV_DIR}/bin/flake8: env
	${ENV_DIR}/bin/pip install flake8

${ENV_DIR}/bin/coverage: env
	${ENV_DIR}/bin/pip install coverage==4.1

# TODO Add etcd-plugins to the verify step, once full UT is in place
verify: ${ENV_DIR}/bin/flake8
	${ENV_DIR}/bin/flake8 --select=E10,E11,E9,F src/ --exclude src/clearwater_etcd_plugins/

style: ${ENV_DIR}/bin/flake8
	${ENV_DIR}/bin/flake8 --select=E,W,C,N --max-line-length=100 src/

explain-style: ${ENV_DIR}/bin/flake8
	${ENV_DIR}/bin/flake8 --select=E,W,C,N --show-pep8 --first --max-line-length=100 src/

# TODO Remove plugin exclusions from .coveragerc, and ensure full coverage of all plugins
.PHONY: coverage
coverage: ${ENV_DIR}/bin/coverage cluster_mgr_setup.py queue_mgr_setup.py config_mgr_setup.py plugins_setup.py
	rm -rf htmlcov/
	${ENV_DIR}/bin/coverage erase
	PYTHONPATH=src:common ${ENV_DIR}/bin/coverage run cluster_mgr_setup.py test
	PYTHONPATH=src:common ${ENV_DIR}/bin/coverage run -a queue_mgr_setup.py test
	PYTHONPATH=src:common ${ENV_DIR}/bin/coverage run -a config_mgr_setup.py test
	PYTHONPATH=src:common ${ENV_DIR}/bin/coverage run -a plugins_setup.py test
	${ENV_DIR}/bin/coverage combine
	${ENV_DIR}/bin/coverage report -m --fail-under 100
	${ENV_DIR}/bin/coverage xml

.PHONY: env
env: cluster_mgr_setup.py queue_mgr_setup.py config_mgr_setup.py shared_setup.py plugins_setup.py $(ENV_DIR)/bin/python build-eggs

$(ENV_DIR)/bin/python:
	# Set up the virtual environment
	virtualenv --setuptools --python=$(PYTHON_BIN) $(ENV_DIR)
	$(ENV_DIR)/bin/easy_install "setuptools==24"
	$(ENV_DIR)/bin/easy_install distribute

BANDIT_EXCLUDE_LIST = src/metaswitch/clearwater/queue_manager/test/,src/metaswitch/clearwater/plugin_tests/, src/metaswitch/clearwater/etcd_tests/,src/metaswitch/clearwater/etcd_shared/test, src/metaswitch/clearwater/config_manager/test/,src/metaswitch/clearwater/cluster_manager/test/,common,_env, .eggs,debian,build_clustermgr,build_configmgr,build_shared
include build-infra/cw-deb.mk
include build-infra/python.mk

.PHONY: build-eggs
build-eggs: ${ENV_DIR}/.cluster-mgr-build-eggs ${ENV_DIR}/.queue-mgr-build-eggs ${ENV_DIR}/.config-mgr-build-eggs

${ENV_DIR}/.queue-mgr-build-eggs: queue_mgr_setup.py shared_setup.py common/setup.py $(shell find src/metaswitch -type f -not -name "*.pyc") $(shell find common/metaswitch -type f -not -name "*.pyc") src/metaswitch/clearwater/queue_manager/alarm_constants.py
        # Generate .egg files
	${ENV_DIR}/bin/python queue_mgr_setup.py build -b build_queuemgr bdist_egg -d queue_mgr_eggs
	${ENV_DIR}/bin/python shared_setup.py build -b build_shared bdist_egg -d queue_mgr_eggs
	cd common && EGG_DIR=../queue_mgr_eggs make build_common_egg

        # Download the egg files they depend upon
	${ENV_DIR}/bin/easy_install -zmaxd queue_mgr_eggs/ queue_mgr_eggs/clearwater_queue_manager-1.0-py2.7.egg
	${ENV_DIR}/bin/easy_install -zmaxd queue_mgr_eggs/ queue_mgr_eggs/clearwater_etcd_shared-1.0-py2.7.egg
	${ENV_DIR}/bin/easy_install -zmaxd queue_mgr_eggs/ queue_mgr_eggs/metaswitchcommon-0.1-py2.7-linux-x86_64.egg

	touch $@

${ENV_DIR}/.config-mgr-build-eggs: config_mgr_setup.py shared_setup.py common/setup.py $(shell find src/metaswitch -type f -not -name "*.pyc") $(shell find common/metaswitch -type f -not -name "*.pyc") src/metaswitch/clearwater/config_manager/alarm_constants.py
	# Generate .egg files
	${ENV_DIR}/bin/python config_mgr_setup.py build -b build_configmgr bdist_egg -d config_mgr_eggs
	${ENV_DIR}/bin/python shared_setup.py build -b build_shared bdist_egg -d config_mgr_eggs
	cd common && EGG_DIR=../config_mgr_eggs make build_common_egg

	# Download the egg files they depend upon
	${ENV_DIR}/bin/easy_install -zmaxd config_mgr_eggs/ config_mgr_eggs/clearwater_config_manager-1.0-py2.7.egg
	${ENV_DIR}/bin/easy_install -zmaxd config_mgr_eggs/ config_mgr_eggs/clearwater_etcd_shared-1.0-py2.7.egg
	${ENV_DIR}/bin/easy_install -zmaxd config_mgr_eggs/ config_mgr_eggs/metaswitchcommon-0.1-py2.7-linux-x86_64.egg

	touch $@

${ENV_DIR}/.cluster-mgr-build-eggs: cluster_mgr_setup.py shared_setup.py common/setup.py $(shell find src/metaswitch -type f -not -name "*.pyc") $(shell find common/metaswitch -type f -not -name "*.pyc") src/metaswitch/clearwater/cluster_manager/alarm_constants.py
	# Generate .egg files
	${ENV_DIR}/bin/python cluster_mgr_setup.py build -b build_clustermgr bdist_egg -d cluster_mgr_eggs
	${ENV_DIR}/bin/python shared_setup.py build -b build_shared bdist_egg -d cluster_mgr_eggs
	cd common && EGG_DIR=../cluster_mgr_eggs make build_common_egg

	# Download the egg files they depend upon
	${ENV_DIR}/bin/easy_install -zmaxd cluster_mgr_eggs/ cluster_mgr_eggs/clearwater_cluster_manager-1.0-py2.7.egg
	${ENV_DIR}/bin/easy_install -zmaxd cluster_mgr_eggs/ cluster_mgr_eggs/clearwater_etcd_shared-1.0-py2.7.egg
	${ENV_DIR}/bin/easy_install -zmaxd cluster_mgr_eggs/ cluster_mgr_eggs/metaswitchcommon-0.1-py2.7-linux-x86_64.egg

	touch $@

src/metaswitch/clearwater/queue_manager/alarm_constants.py: clearwater-queue-manager.root/usr/share/clearwater/infrastructure/alarms/clearwater_queue_manager_alarms.json common/metaswitch/common/alarms_writer.py common/metaswitch/common/alarms_parser.py common/metaswitch/common/alarm_severities.py
	python common/metaswitch/common/alarms_writer.py --json-file="clearwater-queue-manager.root/usr/share/clearwater/infrastructure/alarms/clearwater_queue_manager_alarms.json" --constants-file=$@
src/metaswitch/clearwater/config_manager/alarm_constants.py: clearwater-config-manager.root/usr/share/clearwater/infrastructure/alarms/clearwater_config_manager_alarms.json common/metaswitch/common/alarms_writer.py common/metaswitch/common/alarms_parser.py common/metaswitch/common/alarm_severities.py
	python common/metaswitch/common/alarms_writer.py --json-file="clearwater-config-manager.root/usr/share/clearwater/infrastructure/alarms/clearwater_config_manager_alarms.json" --constants-file=$@
src/metaswitch/clearwater/cluster_manager/alarm_constants.py: clearwater-cluster-manager.root/usr/share/clearwater/infrastructure/alarms/clearwater_cluster_manager_alarms.json common/metaswitch/common/alarms_writer.py common/metaswitch/common/alarms_parser.py common/metaswitch/common/alarm_severities.py
	python common/metaswitch/common/alarms_writer.py --json-file="clearwater-cluster-manager.root/usr/share/clearwater/infrastructure/alarms/clearwater_cluster_manager_alarms.json" --constants-file=$@

.PHONY: deb
deb: env build-eggs deb-only

.PHONY: clean
clean: envclean pyclean

.PHONY: pyclean
pyclean:
	find src -name \*.pyc -exec rm -f {} \;
	rm -rf src/*.egg-info dist
	rm -rf build build_configmgr build_queuemgr build_clustermgr build_shared
	rm -f .coverage
	rm -rf htmlcov/

.PHONY: envclean
envclean:
	rm -rf bin cluster_mgr_eggs queue_mgr_eggs config_mgr_eggs develop-eggs parts .installed.cfg bootstrap.py .downloads .buildout_downloads *.egg .eggs *.egg-info
	rm -rf distribute-*.tar.gz
	rm -rf $(ENV_DIR)

