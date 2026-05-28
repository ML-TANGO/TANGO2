package server

import (
	"context"
	"strings"

	"github.com/go-pg/pg/v10"
	"gitlab.suredatalab.kr/sdlmicro/middleware/auth"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"

	"gitlab.suredatalab.kr/beymons/facilities"
)

// UpdateFacility - 설비 정보 변경 API
func (s FacilitiesServer) UpdateFacility(ctx context.Context, req *facilities.UpdateFacilityRequest) (*facilities.Facility, error) {
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

	changed, err := updateFacilityAttribute(ctx, tx, req.FacilityId, origin.Attributes, req.Payload)
	if err != nil {
		return nil, err
	}

	if len(changed) > 0 {
		if err := writeFacilityHistory(ctx, conn, origin, facilities.FacilityHistory_UPDATED, changed...); err != nil {
			return nil, err
		}

		// Commit Transaction
		if err = tx.Commit(); err != nil {
			return nil, log.InternalError(ctx, err)
		}

		log.Infof("Facility %q is updated", req.FacilityId)
	}

	// 반영된 정보 확인
	resp, err := getFacility(ctx, conn, req.FacilityId)
	if err != nil {
		log.Warn("Failed to load facility metadata", "error", err)
		resp = origin
		resp.Attributes = req.Payload
	}
	return resp, nil
}

// 사용자화 메타데이터 수정 함수
func updateFacilityAttribute(ctx context.Context, tx *pg.Tx, id string, origin, changed map[string]string) ([]*History, error) {
	if changed == nil {
		changed = make(map[string]string)
	}
	if origin == nil {
		origin = make(map[string]string)
	}

	var history []*History
	// 사용자화 메타데이터 업데이트
	for k, v := range changed {
		v = strings.TrimSpace(v)
		ov, ok := origin[k]
		switch {
		case ok:
			if len(v) == 0 {
				// 새로운 값이 없으면 삭제 처리
				break
			}

			ov = strings.TrimSpace(ov)
			delete(origin, k)
			if ov == v {
				// 값의 변화가 없으므로 값을 변경하지 않음
				break
			}
			fallthrough
		case !ok:
			if _, err := tx.ModelContext(ctx, &facilities.FacilityAttribute{
				FacilityId: id,
				Attribute:  k,
				Value:      v,
			}).OnConflict("(facility_id, attribute) DO UPDATE").
				Set("value = ?value").
				Set("updated_at = NOW()").Insert(); err != nil {
				return nil, pgorm.GetError(ctx, err)
			}
			history = append(history, &History{
				Name:   k,
				Origin: ov,
				Change: v,
			})
		}
	}

	// 삭제된 메타데이터 제거
	for k, v := range origin {
		if _, err := tx.ModelContext(ctx, (*facilities.FacilityAttribute)(nil)).
			Where("facility_id = ?", id).Where("attribute = ?", k).Delete(); err != nil {
			return nil, pgorm.GetError(ctx, err)
		}
		history = append(history, &History{
			Name:   k,
			Origin: v,
		})
	}

	return history, nil
}
