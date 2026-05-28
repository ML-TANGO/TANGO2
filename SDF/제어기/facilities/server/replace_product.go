package server

import (
	"context"
	"strings"
	"time"

	"gitlab.suredatalab.kr/sdlmicro/middleware/auth"
	"gitlab.suredatalab.kr/sdlmicro/middleware/errors"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"

	"gitlab.suredatalab.kr/beymons/facilities"
)

// ReplaceProduct - 제품 정보 수정 API
func (s FacilitiesServer) ReplaceProduct(ctx context.Context, req *facilities.Product) (*facilities.Product, error) {
	if req.CreatedAt == nil {
		return nil, errors.New(facilities.ErrMustSetField, "name", "createdAt")
	}

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
		return nil, err
	}

	if !origin.Writable {
		return nil, auth.ErrAccessDenied.Err()
	}

	var changed []*History
	query := tx.ModelContext(ctx, req).WherePK()

	// 변경 확인
	req.ProductName = strings.TrimSpace(req.ProductName)
	if origin.ProductName != req.ProductName {
		query.Column("product_name")
		changed = append(changed, &History{
			Name:   "productName",
			Origin: origin.ProductName,
			Change: req.ProductName,
		})
	}

	if origin.CreatedAt.AsTime().Local().UnixNano() != req.CreatedAt.AsTime().Local().UnixNano() {
		query.Column("created_at")
		changed = append(changed, &History{
			Name:   "createdAt",
			Origin: origin.CreatedAt.AsTime().Format(time.RFC3339Nano),
			Change: req.CreatedAt.AsTime().Format(time.RFC3339Nano),
		})
	}

	// 기본 정보 업데이트
	if len(changed) > 0 {
		if _, err := query.Update(); err != nil {
			return nil, pgorm.GetError(ctx, err)
		}
	}

	updated, err := updateProductAttribute(ctx, tx, req.ManufactureId, req.ModelNumber, origin.Attributes, req.Attributes)
	if err != nil {
		return nil, err
	}

	changed = append(changed, updated...)
	if len(changed) > 0 {
		if err := writeProductHistory(ctx, conn, req, facilities.ProductHistory_UPDATED, changed...); err != nil {
			return nil, err
		}

		// Commit Transaction
		if err = tx.Commit(); err != nil {
			return nil, log.InternalError(ctx, err)
		}

		log.Infof("Product %q %s is updated", origin.ManufactureId, origin.ModelNumber)
	}

	// 반영된 정보 확인
	resp, err := getProduct(ctx, conn, req.ManufactureId, req.ModelNumber)
	if err != nil {
		log.Warn("Failed to load product metadata", "error", err)
		resp = req
	}
	return resp, nil
}
