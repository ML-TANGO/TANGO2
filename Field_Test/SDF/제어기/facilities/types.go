package facilities

import (
	"fmt"
	"reflect"

	"github.com/go-pg/pg/v10/types"
)

func init() {
	var productHistoryKind ProductHistory_Kind
	types.RegisterAppender(productHistoryKind, ProductHistoryKindAppender)
	types.RegisterScanner(productHistoryKind, ProductHistoryKindScanner)

	var facilityHistoryKind FacilityHistory_Kind
	types.RegisterAppender(facilityHistoryKind, FacilityHistoryKindAppender)
	types.RegisterScanner(facilityHistoryKind, FacilityHistoryKindScanner)

	var facilityStatus FacilityStatus
	types.RegisterAppender(facilityStatus, FacilityStatusAppender)
	types.RegisterScanner(facilityStatus, FacilityStatusScanner)
}

// ProductHistory_Kind 타입을 기록하기 위한 함수
func ProductHistoryKindAppender(in []byte, v reflect.Value, flags int) []byte {
	value := v.Interface().(ProductHistory_Kind)
	return types.AppendString(in, ProductHistory_Kind_name[int32(value)], flags)
}

// ProductHistory_Kind 타입을 가져오기 위한 함수
func ProductHistoryKindScanner(v reflect.Value, rd types.Reader, n int) error {
	if !v.CanSet() {
		return fmt.Errorf("pg: Scan(nonsettable %s)", v.Type())
	}

	if n <= 0 {
		v.Set(reflect.ValueOf(v.Interface().(ProductHistory_Kind)))
		return nil
	}

	value, err := types.ScanString(rd, n)
	if err != nil {
		return err
	}

	v.Set(reflect.ValueOf(ProductHistory_Kind(ProductHistory_Kind_value[value])))
	return nil
}

// FacilityHistory_Kind 타입을 기록하기 위한 함수
func FacilityHistoryKindAppender(in []byte, v reflect.Value, flags int) []byte {
	value := v.Interface().(FacilityHistory_Kind)
	return types.AppendString(in, FacilityHistory_Kind_name[int32(value)], flags)
}

// FacilityHistory_Kind 타입을 가져오기 위한 함수
func FacilityHistoryKindScanner(v reflect.Value, rd types.Reader, n int) error {
	if !v.CanSet() {
		return fmt.Errorf("pg: Scan(nonsettable %s)", v.Type())
	}

	if n <= 0 {
		v.Set(reflect.ValueOf(v.Interface().(FacilityHistory_Kind)))
		return nil
	}

	value, err := types.ScanString(rd, n)
	if err != nil {
		return err
	}

	v.Set(reflect.ValueOf(FacilityHistory_Kind(FacilityHistory_Kind_value[value])))
	return nil
}

// FacilityStatus 타입을 기록하기 위한 함수
func FacilityStatusAppender(in []byte, v reflect.Value, flags int) []byte {
	value := v.Interface().(FacilityStatus)
	return types.AppendString(in, FacilityStatus_name[int32(value)], flags)
}

// FacilityStatus 타입을 가져오기 위한 함수
func FacilityStatusScanner(v reflect.Value, rd types.Reader, n int) error {
	if !v.CanSet() {
		return fmt.Errorf("pg: Scan(nonsettable %s)", v.Type())
	}

	if n <= 0 {
		v.Set(reflect.ValueOf(v.Interface().(FacilityStatus)))
		return nil
	}

	value, err := types.ScanString(rd, n)
	if err != nil {
		return err
	}

	v.Set(reflect.ValueOf(FacilityStatus(FacilityStatus_value[value])))
	return nil
}
