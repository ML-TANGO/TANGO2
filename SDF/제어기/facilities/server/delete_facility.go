package server

import (
	"context"

	"github.com/go-pg/pg/v10"
	"gitlab.suredatalab.kr/sdlmicro/middleware/auth"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/emptypb"

	"gitlab.suredatalab.kr/beymons/facilities"
)

// DeleteFacility - 설비 제거 API
func (s FacilitiesServer) DeleteFacility(ctx context.Context, req *facilities.FacilityRequest) (*emptypb.Empty, error) {
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
		if codes.NotFound == status.Code(err) {
			return &emptypb.Empty{}, nil
		}
		return nil, err
	}

	if !origin.Writable {
		return nil, auth.ErrAccessDenied.Err()
	}

	if ok, err := deleteFacility(ctx, conn, origin); err != nil {
		return nil, err
	} else if !ok {
		return &emptypb.Empty{}, nil
	}

	if err = tx.Commit(); err != nil {
		return nil, log.InternalError(ctx, err)
	}

	log.Infof("Facility %q is successfully deleted", origin.FacilityId)
	return &emptypb.Empty{}, nil
}

// 설비 삭제 함수
func deleteFacility(ctx context.Context, conn *pg.Conn, origin *facilities.Facility) (ok bool, err error) {
	// 제품 상세 삭제
	if result, err := conn.ModelContext(ctx, (*facilities.Facility)(nil)).
		Where("facility_id = ?", origin.FacilityId).
		Delete(); err != nil {
		return false, pgorm.GetError(ctx, err)
	} else if result.RowsAffected() == 0 {
		return false, nil
	}

	ok = true
	err = writeFacilityHistory(ctx, conn, origin, facilities.FacilityHistory_DELETED)
	return
}
