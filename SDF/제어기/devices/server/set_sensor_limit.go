package server

import (
	"context"

	"gitlab.suredatalab.kr/sdlmicro/middleware/auth"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"

	"gitlab.suredatalab.kr/beymons/devices"
)

// SetSensorLimit - 임계치 설정 API
func (s DevicesServer) SetSensorLimit(ctx context.Context, req *devices.SetLimitRequest) (*devices.SensorLimit, error) {
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

	// 리밋 설정
	limit := &devices.SensorLimit{
		DeviceId:   req.DeviceId,
		Channel:    req.Channel,
		Attribute:  req.Attribute,
		NormalMin:  req.NormalMin,
		NormalMax:  req.NormalMax,
		CautionMin: req.CautionMin,
		CautionMax: req.CautionMax,
	}
	if err := limit.Set(ctx, conn); err != nil {
		return nil, err
	}

	// Commit
	if err := tx.Commit(); err != nil {
		return nil, log.InternalError(ctx, err)
	}

	return limit, nil
}
