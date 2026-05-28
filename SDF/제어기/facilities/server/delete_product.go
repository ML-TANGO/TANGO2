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

// DeleteProduct - 제품 삭제 API
func (s FacilitiesServer) DeleteProduct(ctx context.Context, req *facilities.ProductRequest) (*emptypb.Empty, error) {
	// DB 연결
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
	origin, err := getProduct(ctx, conn, req.ManufactureId, req.ModelNumber)
	if err != nil {
		if codes.NotFound == status.Code(err) {
			return &emptypb.Empty{}, nil
		}
		return nil, err
	}

	if !origin.Writable {
		return nil, auth.ErrAccessDenied.Err()
	}

	if ok, err := deleteProduct(ctx, conn, origin); err != nil {
		return nil, err
	} else if !ok {
		return &emptypb.Empty{}, nil
	}

	if err = tx.Commit(); err != nil {
		return nil, log.InternalError(ctx, err)
	}

	log.Infof("Product %q %s is successfully deleted", origin.ManufactureId, origin.ModelNumber)
	return &emptypb.Empty{}, nil
}

// 제품 삭제 함수
func deleteProduct(ctx context.Context, conn *pg.Conn, origin *facilities.Product) (ok bool, err error) {
	// 제품 상세 삭제
	if result, err := conn.ModelContext(ctx, (*facilities.Product)(nil)).
		Where("manufacture_id = ?", origin.ManufactureId).
		Where("model_number = ?", origin.ModelNumber).
		Delete(); err != nil {
		return false, pgorm.GetError(ctx, err)
	} else if result.RowsAffected() == 0 {
		return false, nil
	}

	ok = true
	err = writeProductHistory(ctx, conn, origin, facilities.ProductHistory_DELETED)
	return
}
