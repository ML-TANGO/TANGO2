package server

import (
	"context"

	"gitlab.suredatalab.kr/sdlmicro/middleware/auth"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"

	"gitlab.suredatalab.kr/beymons/devices"
)

// DetachDevice - 하위 장치 연결 해제
func (s DevicesServer) DetachDevice(ctx context.Context, req *devices.ChildDeviceRequest) (*devices.DeviceResponse, error) {
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
	query := deviceQuery(ctx, conn).Where("device_id = ?", req.DeviceId)
	if err := query.Select(origin); err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	// 사용자 정보
	claims, err := auth.GetClaim(ctx)
	if err != nil {
		return nil, err
	}

	var history []*devices.DeviceUpdateHistory
	for _, deviceID := range req.Children {
		res, err := tx.ModelContext(ctx, (*devices.DeviceRelation)(nil)).
			Where("parent_id = ?", req.DeviceId).
			Where("child_id = ?", deviceID).
			Delete()
		if err != nil {
			return nil, pgorm.GetError(ctx, err)
		}

		if res.RowsAffected() == 0 {
			continue
		}

		history = append(history, &devices.DeviceUpdateHistory{
			Attribute: "children",
			Origin:    deviceID,
		})

		// 상위 장치 이력 등록
		if err := writeHistory(ctx, tx, deviceID, claims.UserID, devices.DeviceHistory_DETACH, []*devices.DeviceUpdateHistory{
			{
				Attribute: "parent",
				Origin:    req.DeviceId,
			},
		}); err != nil {
			return nil, pgorm.GetError(ctx, err)
		}
	}

	if len(history) == 0 {
		return s.GetDevice(ctx, &devices.DeviceRequest{DeviceId: req.DeviceId})
	}

	// 하위 장치 이력 등록
	if err := writeHistory(ctx, tx, req.DeviceId, claims.UserID, devices.DeviceHistory_DETACH, history); err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	// Commit
	if err := tx.Commit(); err != nil {
		return nil, log.InternalError(ctx, err)
	}

	return s.GetDevice(ctx, &devices.DeviceRequest{DeviceId: req.DeviceId})
}
