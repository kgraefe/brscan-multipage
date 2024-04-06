DOCKER=podman
SCANNER_MODEL=DCP-7070DW
SCANNER_IP=192.168.178.40
HOST_IP=192.168.178.26

-include local.mak

run: build
	mkdir -p output
	podman run \
		-it \
		--env "SCANNER_MODEL=$(SCANNER_MODEL)" \
		--env "SCANNER_IP=$(SCANNER_IP)" \
		--env "HOST_IP=$(HOST_IP)" \
		--publish "54925:54925/UDP" \
		--volume "$(PWD)/output:/output" \
		kgraefe/brscan-multipage:latest

build:
	podman build \
		--tag kgraefe/brscan-multipage:latest \
		--build-context projectroot=$(PWD) \
		containers/

.PHONY: build run
