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

TEST_SETUP_PY = cluster_mgr_setup.py queue_mgr_setup.py config_mgr_setup.py plugins_setup.py
TEST_PYTHON_PATH = src:common
TEST_REQUIREMENTS = common/requirements-test.txt fv-requirements.txt requirements-test.txt
CLEAN_SRC_DIR = src/
FLAKE8_INCLUDE_DIR = src/
FLAKE8_EXCLUDE_DIR = src/clearwater_etcd_plugins/
BANDIT_EXCLUDE_LIST = src/metaswitch/clearwater/queue_manager/test/,src/metaswitch/clearwater/plugin_tests/,src/metaswitch/clearwater/etcd_tests/,src/metaswitch/clearwater/etcd_shared/test,src/metaswitch/clearwater/config_manager/test/,src/metaswitch/clearwater/cluster_manager/test/,common,_env,.wheelhouse,debian,build_clustermgr,build_configmgr,build_shared

include build-infra/cw-deb.mk
include build-infra/python.mk

.PHONY: fvtest
fvtest: fvtest_setup.py env ${ENV_DIR}/.test-requirements
	PYTHONPATH=src:common ${PYTHON} fvtest_setup.py test -v

.PHONY: test_plugins
test_plugins: plugins_setup.py env ${ENV_DIR}/.test-requirements
	PYTHONPATH=src:common ${PYTHON} plugins_setup.py test -v

.PHONY: run_test
run_test: test_plugins

# Macro to define the various etcd targets
#
# @param $1 Name of the etcd target (e.g. "queue-mgr")
#
# For the given components, calls into the python_component macro, and also
# ensures that this component depends on building the python-common wheel
define etcd_component

# Define the variables for this component that will be used by the
# python_component macro
$1_SETUP = $1_setup.py shared_setup.py
$1_REQUIREMENTS = $1-requirements.txt common/requirements.txt shared-requirements.txt
$1_SOURCES = $(shell find src/metaswitch -type f -not -name "*.pyc") $(shell find common/metaswitch -type f -not -name "*.pyc")
$1_BUILD_DIRS = T

# Call into the python_component macro in the common python.mk
$$(eval $$(call python_component,$1))

# Add a target that builds the python-common wheel into the correct wheelhouse
${ENV_DIR}/.$1_build_common_wheel: common/requirements.txt $(shell find common/metaswitch -type f -not -name "*.pyc") ${ENV_DIR}/.wheels-built
	cd common && WHEELHOUSE=../$1_wheelhouse make build_common_wheel
	touch $$@

# Add dependency to the install-wheels to ensure we also install the python-common wheel
${ENV_DIR}/.$1-install-wheels: ${ENV_DIR}/.$1_build_common_wheel

# Test definition
.PHONY: test_$1
test_$1: $1_setup.py env ${ENV_DIR}/.test-requirements
	PYTHONPATH=src:common ${PYTHON} $1_setup.py test -v

# Add the test target to run_test
run_test: test_$1

# Add the alarm constants target
src/metaswitch/clearwater/$$(subst mgr,manager,$1)/alarm_constants.py: clearwater-$$(subst _,-,$$(subst mgr,manager,$1)).root/usr/share/clearwater/infrastructure/alarms/clearwater_$$(subst mgr,manager,$1)_alarms.json common/metaswitch/common/alarms_writer.py common/metaswitch/common/alarms_parser.py common/metaswitch/common/alarm_severities.py
	python common/metaswitch/common/alarms_writer.py --json-file="clearwater-$$(subst _,-,$$(subst mgr,manager,$1)).root/usr/share/clearwater/infrastructure/alarms/clearwater_$$(subst mgr,manager,$1)_alarms.json" --constants-file=$$@

# Add a dependency to the build-wheels targets for the alarm constants
${ENV_DIR}/.$1-build-wheels: src/metaswitch/clearwater/$$(subst mgr,manager,$1)/alarm_constants.py

endef

# Use the macro to define the queue-, config- and cluster-manager components
$(eval $(call etcd_component,queue_mgr))
$(eval $(call etcd_component,config_mgr))
$(eval $(call etcd_component,cluster_mgr))

.PHONY: deb
deb: env deb-only

.PHONY: clean
clean: envclean pyclean

