package server

import (
	"context"

	"gitlab.suredatalab.kr/sdlmicro/middleware/auth"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"gitlab.suredatalab.kr/beymons/devices"
)

// CreateDevice - 장치 생성
func (s DevicesServer) CreateDevice(ctx context.Context, req *devices.Device) (*devices.Device, error) {
	// 노드에만 센서를 추가할 수 있음
	if len(req.Sensors) > 0 && req.DeviceRole != devices.DeviceRole_NODE && req.DeviceRole != devices.DeviceRole_NODEGATEWAY {
		return nil, status.Errorf(codes.InvalidArgument, "The sensor can only be connected to %s or %s", devices.DeviceRole_NODE, devices.DeviceRole_NODEGATEWAY)
	}

	// DB Connection
	conn := pgorm.Conn()
	defer conn.Close()
	// Transaction
	tx, err := conn.Begin()
	if err != nil {
		return nil, pgorm.GetError(ctx, err)
	}
	defer tx.Close()

	log.Infof("Create device %q (%s)", req.DeviceId, req.DeviceRole)
	if _, err := tx.Model(req).Insert(); err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	// 센서 등록
	for _, sensor := range req.Sensors {
		log.Debugf("channel %d: %s", sensor.ChannelId, sensor.SensorType)
		sensor.SensorId = ""
		sensor.DeviceId = req.DeviceId
		if _, err := tx.Model(sensor).Insert(); err != nil {
			return nil, pgorm.GetError(ctx, err)
		}
	}

	// 사용자 정보
	claims, err := auth.GetClaim(ctx)
	if err != nil {
		return nil, err
	}

	// 이력 기록
	if err := writeHistory(ctx, tx, req.DeviceId, claims.UserID, devices.DeviceHistory_CREATE, nil); err != nil {
		return nil, err
	}

	// Commit
	if err := tx.Commit(); err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	log.Infof("Device %q is successfully created", req.DeviceId)

	// 반영 내용 확인
	resp, err := getDevice(ctx, conn, req.DeviceId)
	if err != nil {
		log.Warn("Failed to load device metadata", "error", err)
		return req, nil
	}
	return resp, nil
}
