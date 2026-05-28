package facilities

import (
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

var (
	ErrNotFoundFacility = status.New(codes.NotFound, "Cannot find the specified subject {{.id}}")
	ErrNotFoundProduct  = status.New(codes.NotFound, "Cannot find a product with manufacturer {{.id}} and model number {{.model}}")
	ErrNotFoundSetting  = status.New(codes.NotFound, "No control settings is configured for this product {{.id}}:{{.model}}")
	ErrNotExists        = status.New(codes.NotFound, "Device {{.device}} is not exists or has not been install to site {{.site}}")
	ErrNotInstalled     = status.New(codes.NotFound, "Non-existent device {{.device}} in facility {{.facility}}")
	ErrNotExistsSensor  = status.New(codes.NotFound, "Non-existent modbus address {{.modbus}} on the device {{.device}}")
	ErrUnknownType      = status.New(codes.InvalidArgument, "Unsupported sensor type {{.type}}")
	ErrMustSetField     = status.New(codes.InvalidArgument, "'{{.name}}' value must not be empty")
	ErrCmdNotMatch      = status.New(codes.InvalidArgument, "The commands included in the request cannot be processed together")
	ErrNoData           = status.New(codes.NotFound, "There is no collected data for the requested attribute {{.attribute}}")
	ErrControlUnknown   = status.New(codes.Aborted, "An unexpected internal error occurred during device control.")
)
