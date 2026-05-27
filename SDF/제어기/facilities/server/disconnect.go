package server

import (
	"context"

	"github.com/go-pg/pg/v10"
	"gitlab.suredatalab.kr/sdlmicro/middleware/auth"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"google.golang.org/protobuf/types/known/emptypb"

	"gitlab.suredatalab.kr/beymons/facilities"
	"gitlab.suredatalab.kr/beymons/sites"
)

// Disconnect - 장치 연결 해제 API
func (s FacilitiesServer) Disconnect(ctx context.Context, req *facilities.DisconnectRequest) (*emptypb.Empty, error) {
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

	// 기존 정보 조회
	var originDevice sites.SiteDevice
	if err := tx.ModelContext(ctx, &originDevice).
		Where("site_id = ?", origin.SiteId).
		Where("device_id = ?", req.DeviceId).Select(); err != nil {
		if err == pg.ErrNoRows {
			return &emptypb.Empty{}, nil
		}
		return nil, pgorm.GetError(ctx, err)
	}

	query := tx.ModelContext(ctx, (*facilities.FacilityDevice)(nil))
	query.Where("site_id = ?", origin.SiteId)
	query.Where("facility_id = ?", origin.FacilityId)
	query.Where("device_id = ?", req.DeviceId)
	if req.Modbus > 0 {
		query.Where("modbus = ?", req.Modbus)
	}
	if req.Channel > 0 {
		query.Where("channel = ?", req.Channel)
	}

	result, err := query.Delete()
	if result.RowsAffected() == 0 {
		return &emptypb.Empty{}, nil
	}

	// 이력 기록
	if err := writeFacilityHistory(ctx, conn, origin, facilities.FacilityHistory_DETACHED, &History{
		Name:   "devices",
		Origin: req,
	}); err != nil {
		return nil, err
	}

	log.Infof("Facility %q is updated", req.FacilityId)

	// Commit Transaction
	if err = tx.Commit(); err != nil {
		return nil, log.InternalError(ctx, err)
	}

	return &emptypb.Empty{}, nil
}
