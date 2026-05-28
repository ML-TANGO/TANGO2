package server

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/go-pg/pg/v10"
	"gitlab.suredatalab.kr/sdlmicro/middleware/async"
	"gitlab.suredatalab.kr/sdlmicro/middleware/auth"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"google.golang.org/protobuf/proto"

	"gitlab.suredatalab.kr/beymons/facilities"
)

// FacilityHistories - 설비 변경 이력 API
func (s FacilitiesServer) FacilityHistories(ctx context.Context, req *facilities.FacilityRequest) (*facilities.FacilityHistoryResponse, error) {
	// DB Connection
	conn := pgorm.Conn()
	defer conn.Close()

	query := conn.Model((*facilities.FacilityHistory)(nil)).Where("facility_id = ?", req.FacilityId)
	query.Column("created_at", "site_id", "facility_id", "action", "created_user_id")
	query.Order("created_at ASC")

	// 사용자 정보
	if pgorm.JoinUserInfo(conn, query, "created_user_id") {
		query.ColumnExpr("TO_JSONB(user_info) created_by")
	} else {
		query.ColumnExpr("JSONB_BUILD_OBJECT('name', created_name) created_by")
	}

	// 변경 이력
	updateQuery := conn.Model((*facilities.FacilityUpdateHistory)(nil))
	updateQuery.Column("created_at", "facility_id")
	updateQuery.ColumnExpr("JSONB_BUILD_OBJECT('origin', origin, 'change', change) AS details")
	updateQuery.Where("facility_id = ?", req.FacilityId)
	query.With("updated", updateQuery).Join("LEFT JOIN updated USING (created_at, facility_id)")
	query.Column("details")

	resp := &facilities.FacilityHistoryResponse{}
	if err := query.ForEach(func(tuple *facilities.FacilityHistory) error {
		resp.Histories = append(resp.Histories, proto.Clone(tuple).(*facilities.FacilityHistory))
		tuple = nil
		return nil
	}); err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	return resp, nil
}

type History struct {
	Name   string
	Origin any
	Change any
}

// 이력 기록 함수
func writeFacilityHistory(ctx context.Context, conn *pg.Conn, origin *facilities.Facility, kind facilities.FacilityHistory_Kind, updated ...*History) error {
	// 인증 정보 조회
	claims, err := auth.GetClaim(ctx)
	if err != nil {
		return err
	}

	history := &facilities.FacilityHistory{
		FacilityId:    origin.FacilityId,
		SiteId:        origin.SiteId,
		Action:        kind,
		CreatedUserId: claims.UserID,
		CreatedName:   claims.Name,
	}
	if _, err := conn.ModelContext(ctx, history).Returning("created_at").Insert(); err != nil {
		return pgorm.GetError(ctx, err)
	}

	rawdata, err := jsonMarshaler.Marshal(origin)
	if err != nil {
		log.Error("Failed to marshal origin data", "error", err)
		return log.InternalError(ctx, err)
	}

	var (
		pushEvent     = true
		eventCode     async.EventType
		status        *facilities.FacilityStatusHistory
		updateHistory = &facilities.FacilityUpdateHistory{
			FacilityId: history.FacilityId,
			CreatedAt:  history.CreatedAt,
			SiteId:     origin.SiteId,
		}
	)
	switch kind {
	case facilities.FacilityHistory_CREATED:
		eventCode = async.Event_create
		updateHistory.Change = string(rawdata)
		status = &facilities.FacilityStatusHistory{
			FacilityId: origin.FacilityId,
			SiteId:     origin.SiteId,
			CreatedAt:  history.CreatedAt,
			Status:     facilities.FacilityStatus_NORMAL,
		}

	case facilities.FacilityHistory_DELETED:
		eventCode = async.Event_delete
		updateHistory.Origin = string(rawdata)
		status = &facilities.FacilityStatusHistory{
			FacilityId: origin.FacilityId,
			SiteId:     origin.SiteId,
			CreatedAt:  history.CreatedAt,
			Status:     facilities.FacilityStatus_DEFUNCT,
		}

	case facilities.FacilityHistory_UPDATED,
		facilities.FacilityHistory_ATTACHED,
		facilities.FacilityHistory_DETACHED:
		// 변경 이력 처리
		eventCode = async.Event_update
		origin := make(map[string]any)
		change := make(map[string]any)
		for _, value := range updated {
			origin[value.Name] = value.Origin
			change[value.Name] = value.Change
		}

		if rawdata, err := json.Marshal(origin); err != nil {
			log.Error("Failed to marshal origin data", "error", err)
		} else {
			updateHistory.Origin = string(rawdata)
		}

		if rawdata, err := json.Marshal(change); err != nil {
			log.Error("Failed to marshal change data", "error", err)
		} else {
			updateHistory.Change = string(rawdata)
		}

	case facilities.FacilityHistory_STATUS:
		status = &facilities.FacilityStatusHistory{
			SiteId:     origin.SiteId,
			FacilityId: origin.FacilityId,
			CreatedAt:  history.CreatedAt,
			Status:     origin.Status,
		}
		updateHistory.Change = fmt.Sprintf(`{"status": %q}`, origin.Status.String())
		if len(updated) > 0 {
			updateHistory.Origin = fmt.Sprintf(`{"status": %q}`, updated[0].Origin.(facilities.FacilityStatus).String())
		}

		fallthrough
	default:
		// 이벤트를 기록하지 않음
		pushEvent = false
	}

	if _, err := conn.ModelContext(ctx, updateHistory).Insert(); err != nil {
		return pgorm.GetError(ctx, err)
	}

	if status != nil {
		if _, err := conn.ModelContext(ctx, status).Insert(); err != nil {
			return pgorm.GetError(ctx, err)
		}
	}

	if pushEvent {
		// 이벤트 기록
		payload, err := proto.Marshal(origin)
		if err != nil {
			log.Error("Failed to marshal deployment", "error", err)
			return err
		}
		if err := async.PushEvent(ctx, eventCode, payload); err != nil {
			log.Error("Failed to push event", "error", err)
		}
	}

	return nil
}
