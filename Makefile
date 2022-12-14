DOCKER_REPO ?= public.ecr.aws/i8e5j7a1/robot-api
VERSION ?= $(shell cat VERSION)
DOCKER_TAG ?= ${DOCKER_REPO}/robot-api:${VERSION}

ifeq (${SILENT},1)
	VERBOSE_TEST :=
else
	VERBOSE_TEST := -v
endif

buildx_push:
	docker buildx build \
		--push \
		-t ${DOCKER_TAG} \
		--build-arg CACHEBUST=$(shell git --git-dir=libdds/.git describe) \
		.

buildx_build: docker_login
		docker buildx build \
		-t ${DOCKER_TAG} \
		--build-arg CACHEBUST=$(shell git --git-dir=libdds/.git describe) \
		.

docker_login:
	set -ex
	aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${DOCKER_REGISTRY}
