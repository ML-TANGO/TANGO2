package devices

import (
	"fmt"
	"reflect"

	"github.com/go-pg/pg/v10/types"
)

func init() {
	// 디바이스 상태
	var deviceStatus DeviceStatus
	types.RegisterAppender(deviceStatus, deviceStatusAppender)
	types.RegisterScanner(deviceStatus, deviceStatusScanner)

	// 디바이스 역할 상태
	var deviceRole DeviceRole
	types.RegisterAppender(deviceRole, deviceRoleAppender)
	types.RegisterScanner(deviceRole, deviceRoleScanner)

	// 디바이스 역할 상태
	var historyKind DeviceHistory_Kind
	types.RegisterAppender(historyKind, historyKindAppender)
	types.RegisterScanner(historyKind, historyKindScanner)

	// 명령 수행 상태
	var commandStatus DeviceCommandHistory_Status
	types.RegisterAppender(commandStatus, commandStatusAppender)
	types.RegisterScanner(commandStatus, commandStatusScanner)
}

// 디바이스 상태를 기록하기 위한 함수
func deviceStatusAppender(in []byte, v reflect.Value, flags int) []byte {
	value := v.Interface().(DeviceStatus)
	return types.AppendString(in, DeviceStatus_name[int32(value)], flags)
}

// 디바이스 상태를 가져오기 위한 함수
func deviceStatusScanner(v reflect.Value, rd types.Reader, n int) error {
	if !v.CanSet() {
		return fmt.Errorf("pg: Scan(nonsettable %s)", v.Type())
	}

	if n <= 0 {
		v.Set(reflect.ValueOf(v.Interface().(DeviceStatus)))
		return nil
	}

	value, err := types.ScanString(rd, n)
	if err != nil {
		return err
	}

	v.Set(reflect.ValueOf(DeviceStatus(DeviceStatus_value[value])))
	return nil
}

// 디바이스 역할을 기록하기 위한 함수
func deviceRoleAppender(in []byte, v reflect.Value, flags int) []byte {
	value := v.Interface().(DeviceRole)
	return types.AppendString(in, DeviceRole_name[int32(value)], flags)
}

// 디바이스 역할을 가져오기 위한 함수
func deviceRoleScanner(v reflect.Value, rd types.Reader, n int) error {
	if !v.CanSet() {
		return fmt.Errorf("pg: Scan(nonsettable %s)", v.Type())
	}

	if n <= 0 {
		v.Set(reflect.ValueOf(v.Interface().(DeviceRole)))
		return nil
	}

	value, err := types.ScanString(rd, n)
	if err != nil {
		return err
	}

	v.Set(reflect.ValueOf(DeviceRole(DeviceRole_value[value])))
	return nil
}

// 이력 구분을 기록하기 위한 함수
func historyKindAppender(in []byte, v reflect.Value, flags int) []byte {
	value := v.Interface().(DeviceHistory_Kind)
	return types.AppendString(in, DeviceHistory_Kind_name[int32(value)], flags)
}

// 이력 구분을 가져오기 위한 함수
func historyKindScanner(v reflect.Value, rd types.Reader, n int) error {
	if !v.CanSet() {
		return fmt.Errorf("pg: Scan(nonsettable %s)", v.Type())
	}

	if n <= 0 {
		v.Set(reflect.ValueOf(v.Interface().(DeviceHistory_Kind)))
		return nil
	}

	value, err := types.ScanString(rd, n)
	if err != nil {
		return err
	}

	v.Set(reflect.ValueOf(DeviceHistory_Kind(DeviceHistory_Kind_value[value])))
	return nil
}

// DeviceCommandHistory_Status
func commandStatusAppender(in []byte, v reflect.Value, flags int) []byte {
	value := v.Interface().(DeviceCommandHistory_Status)
	return types.AppendString(in, DeviceCommandHistory_Status_name[int32(value)], flags)
}

// DeviceCommandHistory_Status
func commandStatusScanner(v reflect.Value, rd types.Reader, n int) error {
	if !v.CanSet() {
		return fmt.Errorf("pg: Scan(nonsettable %s)", v.Type())
	}

	if n <= 0 {
		v.Set(reflect.ValueOf(v.Interface().(DeviceCommandHistory_Status)))
		return nil
	}

	value, err := types.ScanString(rd, n)
	if err != nil {
		return err
	}

	v.Set(reflect.ValueOf(DeviceCommandHistory_Status(DeviceCommandHistory_Status_value[value])))
	return nil
}
