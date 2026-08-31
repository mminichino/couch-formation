.PHONY: pypi build publish test commit patch minor major download remote_download remote prerelease tag prerelease_tag remote_tag branch merge container sync test_internal test_kvdb test_project_config test_aws_drv test_gcp_drv test_azure_drv test_aws_cli test_gcp_cli test_azure_cli test_capella_cli test_drv test_cli test_integration test_deploy test_aws test_gcp test_azure test_capella
export LOGPATH := $(shell pwd)/tests/log
export PROJECT_NAME := $$(basename $$(pwd))
export PROJECT_VERSION := $(shell cat VERSION)
export TEST_PATH := $(shell pwd)/tests

commit:
	git commit -am "Version $(shell cat VERSION)"
	git push -u origin main
branch:
	git branch "Version_$(shell cat VERSION)"
merge:
	git checkout main
	git pull origin main
	git merge "Version_$(shell cat VERSION)"
	git push origin main
remote:
	git push cblabs main
patch:
	bumpversion --allow-dirty patch
minor:
	bumpversion --allow-dirty minor
major:
	bumpversion --allow-dirty major
sync:
	uv sync
build:
	uv build
publish:
	uv publish
pypi: build publish
download:
	$(eval REV_FILE := $(shell ls -tr dist/*.whl | tail -1))
	gh release upload --clobber -R "mminichino/$(PROJECT_NAME)" $(PROJECT_VERSION) $(REV_FILE)
tag:
	if gh release view -R "mminichino/$(PROJECT_NAME)" $(PROJECT_VERSION) >/dev/null 2>&1 ; then gh release delete -R "mminichino/$(PROJECT_NAME)" $(PROJECT_VERSION) --cleanup-tag -y ; fi
	gh release create -R "mminichino/$(PROJECT_NAME)" \
	-t "Release $(PROJECT_VERSION)" \
	-n "Release $(PROJECT_VERSION)" \
	$(PROJECT_VERSION)
prerelease_tag:
	if gh release view -R "mminichino/$(PROJECT_NAME)" $(PROJECT_VERSION) >/dev/null 2>&1 ; then gh release delete -R "mminichino/$(PROJECT_NAME)" $(PROJECT_VERSION) --cleanup-tag -y ; fi
	gh release create --prerelease -R "mminichino/$(PROJECT_NAME)" \
	-t "Release $(PROJECT_VERSION)" \
	-n "Release $(PROJECT_VERSION)" \
	$(PROJECT_VERSION)
remote_download:
	$(eval REV_FILE := $(shell ls -tr dist/*.whl | tail -1))
	gh release upload --clobber -R "couchbaselabs/$(PROJECT_NAME)" $(PROJECT_VERSION) $(REV_FILE)
remote_tag:
	gh release create -R "couchbaselabs/$(PROJECT_NAME)" \
	-t "Release $(PROJECT_VERSION)" \
	-n "Release $(PROJECT_VERSION)" \
	$(PROJECT_VERSION)
prerelease: build prerelease_tag download
release: pypi tag download remote_tag remote_download remote
container:
	docker system prune -f
	docker buildx prune -f
	docker buildx build --load --platform linux/amd64,linux/arm64 -t cftest -f $(TEST_PATH)/Dockerfile .

test_internal:
	uv run pytest tests/internal
test_kvdb:
	uv run pytest tests/internal/test_kvdb.py
test_project_config:
	uv run pytest tests/internal/test_project_config.py

test_aws_drv:
	uv run pytest tests/aws/driver
test_gcp_drv:
	uv run pytest tests/gcp/driver
test_azure_drv:
	uv run pytest tests/azure/driver

test_aws_cli:
	uv run pytest -s --log-cli-level=INFO tests/aws/integration/test_cli.py
test_gcp_cli:
	uv run pytest -s --log-cli-level=INFO tests/gcp/integration/test_cli.py
test_azure_cli:
	uv run pytest -s --log-cli-level=INFO tests/azure/integration/test_cli.py
test_capella_cli:
	uv run pytest -s --log-cli-level=INFO tests/capella/integration

test_drv:
	uv run pytest -m driver
test_cli:
	uv run pytest tests/aws/integration/test_cli.py tests/gcp/integration/test_cli.py tests/azure/integration/test_cli.py
test_integration:
	uv run pytest -m integration
test_deploy:
	uv run pytest -m regression

test_aws:
	uv run pytest -m cf_aws
test_gcp:
	uv run pytest -m cf_gcp
test_azure:
	uv run pytest -m cf_azure
test_capella:
	uv run pytest -m cf_capella

test:
	mkdir -p $(LOGPATH)
	uv run pytest
