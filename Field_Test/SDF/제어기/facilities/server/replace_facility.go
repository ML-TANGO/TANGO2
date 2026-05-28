package server

import (
	"context"
	"fmt"
	"reflect"
	"strings"

	"gitlab.suredatalab.kr/sdlmicro/middleware/auth"
	"gitlab.suredatalab.kr/sdlmicro/middleware/errors"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"

	"gitlab.suredatalab.kr/beymons/facilities"
)

// ReplaceFacility 설비 정보 수정
func (s FacilitiesServer) ReplaceFacility(ctx context.Context, req *facilities.Facility) (*facilities.Facility, error) {
	if req.CreatedAt == nil {
		return nil, errors.New(facilities.ErrMustSetField, "name", "createdAt")
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

	// 기존 정보 조회
	log.Debug("load origin model...")
	origin, err := getFacility(ctx, conn, req.FacilityId)
	if err != nil {
		return nil, err
	}

	if !origin.Writable {
		return nil, auth.ErrAccessDenied.Err()
	}

	// 업데이트 항목 확인
	updateQuery := tx.ModelContext(ctx, req).WherePK()
	var changed []*History
	oldValues := reflect.ValueOf(origin)
	newValues := reflect.ValueOf(req)
	fieldType := reflect.TypeOf(facilities.Facility{})
	for _, fieldName := range changeableFacilityFields {
		oValue := reflect.Indirect(oldValues).FieldByName(fieldName).Interface()
		nValue := reflect.Indirect(newValues).FieldByName(fieldName).Interface()

		switch nValue.(type) {
		case string:
			nValue = strings.TrimSpace(nValue.(string))
		}

		if oValue != nValue {
			if temp, ok := fieldType.FieldByName(fieldName); ok {
				var columnName, jsonName string
				for _, name := range strings.Split(temp.Tag.Get("protobuf"), ",") {
					if strings.HasPrefix(name, "name=") {
						columnName = name[5:]
						updateQuery.Column(columnName)
					}
					if strings.HasPrefix(name, "json=") {
						jsonName = name[5:]
					}
				}
				if len(jsonName) == 0 {
					jsonName = columnName
				}
				changed = append(changed, &History{
					Name:   jsonName,
					Origin: fmt.Sprintf("%v", oValue),
					Change: fmt.Sprintf("%v", nValue),
				})
			}
		}
	}

	// 기본 정보 업데이트
	if len(changed) > 0 {
		if _, err := updateQuery.Update(); err != nil {
			return nil, pgorm.GetError(ctx, err)
		}
	}

	updated, err := updateFacilityAttribute(ctx, tx, req.FacilityId, origin.Attributes, req.Attributes)
	if err != nil {
		return nil, err
	}

	changed = append(changed, updated...)
	if len(changed) > 0 {
		if err := writeFacilityHistory(ctx, conn, req, facilities.FacilityHistory_UPDATED, changed...); err != nil {
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
		resp = req
	}
	return resp, nil
}

var changeableFacilityFields = []string{
	"FacilityName",
	"Latitude",
	"Longitude",
	"Altitude",
	"SerialNumber",
	"CreatedAt",
}
