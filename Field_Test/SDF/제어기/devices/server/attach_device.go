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

// AttachDevice - 하위 장치 연결 API
func (s DevicesServer) AttachDevice(ctx context.Context, req *devices.ChildDeviceRequest) (*devices.DeviceResponse, error) {
	// DB 연결
	conn := pgorm.Conn()
	defer conn.Close()
	// Transaction
	tx, err := conn.Begin()
	if err != nil {
		return nil, log.InternalError(ctx, err)
	}
	defer tx.Close()

	// 장치 정보 조회
	log.Debugf("load origin %s", req.DeviceId)
	origin := &devices.Device{}
	if err := deviceQuery(ctx, conn).Where("device_id = ?", req.DeviceId).Select(origin); err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	if origin.DeviceRole == devices.DeviceRole_NODE {
		return nil, status.Errorf(codes.InvalidArgument, "Cannot connect a child device to %s", devices.DeviceRole_NODE)
	}

	// 사용자 정보
	claims, err := auth.GetClaim(ctx)
	if err != nil {
		return nil, err
	}

	var history []*devices.DeviceUpdateHistory
	for _, deviceID := range req.Children {
		if _, err := tx.ModelContext(ctx, &devices.DeviceRelation{
			ParentId: req.DeviceId,
			ChildId:  deviceID,
		}).Insert(); err != nil {
			return nil, pgorm.GetError(ctx, err)
		}

		history = append(history, &devices.DeviceUpdateHistory{
			Attribute: "children",
			Change:    deviceID,
		})

		// 상위 장치 이력 등록
		if err := writeHistory(ctx, tx, deviceID, claims.UserID, devices.DeviceHistory_ATTACH, []*devices.DeviceUpdateHistory{
			{
				Attribute: "parent",
				Change:    req.DeviceId,
			},
		}); err != nil {
			return nil, pgorm.GetError(ctx, err)
		}
	}

	// 하위 장치 이력 등록
	if err := writeHistory(ctx, tx, req.DeviceId, claims.UserID, devices.DeviceHistory_ATTACH, history); err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	// Commit
	if err := tx.Commit(); err != nil {
		return nil, log.InternalError(ctx, err)
	}

	return s.GetDevice(ctx, &devices.DeviceRequest{DeviceId: req.DeviceId})
}
