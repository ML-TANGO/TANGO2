package server

import (
	"context"
	"strings"

	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"

	"gitlab.suredatalab.kr/beymons/facilities"
	"gitlab.suredatalab.kr/beymons/sites"
)

// CreateProduct - 제품 등록 API
func (s FacilitiesServer) CreateProduct(ctx context.Context, req *facilities.Product) (*facilities.Product, error) {
	// DB Connection
	conn := pgorm.Conn()
	defer conn.Close()

	// 사이트 확인
	exists, err := conn.ModelContext(ctx, (*sites.Site)(nil)).Where("site_id = ?", req.ManufactureId).Exists()
	if err != nil {
		return nil, pgorm.GetError(ctx, err)
	}
	if !exists {
		// 제조사로 등록
		site := &sites.Site{SiteId: req.ManufactureId}
		if req.Manufacture != nil {
			if name, ok := req.Manufacture.Fields["siteName"]; ok {
				site.SiteName = name.GetStringValue()
			}
		}
		if _, err := sites.Client().Create(ctx, site); err != nil {
			return nil, err
		}
		log.Infof("Manufacture %q is successfully created", req.ManufactureId)
	}

	// Transaction
	tx, err := conn.Begin()
	if err != nil {
		return nil, log.InternalError(ctx, err)
	}
	defer tx.Close()

	// 제품 등록
	req.ProductName = strings.TrimSpace(req.ProductName)
	if _, err := tx.ModelContext(ctx, req).Returning("created_at").Insert(); err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	// 사용자화 메타데이터 추가
	for k, v := range req.Attributes {
		v = strings.TrimSpace(v)
		if len(v) == 0 {
			continue
		}

		if _, err := tx.ModelContext(ctx, &facilities.ProductAttribute{
			ManufactureId: req.ManufactureId,
			ModelNumber:   req.ModelNumber,
			Attribute:     k,
			Value:         v,
		}).Insert(); err != nil {
			return nil, pgorm.GetError(ctx, err)
		}
	}

	// 이력 생성
	req.Writable = true
	if err := writeProductHistory(ctx, conn, req, facilities.ProductHistory_CREATED); err != nil {
		return nil, err
	}

	// Commit Transaction
	if err = tx.Commit(); err != nil {
		return nil, log.InternalError(ctx, err)
	}

	log.Infof("Product %q %s is successfully created", req.ManufactureId, req.ModelNumber)
	// 반영된 정보 확인
	resp, err := getProduct(ctx, conn, req.ManufactureId, req.ModelNumber)
	if err != nil {
		log.Warn("Failed to load product metadata", "error", err)
		resp = req
	}
	return resp, nil
}
