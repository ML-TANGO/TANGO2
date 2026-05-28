package server

import (
	"context"
	"encoding/json"
	"strings"

	"gitlab.suredatalab.kr/sdlmicro/middleware/auth"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"

	"gitlab.suredatalab.kr/beymons/facilities"
)

// FIXME: Description
func (s FacilitiesServer) UpdateControlProduct(ctx context.Context, req *facilities.UpdateControlProductRequest) (*facilities.ProductControl, error) {
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
	product, err := getProduct(ctx, conn, req.ManufactureId, req.ModelNumber)
	if err != nil {
		return nil, err
	}

	// 권한 확인
	if !product.Writable {
		return nil, auth.ErrAccessDenied.Err()
	}

	// 기존 설정 조회
	var originControl facilities.ProductControl
	query := tx.ModelContext(ctx, &originControl)
	query.Where("control_id = ?", req.ControlId)
	query.Where("manufacture_id = ?", req.ManufactureId)
	query.Where("model_number = ?", req.ModelNumber)
	if err := query.Select(); err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	req.SensorType = strings.TrimSpace(req.SensorType)
	req.Command = strings.TrimSpace(req.Command)
	req.Payload = strings.TrimSpace(req.Payload)

	var updated []*History
	if req.SensorType != originControl.SensorType {
		query.Set("sensor_type = ?", req.SensorType)
		updated = append(updated, &History{
			Name:   "sensorType",
			Origin: originControl.SensorType,
		})
	}

	if req.Command != originControl.Command {
		query.Set("command = ?", req.Command)
		updated = append(updated, &History{
			Name:   "command",
			Origin: originControl.SensorType,
		})
	}

	if req.Payload != originControl.Payload {
		if err := validatePayload(req.Payload); err != nil {
			return nil, err
		}

		query.Set("payload = ?", req.Payload)
		updated = append(updated, &History{
			Name:   "payload",
			Origin: originControl.SensorType,
		})
	}

	if len(updated) > 0 {
		query.Set("updated_at = NOW()")
		if _, err := query.Update(); err != nil {
			return nil, pgorm.GetError(ctx, err)
		}

		originValue := make(map[string]any)
		changeValue := make(map[string]any)
		for _, value := range updated {
			originValue[value.Name] = value.Origin
			changeValue[value.Name] = value.Change
		}

		updateHistory := &History{
			Name: "control",
		}

		if rawdata, err := json.Marshal(originValue); err != nil {
			log.Error("Failed to marshal origin data", "error", err)
		} else {
			updateHistory.Origin = string(rawdata)
		}

		if rawdata, err := json.Marshal(changeValue); err != nil {
			log.Error("Failed to marshal change data", "error", err)
		} else {
			updateHistory.Change = string(rawdata)
		}

		// 이력 기록
		if err := writeProductHistory(ctx, conn, product, facilities.ProductHistory_UPDATED, updateHistory); err != nil {
			return nil, err
		}

		// Commit Transaction
		if err = tx.Commit(); err != nil {
			return nil, log.InternalError(ctx, err)
		}
	}

	if err := query.Select(); err != nil {
		log.Warn(err)
	}

	return &originControl, nil
}
