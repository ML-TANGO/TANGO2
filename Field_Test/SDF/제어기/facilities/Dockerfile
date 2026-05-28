FROM golang:1.24 AS build-env
LABEL stage=build-env
WORKDIR /facilities
COPY . /facilities
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags '-s' --mod=vendor -o build/facilities main/main.go


FROM scratch
COPY --from=build-env /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --from=build-env /facilities/build/facilities /usr/local/bin/
ENV PATH=/usr/local/bin:$PATH
ENV SECURE_MODE=enforce
ENV ZIPKIN_ENDPOINT=http://zipkin:9411/api/v2/spans
ENV LOG_LEVEL=INFO
EXPOSE 50251
ENTRYPOINT ["facilities"]
CMD ["up", "--grpc-port=50251"]
