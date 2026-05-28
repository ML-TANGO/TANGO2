package server

import (
	"context"
	"strings"

	"gitlab.suredatalab.kr/sdlmicro/middleware/auth"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"gitlab.suredatalab.kr/beymons/facilities"
	"gitlab.suredatalab.kr/beymons/sites"
)

// CreateFacility - 설비 등록 API
func (s FacilitiesServer) CreateFacility(ctx context.Context, req *facilities.Facility) (*facilities.Facility, error) {
	// 설비 그룹 조회
	result, err := sites.Client().Groups(ctx, &sites.GroupRequest{SiteId: req.SiteId, GroupId: req.GroupId})
	if err != nil {
		return nil, err
	}

	if !result.Group.Writable {
		return nil, auth.ErrAccessDenied.Err()
	}

	// DB Connection
	conn := pgorm.Conn()
	defer conn.Close()
	// Transaction
	tx, err := conn.Begin()
	if err != nil {
		return nil, log.InternalError(ctx, err)
	}
	defer tx.Close()

	// 제품 정보 확인
	exists, err := tx.ModelContext(ctx, (*facilities.Product)(nil)).
		Where("manufacture_id = ?", req.ManufactureId).
		Where("model_number = ?", req.ModelNumber).Exists()
	if err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	if !exists {
		return nil, status.Errorf(codes.NotFound, "Cannot find product %s %s", req.ManufactureId, req.ModelNumber)
	}

	// Facility 생성
	req.FacilityId = ""
	req.Status = facilities.FacilityStatus_NORMAL
	req.FacilityName = strings.TrimSpace(req.FacilityName)
	if _, err := tx.ModelContext(ctx, req).Returning("facility_id").Returning("created_at").Insert(); err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	// 사용자화 메타데이터 추가
	for k, v := range req.Attributes {
		v = strings.TrimSpace(v)
		if len(v) == 0 {
			continue
		}

		if _, err := tx.ModelContext(ctx, &facilities.FacilityAttribute{
			FacilityId: req.FacilityId,
			Attribute:  k,
			Value:      v,
		}).Insert(); err != nil {
			return nil, pgorm.GetError(ctx, err)
		}
	}

	// FacilityHistory 생성
	req.Writable = true
	if err := writeFacilityHistory(ctx, conn, req, facilities.FacilityHistory_CREATED); err != nil {
		return nil, err
	}

	// Commit Transaction
	if err = tx.Commit(); err != nil {
		return nil, log.InternalError(ctx, err)
	}

	log.Infof("Facility %q is successfully created", req.FacilityId)
	// 반영된 정보 확인
	resp, err := getFacility(ctx, conn, req.FacilityId)
	if err != nil {
		log.Warn("Failed to load facility metadata", "error", err)
		resp = req
	}
	return resp, nil
}
