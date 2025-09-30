# Use the official Go image as the base image
FROM golang:1.22.4 AS builder

# Set the working directory inside the container
WORKDIR /app

# Copy the server.go file
COPY . .
# Copy the Go module files
#COPY go.mod go.sum ./

# Download the Go module dependencies
RUN go mod download

# Build the Go application
RUN CGO_ENABLED=0 GOOS=linux go build -o /go-poc

FROM scratch

COPY --from=builder /go-poc .

# Expose the port that the server listens on
EXPOSE 8080
EXPOSE 50051

# Run the server when the container starts
ENTRYPOINT ["/go-poc"]