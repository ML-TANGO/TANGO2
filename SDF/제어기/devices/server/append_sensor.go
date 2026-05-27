package server

import (
	"context"
	"fmt"

	"gitlab.suredatalab.kr/sdlmicro/middleware/auth"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"google.golang.org/protobuf/types/known/emptypb"

	"gitlab.suredatalab.kr/beymons/devices"
)

// AppendSensor - 센서 추가 및 수정 API
func (s DevicesServer) AppendSensor(ctx context.Context, req *devices.Sensor) (*emptypb.Empty, error) {
	// DB 연결
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

	var exists bool
	if len(req.SensorId) > 0 {
		// 등록된 센서 확인
		if exists, err = tx.ModelContext(ctx, req).WherePK().Exists(); err != nil {
			return nil, pgorm.GetError(ctx, err)
		}
	}

	query := tx.ModelContext(ctx, req)
	query.OnConflict("(sensor_id) DO UPDATE")
	query.Set("display_name = EXCLUDED.display_name")
	query.Set("description = EXCLUDED.description")
	res, err := query.Insert()
	if err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	if res.RowsAffected() == 0 {
		return &emptypb.Empty{}, nil
	}

	if !exists {
		// 사용자 정보
		claims, err := auth.GetClaim(ctx)
		if err != nil {
			return nil, err
		}

		history := []*devices.DeviceUpdateHistory{
			{
				Attribute: "sensor",
				Change:    fmt.Sprint(req.ChannelId),
			},
		}

		if err := writeHistory(ctx, tx, req.DeviceId, claims.UserID, devices.DeviceHistory_ATTACH, history); err != nil {
			return nil, pgorm.GetError(ctx, err)
		}
	}

	// Commit
	if err := tx.Commit(); err != nil {
		return nil, log.InternalError(ctx, err)
	}

	log.Infof("Sensor %s of %q is successfully created", req.SensorId, req.DeviceId)
	return &emptypb.Empty{}, nil
}
