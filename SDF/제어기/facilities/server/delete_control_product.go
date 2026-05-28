package server

import (
	"context"

	"gitlab.suredatalab.kr/sdlmicro/middleware/auth"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"google.golang.org/protobuf/types/known/emptypb"

	"gitlab.suredatalab.kr/beymons/facilities"
)

// DeleteControlProduct - 제품 설정 삭제 API
func (s FacilitiesServer) DeleteControlProduct(ctx context.Context, req *facilities.ControlProductRequest) (*emptypb.Empty, error) {
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
	log.Debug("load product...")
	origin, err := getProduct(ctx, conn, req.ManufactureId, req.ModelNumber)
	if err != nil {
		return nil, err
	}

	// 권한 확인
	if !origin.Writable {
		return nil, auth.ErrAccessDenied.Err()
	}

	// 기존 설정 조회
	var originControl facilities.ProductControl
	query := tx.ModelContext(ctx, &originControl)
	query.Where("control_id = ?", req.ControlId)
	query.Where("manufacture_id = ?", req.ManufactureId)
	query.Where("model_number = ?", req.ModelNumber)

	// 제어 설정 삭제
	result, err := query.Delete()
	if err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	if result.RowsAffected() > 0 {
		// 이력 기록
		if err := writeProductHistory(ctx, conn, origin, facilities.ProductHistory_UPDATED, &History{
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
