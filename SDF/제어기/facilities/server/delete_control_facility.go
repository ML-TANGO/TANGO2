package server

import (
	"context"

	"gitlab.suredatalab.kr/sdlmicro/middleware/auth"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"google.golang.org/protobuf/types/known/emptypb"

	"gitlab.suredatalab.kr/beymons/facilities"
)

// DeleteControlFacility - 설비 설정 삭제 API
func (s FacilitiesServer) DeleteControlFacility(ctx context.Context, req *facilities.ControlFacilityRequest) (*emptypb.Empty, error) {
	// DB 연결
	conn := pgorm.Conn()
	defer conn.Close()
	// Transaction
	tx, err := conn.Begin()
	if err != nil {
		return nil, log.InternalError(ctx, err)
	}
	defer tx.Close()

	// 제품 정보 조회
	log.Debug("load facility...")
	facility, err := getFacility(ctx, conn, req.FacilityId)
	if err != nil {
		return nil, err
	}

	// 권한 확인
	if !facility.Writable {
		return nil, auth.ErrAccessDenied.Err()
	}

	// 기존 설정 조회
	var originControl facilities.FacilityControl
	query := controlFacilityQuery(ctx, conn)
	query.Where("facility_id = ?", req.FacilityId)
	query.Where("control_id = ?", req.ControlId)
	if err := query.Select(&originControl); err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	// 제어 설정 삭제
	result, err := conn.ModelContext(ctx, (*facilities.FacilityControl)(nil)).
		Where("facility_id = ?", req.FacilityId).
		Where("control_id = ?", req.ControlId).
		Delete()
	if err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	if result.RowsAffected() > 0 {
		// 이력 기록
		if err := writeFacilityHistory(ctx, conn, facility, facilities.FacilityHistory_UPDATED, &History{
			Name:   "control",
			Origin: &originControl,
		}); err != nil {
			return nil, err
		}

		// Commit Transaction
		if err = tx.Commit(); err != nil {
			return nil, log.InternalError(ctx, err)
		}
	}

	return &emptypb.Empty{}, nil
}
