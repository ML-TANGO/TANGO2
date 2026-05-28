package server

import (
	"context"
	"fmt"

	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"google.golang.org/protobuf/types/known/emptypb"

	"gitlab.suredatalab.kr/beymons/devices"
)

// DeleteType - 센서 타입 삭제
func (s DevicesServer) DeleteType(ctx context.Context, req *devices.SensorTypeRequest) (*emptypb.Empty, error) {
	// DB Connection
	conn := pgorm.Conn()
	defer conn.Close()
	// Transaction
	tx, err := conn.Begin()
	if err != nil {
		return nil, log.InternalError(ctx, err)
	}
	defer tx.Close()

	res, err := tx.ModelContext(ctx, (*devices.SensorTypeAttribute)(nil)).Where("type_id = ?", req.TypeId).Delete()
	if err != nil {
		return nil, pgorm.GetError(ctx, err)
	}
	log.Debugf("Delete attributes (%d) of %q", res.RowsAffected(), req.TypeId)

	log.Infof("Delete sensor type %q", req.TypeId)
	res, err = tx.ModelContext(ctx, (*devices.SensorType)(nil)).Where("type_id = ?", req.TypeId).Delete()
	if err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	if res.RowsAffected() > 0 {
		res, err = tx.ExecContext(ctx, fmt.Sprintf("DROP TABLE IF EXISTS %q", req.TypeId))
	}

	// Commit
	if err := tx.Commit(); err != nil {
		return nil, log.InternalError(ctx, err)
	}

	return &emptypb.Empty{}, nil
}
