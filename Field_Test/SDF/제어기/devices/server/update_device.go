package server

import (
	"context"
	"fmt"
	"reflect"
	"strings"

	"gitlab.suredatalab.kr/sdlmicro/middleware/auth"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"gitlab.suredatalab.kr/beymons/devices"
)

var ErrNoChangedValue = status.New(codes.InvalidArgument, "No value to change from existing information")

// UpdateDevice - 장치 정보 변경
func (s DevicesServer) UpdateDevice(ctx context.Context, req *devices.Device) (*devices.Device, error) {
	// DB 연결
	conn := pgorm.Conn()
	defer conn.Close()
	// Transaction
	tx, err := conn.Begin()
	if err != nil {
		return nil, log.InternalError(ctx, err)
	}
	defer tx.Close()

	// 장치 정보 조회
	log.Debugf("load origin %s", req.DeviceId)
	origin := &devices.Device{}
	if err := deviceQuery(ctx, conn).Where("device_id = ?", req.DeviceId).Select(origin); err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	if !origin.Writable {
		return nil, auth.ErrAccessDenied.Err()
	}

	// 변경사항 확인 및 이력 생성
	var changed []*devices.DeviceUpdateHistory
	query := tx.ModelContext(ctx, req).WherePK()
	oldValues := reflect.ValueOf(origin)
	newValues := reflect.ValueOf(req)
	fileType := reflect.TypeOf(devices.Device{})

	// 변경사항 확인
	for _, fieldName := range changeableFields {
		oValue := reflect.Indirect(oldValues).FieldByName(fieldName).Interface()
		nValue := reflect.Indirect(newValues).FieldByName(fieldName).Interface()

		// 변경사항이 있는 경우 이력 생성
		if oValue != nValue {
			if temp, ok := fileType.FieldByName(fieldName); ok {
				for _, name := range strings.Split(temp.Tag.Get("protobuf"), ",") {
					if strings.HasPrefix(name, "name=") {
						columnName := name[5:]
						query.Column(columnName)
						changed = append(changed, &devices.DeviceUpdateHistory{
							Attribute: columnName,
							Origin:    fmt.Sprintf("%v", oValue),
							Change:    fmt.Sprintf("%v", nValue),
						})
					}
				}
			}
		}
	}

	if len(changed) == 0 {
		return nil, ErrNoChangedValue.Err()
	}

	// 기본 정보 업데이트
	res, err := query.Update()
	if err != nil {
		return nil, pgorm.GetError(ctx, err)
	}
	if res.RowsAffected() == 0 {
		return nil, ErrNoChangedValue.Err()
	}

	// 사용자 정보
	claims, err := auth.GetClaim(ctx)
	if err != nil {
		return nil, err
	}

	// 이력 기록
	if err := writeHistory(ctx, tx, req.DeviceId, claims.UserID, devices.DeviceHistory_UPDATE, changed); err != nil {
		return nil, err
	}

	// Commit
	if err := tx.Commit(); err != nil {
		return nil, log.InternalError(ctx, err)
	}

	log.Infof("Device %q is updated", req.DeviceId)

	// 반영 내용 확인
	resp, err := getDevice(ctx, conn, req.DeviceId)
	if err != nil {
		log.Warn("Failed to load device metadata", "error", err)
		return req, nil
	}
	return resp, nil
}

var changeableFields = []string{
	"DisplayName",
	"Description",
}
