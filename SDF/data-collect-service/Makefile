SHELL        := /bin/bash
GOPATH       := $(shell go env GOPATH)

.PHONY: init clean envoy proto test build doc
default: all

ifndef VERSION
VERSION := $(shell git log -1 --format="%ad-%h" --date format:%Y%m%d)
endif

ifneq (,$(wildcard .env))
include .env
export $(shell sed 's/=.*//' .env)
endif

all: proto envoy doc
	go mod tidy
	go mod vendor

init:
	go get -d gitlab.suredatalab.kr/sdlmicro/middleware
	go mod tidy
	go mod vendor
	buf dep update

clean:
	go run --mod=vendor main/main.go clean

envoy:
	buf build \
	    -o envoy-proxy/proto.pb \
	    --exclude-source-info \
	    --as-file-descriptor-set

proto:
	buf generate
	buf generate --template buf.sdlmicro.yaml

test:
	@rm -rf profile.cov coverage.out coverage.html
	go test -mod=vendor -tags test -cover -covermode=atomic \
	        -coverpkg=$(shell go list ./... | grep -v main | grep -v cmd | tr '\n' ',') \
	        -coverprofile=profile.cov -p 1 -v ./...
	@cat profile.cov | grep -v "pb.go" > coverage.out
	go tool cover -func=coverage.out
	go tool cover -html=coverage.out -o coverage.html
	go vet ./...

build:
	go fmt ./...
	CGO_ENABLED=0 go build --mod=vendor -o build/collects main/main.go

doc:
	buf generate --template buf.doc.yaml
	@cat collects.swagger.json | \
	sed -r 's/([ ]+)("\$$ref":[^\n,]+)([,]?)/\1"allOf": [\n  \1{\2}\n\1]\3/g' | \
	sed -r 's/"version": "version not set"/"version": "${VERSION}"/g'> swagger.json
	@rm -f collects.swagger.json
