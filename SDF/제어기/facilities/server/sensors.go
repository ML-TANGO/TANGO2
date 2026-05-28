package server

import (
	"context"

	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"google.golang.org/protobuf/proto"

	"gitlab.suredatalab.kr/beymons/facilities"
)

// Sensors - 설비에 연결된 센서 목록 조회
func (s FacilitiesServer) Sensors(ctx context.Context, req *facilities.FacilityRequest) (*facilities.SensorsReponse, error) {
	// DB Connection
	conn := pgorm.Conn()
	defer conn.Close()

	devQuery := conn.Model((*facilities.FacilityDevice)(nil))
	devQuery.Where("facility_id = ?", req.FacilityId)
	devQuery.Where("modbus IS NULL AND channel IS NULL")
	devQuery.Column("device_id")
	devQuery.Join("JOIN sensors USING (device_id)")
	devQuery.ColumnExpr("channel_id AS modbus")
	devQuery.ColumnExpr("NULL::smallint AS channel")
	devQuery.Column("sensor_type")
	devQuery.Join("JOIN sensor_types").JoinOn("type_id = sensor_type")
	devQuery.ColumnExpr("type_name AS sensor_type_name")
	devQuery.ColumnExpr("COALESCE(facility_device.description, sensors.description) AS description")

	addrQuery := conn.Model((*facilities.FacilityDevice)(nil))
	addrQuery.Where("facility_id = ?", req.FacilityId)
	addrQuery.Where("channel IS NULL")
	addrQuery.Column("facility_device.device_id", "modbus")
	addrQuery.ColumnExpr("NULL::smallint AS channel")
	addrQuery.Join("JOIN sensors").JoinOn("sensors.device_id = facility_device.device_id AND channel_id = modbus")
	addrQuery.Column("sensor_type")
	addrQuery.Join("JOIN sensor_types").JoinOn("type_id = sensor_type")
	addrQuery.ColumnExpr("type_name AS sensor_type_name")
	addrQuery.ColumnExpr("COALESCE(facility_device.description, sensors.description) AS description")

	chQuery := conn.Model((*facilities.FacilityDevice)(nil))
	chQuery.Where("facility_id = ?", req.FacilityId)
	chQuery.Where("channel IS NOT NULL")
	chQuery.Column("facility_device.device_id", "modbus", "channel")
	chQuery.Join("JOIN sensors").JoinOn("sensors.device_id = facility_device.device_id AND channel_id = modbus")
	chQuery.Column("sensor_type")
	chQuery.Join("JOIN sensor_types").JoinOn("type_id = sensor_type")
	chQuery.ColumnExpr("type_name AS sensor_type_name")
	chQuery.ColumnExpr("COALESCE(facility_device.description, sensors.description) AS description")

	var resp facilities.SensorsReponse
	if err := devQuery.Union(addrQuery).Union(chQuery).ForEach(func(tuple *facilities.SensorsReponse_Sensor) error {
		resp.Entities = append(resp.Entities, proto.Clone(tuple).(*facilities.SensorsReponse_Sensor))
		tuple = nil
		return nil
	}); err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	return &resp, nil
}
