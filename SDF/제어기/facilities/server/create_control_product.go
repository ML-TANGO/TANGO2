package server

import (
	"context"

	"github.com/go-pg/pg/v10"
	"gitlab.suredatalab.kr/sdlmicro/middleware/auth"
	"gitlab.suredatalab.kr/sdlmicro/middleware/errors"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"

	"gitlab.suredatalab.kr/beymons/facilities"
)

// CreateControlProduct - 제품 제어 설정 추가 API
func (s FacilitiesServer) CreateControlProduct(ctx context.Context, req *facilities.ProductControl) (*facilities.ProductControl, error) {
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

	if err := checkSensorType(ctx, conn, req.SensorType); err != nil {
		return nil, err
	}

	if err := validatePayload(req.Payload); err != nil {
		return nil, err
	}

	// 제어 설정 등록
	req.UpdatedAt = nil
	if _, err := tx.ModelContext(ctx, req).Returning("control_id").Returning("updated_at").Insert(); err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	// 이력 기록
	if err := writeProductHistory(ctx, conn, origin, facilities.ProductHistory_UPDATED, &History{
		Name:   "control",
		Change: req,
	}); err != nil {
		return nil, err
	}

	// Commit Transaction
	if err = tx.Commit(); err != nil {
		return nil, log.InternalError(ctx, err)
	}

	return req, nil
}

// 센서 타입 확인 함수
func checkSensorType(ctx context.Context, conn *pg.Conn, typeID string) error {
	exists, err := conn.ModelContext(ctx).Table("sensor_types").Where("type_id = ?", typeID).Exists()
	if err != nil {
		return pgorm.GetError(ctx, err)
	}

	if !exists {
		return errors.New(facilities.ErrUnknownType, "type", typeID)
	}
	return nil
}
