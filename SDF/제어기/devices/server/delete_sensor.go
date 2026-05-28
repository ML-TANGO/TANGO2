package server

import (
	"context"
	"fmt"

	"github.com/go-pg/pg/v10"
	"gitlab.suredatalab.kr/sdlmicro/middleware/auth"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"google.golang.org/protobuf/types/known/emptypb"

	"gitlab.suredatalab.kr/beymons/devices"
)

// DeleteSensor - 센서 제거 API
func (s DevicesServer) DeleteSensor(ctx context.Context, req *devices.DeleteSensorRequest) (*emptypb.Empty, error) {
	// DB 연결
	conn := pgorm.Conn()
	defer conn.Close()
	// Transaction
	tx, err := conn.Begin()
	if err != nil {
		return nil, log.InternalError(ctx, err)
	}
	defer tx.Close()

	sensor := &devices.Sensor{}
	res, err := tx.ModelContext(ctx, sensor).
		Where("device_id = ?", req.DeviceId).
		Where("sensor_id = ?", req.SensorId).
		Returning("channel_id").Delete()
	if err != nil {
		if err == pg.ErrNoRows {
			return &emptypb.Empty{}, nil
		}

		return nil, pgorm.GetError(ctx, err)
	}

	if res.RowsAffected() == 0 {
		return &emptypb.Empty{}, nil
	}

	history := []*devices.DeviceUpdateHistory{
		{
			Attribute: "sensor",
			Origin:    fmt.Sprint(sensor.ChannelId),
		},
	}

	// 사용자 정보
	claims, err := auth.GetClaim(ctx)
	if err != nil {
		return nil, err
	}

	if err := writeHistory(ctx, tx, req.DeviceId, claims.UserID, devices.DeviceHistory_DETACH, history); err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	// Commit
	if err := tx.Commit(); err != nil {
		return nil, log.InternalError(ctx, err)
	}

	log.Infof("Sensor %s of %q is successfully deleted", req.SensorId, req.DeviceId)
	return &emptypb.Empty{}, nil
}
