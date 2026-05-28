package server

import (
	"context"

	"gitlab.suredatalab.kr/sdlmicro/middleware/auth"
	"gitlab.suredatalab.kr/sdlmicro/middleware/errors"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"

	"gitlab.suredatalab.kr/beymons/devices"
	"gitlab.suredatalab.kr/beymons/facilities"
	"gitlab.suredatalab.kr/beymons/sites"
)

// Connect - 설비에 장치 연결
func (s FacilitiesServer) Connect(ctx context.Context, req *facilities.ConnectRequest) (*facilities.SensorsReponse, error) {
	// DB Connection
	conn := pgorm.Conn()
	defer conn.Close()
	// Transaction
	tx, err := conn.Begin()
	if err != nil {
		return nil, log.InternalError(ctx, err)
	}
	defer tx.Close()

	// 기존 정보 조회
	log.Debug("load origin model...")
	origin, err := getFacility(ctx, conn, req.FacilityId)
	if err != nil {
		return nil, err
	}

	if !origin.Writable {
		return nil, auth.ErrAccessDenied.Err()
	}

	var payload []*facilities.FacilityDevice
	for _, dev := range req.Devices {
		// 사이트에 출고된 장치인지 확인
		exists, err := tx.ModelContext(ctx, (*sites.SiteDevice)(nil)).
			Where("site_id = ?", origin.SiteId).
			Where("device_id = ?", dev.DeviceId).Exists()
		if err != nil {
			return nil, pgorm.GetError(ctx, err)
		}

		if !exists {
			return nil, errors.New(facilities.ErrNotExists, "device", dev.DeviceId, "site", origin.SiteId)
		}

		if dev.Modbus == 0 {
			dev.Channel = 0
		} else {
			// 센서가 존재하는지 확인
			exists, err = conn.ModelContext(ctx, (*devices.Sensor)(nil)).
				Where("device_id = ?", dev.DeviceId).
				Where("channel_id = ?", dev.Modbus).Exists()
			if err != nil {
				return nil, pgorm.GetError(ctx, err)
			}

			if !exists {
				return nil, errors.New(facilities.ErrNotExistsSensor, "device", dev.DeviceId, "modbus", dev.Modbus)
			}
		}

		payload = append(payload, &facilities.FacilityDevice{
			SiteId:      origin.SiteId,
			FacilityId:  req.FacilityId,
			DeviceId:    dev.DeviceId,
			Modbus:      dev.Modbus,
			Channel:     dev.Channel,
			Description: dev.Description,
		})
	}

	if _, err := tx.ModelContext(ctx, &payload).Insert(); err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	// 이력 기록
	if err := writeFacilityHistory(ctx, conn, origin, facilities.FacilityHistory_ATTACHED, &History{
		Name:   "devices",
		Change: req.Devices,
	}); err != nil {
		return nil, err
	}

	// Commit Transaction
	if err = tx.Commit(); err != nil {
		return nil, log.InternalError(ctx, err)
	}

	log.Infof("Facility %q is updated", req.FacilityId)

	return s.Sensors(ctx, &facilities.FacilityRequest{FacilityId: req.FacilityId})
}
