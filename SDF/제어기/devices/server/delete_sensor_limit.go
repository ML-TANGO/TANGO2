package server

import (
	"context"

	"gitlab.suredatalab.kr/sdlmicro/middleware/auth"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"google.golang.org/protobuf/types/known/emptypb"

	"gitlab.suredatalab.kr/beymons/devices"
)

// DeleteSensorLimit - 임계치 해제 API
func (s DevicesServer) DeleteSensorLimit(ctx context.Context, req *devices.DeleteLimitRequest) (*emptypb.Empty, error) {
	// DB Connection
	conn := pgorm.Conn()
	defer conn.Close()
	// Transaction
	tx, err := conn.Begin()
	if err != nil {
		return nil, log.InternalError(ctx, err)
	}
	defer tx.Close()

	// 장치 정보 확인
	log.Debugf("load origin %s", req.DeviceId)
	var origin devices.Device
	if err := deviceQuery(ctx, conn).Where("device_id = ?", req.DeviceId).Select(&origin); err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	// 권한 확인
	if !origin.Writable {
		return nil, auth.ErrAccessDenied.Err()
	}

	// 임계치 설정 제거
	query := tx.ModelContext(ctx, &devices.SensorLimit{
		DeviceId:  req.DeviceId,
		Channel:   req.Channel,
		Attribute: req.Attribute,
	})
	if _, err := query.WherePK().Delete(); err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	// Commit
	if err := tx.Commit(); err != nil {
		return nil, log.InternalError(ctx, err)
	}

	return &emptypb.Empty{}, nil
}
