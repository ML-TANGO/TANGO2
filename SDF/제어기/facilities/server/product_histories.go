package server

import (
	"context"
	"encoding/json"

	"github.com/go-pg/pg/v10"
	"gitlab.suredatalab.kr/sdlmicro/middleware/auth"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"google.golang.org/protobuf/proto"

	"gitlab.suredatalab.kr/beymons/facilities"
)

// ProductHistories - 제품 변경 이력 API
func (s FacilitiesServer) ProductHistories(ctx context.Context, req *facilities.ProductRequest) (*facilities.ProductHistoryResponse, error) {
	// DB Connection
	conn := pgorm.Conn()
	defer conn.Close()

	query := conn.Model((*facilities.ProductHistory)(nil)).
		Where("manufacture_id = ?", req.ManufactureId).
		Where("model_number = ?", req.ModelNumber)
	query.Column("created_at", "manufacture_id", "model_number", "action", "created_user_id")
	query.Order("created_at ASC")

	// 사용자 정보
	if pgorm.JoinUserInfo(conn, query, "created_user_id") {
		query.ColumnExpr("TO_JSONB(user_info) created_by")
	} else {
		query.ColumnExpr("JSONB_BUILD_OBJECT('name', created_name) created_by")
	}

	// 변경 이력
	updateQuery := conn.Model((*facilities.ProductUpdateHistory)(nil))
	updateQuery.Column("created_at", "manufacture_id", "model_number")
	updateQuery.ColumnExpr("JSONB_BUILD_OBJECT('origin', origin, 'change', change) AS details")
	updateQuery.Where("manufacture_id = ?", req.ManufactureId)
	updateQuery.Where("model_number = ?", req.ModelNumber)
	query.With("updated", updateQuery).Join("LEFT JOIN updated USING (created_at, manufacture_id, model_number)")
	query.Column("details")

	resp := &facilities.ProductHistoryResponse{}
	if err := query.ForEach(func(tuple *facilities.ProductHistory) error {
		resp.Histories = append(resp.Histories, proto.Clone(tuple).(*facilities.ProductHistory))
		tuple = nil
		return nil
	}); err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	return resp, nil
}

// 이력 기록 함수
func writeProductHistory(ctx context.Context, conn *pg.Conn, origin *facilities.Product, kind facilities.ProductHistory_Kind, updated ...*History) error {
	// 인증 정보 조회
	claims, err := auth.GetClaim(ctx)
	if err != nil {
		return err
	}

	history := &facilities.ProductHistory{
		ManufactureId: origin.ManufactureId,
		ModelNumber:   origin.ModelNumber,
		Action:        kind,
		CreatedUserId: claims.UserID,
		CreatedName:   claims.Name,
	}
	if _, err := conn.ModelContext(ctx, history).Returning("created_at").Insert(); err != nil {
		return pgorm.GetError(ctx, err)
	}

	updateHistory := &facilities.ProductUpdateHistory{
		ManufactureId: history.ManufactureId,
		ModelNumber:   origin.ModelNumber,
		CreatedAt:     history.CreatedAt,
	}
	rawdata, err := jsonMarshaler.Marshal(origin)
	if err != nil {
		log.Error("Failed to marshal origin data", "error", err)
		return log.InternalError(ctx, err)
	}

	switch kind {
	case facilities.ProductHistory_CREATED:
		updateHistory.Change = string(rawdata)
	case facilities.ProductHistory_DELETED:
		updateHistory.Origin = string(rawdata)

	case facilities.ProductHistory_UPDATED:
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
	}

	// 이력 기록
	if _, err := conn.ModelContext(ctx, updateHistory).Insert(); err != nil {
		return pgorm.GetError(ctx, err)
	}

	return nil
}
