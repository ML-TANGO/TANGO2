package server

import (
	"context"
	"text/template"

	"github.com/go-pg/pg/v10"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"google.golang.org/protobuf/proto"

	"gitlab.suredatalab.kr/beymons/facilities"
)

// ControlFacility - 설비 제어 설정 조회
func (s FacilitiesServer) ControlFacility(ctx context.Context, req *facilities.ControlFacilityRequest) (*facilities.ControlFacilityResponse, error) {
	// DB 연결
	conn := pgorm.Conn()
	defer conn.Close()

	query := controlFacilityQuery(ctx, conn).Where("facility_id = ?", req.FacilityId)
	if len(req.ControlId) > 0 {
		query.Where("control_id = ?", req.ControlId)
	}

	var resp facilities.ControlFacilityResponse
	if err := query.ForEach(func(tuple *facilities.FacilityControl) error {
		// 템플릿 파싱
		tmpl, err := template.New("test").Parse(tuple.Payload)
		if err != nil {
			return err
		}

		tuple.Attributes = findVariables(tmpl.Root)
		tuple.Channels = findChannels(tmpl, tuple.Attributes)
		resp.Entities = append(resp.Entities, proto.Clone(tuple).(*facilities.FacilityControl))
		tuple = nil
		return nil
	}); err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	return &resp, nil
}

// 설비 제어 설정 조회
func getControlFacility(ctx context.Context, conn *pg.Conn, facilityID, controlID string) (*facilities.FacilityControl, error) {
	var tuple facilities.FacilityControl
	query := controlFacilityQuery(ctx, conn).Where("facility_id = ?", facilityID)
	query.Where("control_id = ?", controlID)
	if err := query.Select(&tuple); err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	// 템플릿 파싱
	tmpl, err := template.New("test").Parse(tuple.Payload)
	if err != nil {
		return nil, log.InternalError(ctx, err)
	}

	tuple.Attributes = findVariables(tmpl.Root)
	tuple.Channels = findChannels(tmpl, tuple.Attributes)

	return &tuple, nil
}

// 설비 제어 설정 쿼리
func controlFacilityQuery(ctx context.Context, conn *pg.Conn) *pg.Query {
	// 상속된 설정
	prodQuery := conn.ModelContext(ctx, (*facilities.Facility)(nil))
	prodQuery.Join("JOIN product_controls pc USING (manufacture_id, model_number)")
	prodQuery.Join("LEFT JOIN facility_controls fc").JoinOn("fc.facility_id = facility.facility_id AND p_control_id = pc.control_id")
	prodQuery.Column("fc.control_id", "facility.facility_id", "device_id")
	prodQuery.ColumnExpr("COALESCE(p_control_id, pc.control_id) AS p_control_id")
	prodQuery.ColumnExpr("COALESCE(fc.control_name, pc.control_name) AS control_name")
	prodQuery.ColumnExpr("COALESCE(fc.modbus, pc.modbus) AS modbus")
	prodQuery.ColumnExpr("COALESCE(fc.sensor_type, pc.sensor_type) AS sensor_type")
	prodQuery.ColumnExpr("COALESCE(fc.command, pc.command) AS command")
	prodQuery.ColumnExpr("COALESCE(fc.payload, pc.payload) AS payload")
	prodQuery.Column("fc.updated_at")

	// 장치 고유 설정
	fQuery := conn.Model((*facilities.FacilityControl)(nil))
	fQuery.Column("control_id", "facility_id", "device_id", "p_control_id")
	fQuery.Column("control_name", "modbus", "sensor_type", "command", "payload")
	fQuery.Column("updated_at")
	fQuery.Where("p_control_id IS NULL AND control_id IS NOT NULL")

	query := prodQuery.Union(fQuery).WrapWith("control").Table("control").Column("control.*")

	// 장치 이름 조인
	devQuery := conn.Model((*facilities.Facility)(nil)).Distinct()
	devQuery.Join("JOIN site_devices sd USING (site_id)")
	devQuery.Join("JOIN devices USING (device_id)")
	devQuery.Column("device_id")
	devQuery.ColumnExpr("COALESCE(sd.display_name, devices.display_name) AS device_name")
	query.With("dev", devQuery).Join("LEFT JOIN dev USING (device_id)")
	query.Column("device_id", "device_name")

	// 센서 타입 조인
	query.Join("LEFT JOIN sensor_types").JoinOn("type_id = control.sensor_type")
	query.ColumnExpr("type_name AS sensor_type_name")

	return query
}
