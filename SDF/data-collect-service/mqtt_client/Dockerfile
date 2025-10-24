FROM golang:1.24 AS build-env
LABEL stage=build-env
WORKDIR /collects/mqtt_client
COPY . /collects
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags '-s' --mod=vendor -o consumer main.go subscribe.go


# FROM scratch
FROM scratch
COPY --from=build-env /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --from=build-env /collects/mqtt_client/consumer /usr/local/bin/
ENV PATH=/usr/local/bin:$PATH
ENV LOG_LEVEL=INFO
ENTRYPOINT ["consumer"]
