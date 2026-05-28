package server

import (
	"context"
	"encoding/json"

	"github.com/go-pg/pg/v10"
	"gitlab.suredatalab.kr/sdlmicro/middleware/auth"
	"gitlab.suredatalab.kr/sdlmicro/middleware/errors"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"

	"gitlab.suredatalab.kr/beymons/devices"
	"gitlab.suredatalab.kr/beymons/facilities"
)

// SetControlFacility - 설비 제어 설정 API
func (s FacilitiesServer) SetControlFacility(ctx context.Context, req *facilities.SetControlFacilityRequest) (*facilities.FacilityControl, error) {
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
	log.Debug("load facility...")
	facility, err := getFacility(ctx, conn, req.FacilityId)
	if err != nil {
		return nil, err
	}

	if !facility.Writable {
		return nil, auth.ErrAccessDenied.Err()
	}

	var (
		control    facilities.FacilityControl
		updated    []*History
		sensorType string
		modbus     uint32
	)

	control.FacilityId = req.FacilityId
	query := tx.ModelContext(ctx, &control).Returning("updated_at")
	switch req.Payload.(type) {
	// 설비 고유 설정 추가
	case *facilities.SetControlFacilityRequest_Create:
		query.Returning("control_id")
		payload := req.GetCreate()
		control.DeviceId = payload.DeviceId
		control.ControlName = payload.ControlName
		control.Modbus = payload.Modbus
		control.SensorType = payload.SensorType
		control.Command = payload.Command
		control.Payload = payload.Payload
		sensorType = payload.SensorType
		modbus = control.Modbus

		if err := validatePayload(payload.Payload); err != nil {
			return nil, err
		}

		updated = []*History{
			{Name: "deviceId", Change: payload.DeviceId},
			{Name: "controlName", Change: payload.ControlName},
			{Name: "modbus", Change: payload.Modbus},
			{Name: "sensorType", Change: payload.SensorType},
			{Name: "command", Change: payload.Command},
			{Name: "payload", Change: payload.Payload},
		}

	// 설비 제어 설정
	case *facilities.SetControlFacilityRequest_Replace_:
		query.Returning("control_id")
		payload := req.GetReplace()

		// 제품 설정 조회
		var productControl facilities.ProductControl
		if err := tx.ModelContext(ctx, &productControl).
			Where("control_id = ?", payload.PControlId).
			Where("manufacture_id = ?", facility.ManufactureId).
			Where("model_number = ?", facility.ModelNumber).Select(); err != nil {
			if err == pg.ErrNoRows {
				return nil, errors.New(facilities.ErrNotFoundSetting, "id", facility.ManufactureId, "model", facility.ModelNumber)
			}
			return nil, pgorm.GetError(ctx, err)
		}

		control.PControlId = payload.PControlId
		control.DeviceId = payload.DeviceId
		control.ControlName = payload.ControlName
		control.Modbus = payload.Modbus
		control.SensorType = payload.SensorType
		control.Command = payload.Command
		control.Payload = payload.Payload
		sensorType = productControl.SensorType
		modbus = productControl.Modbus

		query.Set("device_id = ?device_id")
		updated = append(updated, &History{
			Name:   "deviceId",
			Change: payload.DeviceId,
		})
		if len(payload.ControlName) > 0 && payload.ControlName != productControl.ControlName {
			query.Set("control_name = ?control_name")
			updated = append(updated, &History{
				Name:   "controlName",
				Origin: productControl.ControlName,
				Change: payload.ControlName,
			})
		}
		if payload.Modbus > 0 && payload.Modbus != productControl.Modbus {
			modbus = payload.Modbus
			query.Set("modbus = ?modbus")
			updated = append(updated, &History{
				Name:   "modbus",
				Origin: productControl.Modbus,
				Change: payload.Modbus,
			})
		}
		if len(payload.SensorType) > 0 && payload.SensorType != productControl.SensorType {
			if err := checkSensorType(ctx, conn, payload.SensorType); err != nil {
				return nil, err
			}

			sensorType = payload.SensorType
			query.Set("sensor_type = ?sensor_type")
			updated = append(updated, &History{
				Name:   "sensorType",
				Origin: productControl.SensorType,
				Change: payload.SensorType,
			})
		}
		if len(payload.Command) > 0 && payload.Command != productControl.Command {
			query.Set("command = ?command")
			updated = append(updated, &History{
				Name:   "command",
				Origin: productControl.Command,
				Change: payload.Command,
			})
		}
		if len(payload.Payload) > 0 && payload.Payload != productControl.Payload {
			if err := validatePayload(payload.Payload); err != nil {
				return nil, err
			}

			query.Set("payload = ?payload")
			updated = append(updated, &History{
				Name:   "payload",
				Origin: productControl.Payload,
				Change: payload.Payload,
			})
		}

	// 설비 제어 설정 수정
	case *facilities.SetControlFacilityRequest_Update:
		control.ControlId = req.ControlId

		query.Set("updated_at = NOW()")
		// 기존 설정 확인
		var origin facilities.FacilityControl
		if err := controlFacilityQuery(ctx, conn).
			Where("facility_id = ?", req.FacilityId).
			Where("control_id = ?", req.ControlId).Select(&origin); err != nil {
			return nil, pgorm.GetError(ctx, err)
		}

		payload := req.GetUpdate()
		control.DeviceId = payload.DeviceId
		control.ControlName = payload.ControlName
		control.Modbus = payload.Modbus
		control.SensorType = payload.SensorType
		control.Command = payload.Command
		control.Payload = payload.Payload
		sensorType = origin.SensorType
		modbus = origin.Modbus

		if payload.DeviceId != origin.DeviceId {
			query.Set("device_id = ?", payload.DeviceId)
			updated = append(updated, &History{
				Name:   "deviceId",
				Origin: origin.DeviceId,
				Change: payload.DeviceId,
			})
		}
		if payload.ControlName != origin.ControlName {
			query.Set("control_name = ?", payload.ControlName)
			updated = append(updated, &History{
				Name:   "controlName",
				Origin: origin.ControlName,
				Change: payload.ControlName,
			})
		}
		if payload.Modbus != origin.Modbus {
			query.Set("modbus = ?", payload.Modbus)
			modbus = payload.Modbus
			updated = append(updated, &History{
				Name:   "modbus",
				Origin: origin.Modbus,
				Change: payload.Modbus,
			})
		}
		if payload.SensorType != origin.SensorType {
			if err := checkSensorType(ctx, conn, payload.SensorType); err != nil {
				return nil, err
			}

			sensorType = payload.SensorType
			query.Set("sensor_type = ?", payload.SensorType)
			updated = append(updated, &History{
				Name:   "sensorType",
				Origin: origin.SensorType,
				Change: payload.SensorType,
			})
		}
		if payload.Command != origin.Command {
			query.Set("command = ?", payload.Command)
			updated = append(updated, &History{
				Name:   "command",
				Origin: origin.Command,
				Change: payload.Command,
			})
		}
		if payload.Payload != origin.Payload {
			if err := validatePayload(payload.Payload); err != nil {
				return nil, err
			}

			query.Set("payload = ?", payload.Payload)
			updated = append(updated, &History{
				Name:   "payload",
				Origin: origin.Payload,
				Change: payload.Payload,
			})
		}
	}

	// 장치 연결 확인
	if err := checkControlDevice(ctx, conn, req.FacilityId, control.DeviceId, sensorType, modbus); err != nil {
		return nil, err
	}

	if len(updated) > 0 {
		if _, err := query.OnConflict("(control_id) DO UPDATE").Insert(); err != nil {
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
		if err := writeFacilityHistory(ctx, conn, facility, facilities.FacilityHistory_UPDATED, updateHistory); err != nil {
			return nil, err
		}

		// Commit Transaction
		if err = tx.Commit(); err != nil {
			return nil, log.InternalError(ctx, err)
		}
	}

	res, err := getControlFacility(ctx, conn, req.FacilityId, control.ControlId)
	if err != nil {
		log.Warn("Failed to load facility control", "error", err)
		res = &control
	}
	return res, nil
}

// 제어 장치인지 확인하는 함수
func checkControlDevice(ctx context.Context, conn *pg.Conn, facilityID, deviceID, typeID string, modbus uint32) error {
	// 현장에 출고된 장치인지 확인
	exists, err := conn.ModelContext(ctx, (*facilities.Facility)(nil)).
		Join("JOIN site_devices USING (site_id)").
		Where("facility_id = ?", facilityID).
		Where("device_id = ?", deviceID).Exists()
	if err != nil {
		return pgorm.GetError(ctx, err)
	}

	if !exists {
		return errors.New(facilities.ErrNotInstalled, "device", deviceID, "facility", facilityID)
	}

	// 센서 타입 확인
	exists, err = conn.ModelContext(ctx, (*devices.Sensor)(nil)).
		Where("device_id = ?", deviceID).
		Where("sensor_type = ?", typeID).
		Where("channel_id = ?", modbus).Exists()
	if err != nil {
		return pgorm.GetError(ctx, err)
	}

	if !exists {
		return errors.New(facilities.ErrNotExistsSensor, "device", deviceID, "modbus", modbus, "type", typeID)
	}

	return nil
}
