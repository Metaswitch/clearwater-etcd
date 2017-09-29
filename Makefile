ROOT ?= ${PWD}
ENV_DIR := $(shell pwd)/_env
PYTHON_BIN := $(shell which python)

DEB_COMPONENT := clearwater-etcd
DEB_MAJOR_VERSION ?= 1.0${DEB_VERSION_QUALIFIER}
DEB_NAMES := clearwater-etcd clearwater-cluster-manager clearwater-queue-manager clearwater-config-manager clearwater-management
DEB_ARCH := all

# The build has been seen to fail on Mac OSX when trying to build on i386. Enable this to build for x86_64 only
X86_64_ONLY=0

.DEFAULT_GOAL = deb

COVERAGE_SETUP_PY = cluster_mgr_setup.py queue_mgr_setup.py config_mgr_setup.py plugins_setup.py
COVERAGE_PYTHON_PATH = src:common
SRC_DIR = src/
FLAKE8_INCLUDE_DIR = src/
FLAKE8_EXCLUDE_DIR = src/clearwater_etcd_plugins/
BANDIT_EXCLUDE_LIST = src/metaswitch/clearwater/queue_manager/test/,src/metaswitch/clearwater/plugin_tests/,src/metaswitch/clearwater/etcd_tests/,src/metaswitch/clearwater/etcd_shared/test,src/metaswitch/clearwater/config_manager/test/,src/metaswitch/clearwater/cluster_manager/test/,common,_env,.wheelhouse,debian,build_clustermgr,build_configmgr,build_shared

include build-infra/cw-deb.mk
include build-infra/python.mk

.PHONY: fvtest
fvtest: fvtest_setup.py env ${ENV_DIR}/.test_requirements
	PYTHONPATH=src:common ${PYTHON} fvtest_setup.py test -v

.PHONY: test
test: coverage

coverage: ${ENV_DIR}/.test_requirements

.PHONY: test_cluster_mgr
test_cluster_mgr: cluster_mgr_setup.py env ${ENV_DIR}/.test_requirements
	PYTHONPATH=src:common ${PYTHON} cluster_mgr_setup.py test -v

.PHONY: test_queue_mgr
test_queue_mgr: queue_mgr_setup.py env ${ENV_DIR}/.test_requirements
	PYTHONPATH=src:common ${PYTHON} queue_mgr_setup.py test -v

.PHONY: test_config_mgr
test_config_mgr: config_mgr_setup.py env ${ENV_DIR}/.test_requirements
	PYTHONPATH=src:common ${PYTHON} config_mgr_setup.py test -v

.PHONY: test_plugins
test_plugins: plugins_setup.py env ${ENV_DIR}/.test_requirements
	PYTHONPATH=src:common ${PYTHON} plugins_setup.py test -v

.PHONY: run_test
run_test: queue_mgr_setup.py config_mgr_setup.py cluster_mgr_setup.py env ${ENV_DIR}/.test_requirements
	PYTHONPATH=src:common ${PYTHON} cluster_mgr_setup.py test -v && PYTHONPATH=src:common ${PYTHON} queue_mgr_setup.py test -v && PYTHONPATH=src:common ${PYTHON} config_mgr_setup.py test -v && PYTHONPATH=src:common ${PYTHON} plugins_setup.py test -v



${ENV_DIR}/.test_requirements: common/requirements-test.txt fv-requirements.txt ${ENV_DIR}/.wheels-installed
	${PIP} install -r common/requirements-test.txt -r fv-requirements.txt

# Macro to define how the various etcd targets use python common
define python_common_component

# Add a target that builds the python-common wheel into the correct wheelhouse
${ENV_DIR}/.$1_build_common_wheel: common/requirements.txt $(shell find common/metaswitch -type f -not -name "*.pyc")
	cd common && WHEELHOUSE=../$1_wheelhouse make build_common_wheel
	touch $$@

