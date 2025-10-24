package collects

import (
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

var (
	ErrTimeout = status.New(codes.DeadlineExceeded, "Timeout occurred while processing data")
)
