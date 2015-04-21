# Makefile for clearwater-etcd package

# this should come first so make does the right thing by default
all: deb

DEB_COMPONENT := clearwater-etcd
DEB_MAJOR_VERSION := 1.0${DEB_VERSION_QUALIFIER}
DEB_NAMES := clearwater-etcd
DEB_ARCH := all

include build-infra/cw-deb.mk

deb: deb-only

clean:

.PHONY: all deb-only deb clean
