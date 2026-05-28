package server

import (
	"context"

	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/proto"

	"gitlab.suredatalab.kr/beymons/devices"
)

// GetSensorLimit - 임계치 조회 API
func (s DevicesServer) GetSensorLimit(ctx context.Context, req *devices.GetLimitRequest) (*devices.GetLimitResponse, error) {
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

	// 센서 확인
	query := tx.ModelContext(ctx, (*devices.Sensor)(nil))
	query.Where("device_id = ?", req.DeviceId)
	if exists, _ := query.Where("channel_id = ?", req.Channel).Exists(); !exists {
		return nil, status.Errorf(codes.NotFound, "Cannot find device ID %q or channel %d", req.DeviceId, req.Channel)
	}

	// 임계치 조회
	res := &devices.GetLimitResponse{
		Limits: make(map[string]*devices.SensorLimit),
	}
	query = tx.ModelContext(ctx, (*devices.SensorLimit)(nil)).Where("device_id = ?", req.DeviceId)
	query.Where("channel = ?", req.Channel)
	if err := query.ForEach(func(tuple *devices.SensorLimit) error {
		res.Limits[tuple.Attribute] = proto.Clone(tuple).(*devices.SensorLimit)
		return nil
	}); err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	return res, nil
}