# Add dependency to the install-wheels to ensure we also install the python-common wheel
${ENV_DIR}/.$1-install-wheels: ${ENV_DIR}/.$1_build_common_wheel

endef

# Queue manager definitions
queue_mgr_SETUP = queue_mgr_setup.py shared_setup.py
queue_mgr_REQUIREMENTS = queue_mgr-requirements.txt common/requirements.txt shared-requirements.txt
queue_mgr_SOURCES = $(shell find src/metaswitch -type f -not -name "*.pyc") $(shell find common/metaswitch -type f -not -name "*.pyc")
$(eval $(call python_common_component,queue_mgr))
$(eval $(call python_component,queue_mgr))

# Cluster manager definitions
cluster_mgr_SETUP = cluster_mgr_setup.py shared_setup.py
cluster_mgr_REQUIREMENTS = cluster_mgr-requirements.txt common/requirements.txt shared-requirements.txt
cluster_mgr_SOURCES = $(shell find src/metaswitch -type f -not -name "*.pyc") $(shell find common/metaswitch -type f -not -name "*.pyc")
$(eval $(call python_common_component,cluster_mgr))
$(eval $(call python_component,cluster_mgr))

# Config manager definitions
config_mgr_SETUP = config_mgr_setup.py shared_setup.py
config_mgr_REQUIREMENTS = config_mgr-requirements.txt common/requirements.txt shared-requirements.txt
config_mgr_SOURCES = $(shell find src/metaswitch -type f -not -name "*.pyc") $(shell find common/metaswitch -type f -not -name "*.pyc")
$(eval $(call python_common_component,config_mgr))
$(eval $(call python_component,config_mgr))

# Add a dependency to the wheels-built target for the alarm constants
${ENV_DIR}/.wheels-built: src/metaswitch/clearwater/queue_manager/alarm_constants.py src/metaswitch/clearwater/config_manager/alarm_constants.py src/metaswitch/clearwater/cluster_manager/alarm_constants.py

src/metaswitch/clearwater/queue_manager/alarm_constants.py: clearwater-queue-manager.root/usr/share/clearwater/infrastructure/alarms/clearwater_queue_manager_alarms.json common/metaswitch/common/alarms_writer.py common/metaswitch/common/alarms_parser.py common/metaswitch/common/alarm_severities.py
	python common/metaswitch/common/alarms_writer.py --json-file="clearwater-queue-manager.root/usr/share/clearwater/infrastructure/alarms/clearwater_queue_manager_alarms.json" --constants-file=$@

src/metaswitch/clearwater/config_manager/alarm_constants.py: clearwater-config-manager.root/usr/share/clearwater/infrastructure/alarms/clearwater_config_manager_alarms.json common/metaswitch/common/alarms_writer.py common/metaswitch/common/alarms_parser.py common/metaswitch/common/alarm_severities.py
	python common/metaswitch/common/alarms_writer.py --json-file="clearwater-config-manager.root/usr/share/clearwater/infrastructure/alarms/clearwater_config_manager_alarms.json" --constants-file=$@

src/metaswitch/clearwater/cluster_manager/alarm_constants.py: clearwater-cluster-manager.root/usr/share/clearwater/infrastructure/alarms/clearwater_cluster_manager_alarms.json common/metaswitch/common/alarms_writer.py common/metaswitch/common/alarms_parser.py common/metaswitch/common/alarm_severities.py
	python common/metaswitch/common/alarms_writer.py --json-file="clearwater-cluster-manager.root/usr/share/clearwater/infrastructure/alarms/clearwater_cluster_manager_alarms.json" --constants-file=$@

.PHONY: env
env: cluster_mgr_setup.py queue_mgr_setup.py config_mgr_setup.py shared_setup.py plugins_setup.py ${ENV_DIR}/.wheels-installed

.PHONY: deb
deb: env deb-only

.PHONY: clean
clean: envclean pyclean

