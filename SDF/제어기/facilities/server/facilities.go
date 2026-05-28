package server

import (
	"context"
	"fmt"

	"github.com/go-pg/pg/v10"
	"gitlab.suredatalab.kr/sdlmicro/middleware/auth"
	"gitlab.suredatalab.kr/sdlmicro/middleware/errors"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"

	"gitlab.suredatalab.kr/beymons/facilities"
	"gitlab.suredatalab.kr/beymons/sites"
)

// Facilities - 설비 조회 API
func (s FacilitiesServer) Facilities(ctx context.Context, req *facilities.FacilityRequest) (*facilities.FacilityResponse, error) {
	// DB Connection
	conn := pgorm.Conn()
	defer conn.Close()

	res := &facilities.FacilityResponse{
		Link: make(map[string]string),
	}

	// 설비 정보 조회
	var err error
	res.Facility, err = getFacility(ctx, conn, req.FacilityId)
	if err != nil {
		return nil, err
	}

	// 관련 링크
	res.Link["site"] = fmt.Sprintf("/api/sites/%s", res.Facility.SiteId)
	res.Link["group"] = fmt.Sprintf("/api/sites/%s/groups/%s", res.Facility.SiteId, res.Facility.GroupId)
	res.Link["product"] = fmt.Sprintf("/api/products/%s/%s", res.Facility.ManufactureId, res.Facility.ModelNumber)
	return res, nil
}

// 설비 조회 쿼리
func facilityQuery(ctx context.Context, conn *pg.Conn, isSearh bool) *pg.Query {
	query := conn.ModelContext(ctx, (*facilities.Facility)(nil))
	query.Column("facility_id", "facility_name", "site_id", "group_id")
	query.Column("manufacture_id", "model_number", "serial_number")
	query.Column("status", "facility.created_at")

	// 현장 및 그룹 정보
	existSite := pgorm.ExistTable(conn, "sites")
	if existSite {
		groupQuery := conn.ModelContext(ctx, (*sites.Group)(nil))
		groupQuery.Column("group_id", "site_id", "group_name")
		groupQuery.Join("JOIN sites USING (site_id)")
		groupQuery.Column("latitude", "longitude", "altitude")
		groupQuery.ColumnExpr("JSONB_BUILD_OBJECT('siteName', site_name, 'groupName', group_name, 'location', location) site_group")
		query.With("sg", groupQuery).Join("JOIN sg USING (site_id, group_id)").Column("site_group")
		query.ColumnExpr("COALESCE(facility.latitude, sg.latitude) latitude")
		query.ColumnExpr("COALESCE(facility.longitude, sg.longitude) longitude")
		query.ColumnExpr("COALESCE(facility.altitude, sg.altitude) altitude")
	} else {
		query.Column("latitude", "longitude", "altitude")
	}

	// 제품 정보
	productQuery := conn.ModelContext(ctx, (*facilities.Product)(nil))
	productQuery.Column("manufacture_id", "model_number")
	// 제조사 정보
	if existSite {
		productQuery.Join("JOIN sites").JoinOn("site_id = manufacture_id")
		productQuery.ColumnExpr("JSONB_BUILD_OBJECT('manufacture', site_name, 'productName', product_name, 'createdAt', created_at) product")
		query.With("product", productQuery).Join("LEFT JOIN product USING (manufacture_id, model_number)")
		query.Column("product")
	} else {
		productQuery.ColumnExpr("JSONB_BUILD_OBJECT('productName', product_name, 'createdAt', created_at) product")
	}

	// 사용자화 메타데이터
	if pgorm.ExistTable(conn, "documentations") {
		// 추가 메타데이터
		attributeQuery := conn.Model((*facilities.FacilityAttribute)(nil)).Group("facility_id")
		attributeQuery.Column("facility_id")
		attributeQuery.ColumnExpr("JSONB_OBJECT(ARRAY_AGG(d.name), ARRAY_AGG(value)) attributes")
		attributeQuery.Join("JOIN documentations d").JoinOn("d.kind = ? AND d.name = facility_attribute.attribute", facilities.PACKAGE_NAME)
		if isSearh {
			attributeQuery.Where("search IS FALSE")
		}
		query.With("attribute", attributeQuery).Join("LEFT JOIN attribute USING (facility_id)")
		query.Column("attributes")
	}

	// 권한 확인
	if claims, err := auth.GetClaim(ctx); err == nil {
		if claims.IsAdmin() {
			query.ColumnExpr("TRUE AS writable")
		} else {
			authQuery := conn.Model().Table("site_users")
			authQuery.Where("user_id = ?", claims.UserID)
			authQuery.Column("site_id", "user_id", "role")
			query.With("users", authQuery).Join("JOIN users USING (site_id)")
			query.ColumnExpr("CASE users.role WHEN 'user' THEN FALSE ELSE TRUE END writable")
		}
	} else {
		query.Where("facility_id IS NULL")
	}

	// 측정 정보 (센서)
	relatedQuery := conn.Model((*facilities.FacilityDevice)(nil)).Column("facility_id")
	relatedQuery.ColumnExpr("? AS kind", facilities.Facility_Related_metric)
	relatedQuery.Join("JOIN sensors")
	relatedQuery.JoinOn("facility_device.device_id = sensors.device_id")
	relatedQuery.JoinOn("facility_device.modbus = sensors.channel_id")
	relatedQuery.ColumnExpr("facility_device.device_id AS id")
	relatedQuery.ColumnExpr("COALESCE(facility_device.description, sensors.display_name) AS name")
	relatedQuery.ColumnExpr("'/api/view/' || facility_device.device_id || '/' || modbus AS link")

	// 제어 장치
	controlQuery := conn.Model((*facilities.FacilityControl)(nil)).Column("facility_id")
	controlQuery.ColumnExpr("? AS kind", facilities.Facility_Related_control)
	controlQuery.Join("JOIN site_devices USING (device_id)")
	controlQuery.ColumnExpr("device_id AS id")
	controlQuery.ColumnExpr("display_name AS name")
	controlQuery.ColumnExpr("'/api/view/' || device_id || '/' || modbus AS link")
	relatedQuery.UnionAll(controlQuery.Distinct())

	// 작물 정보
	if pgorm.ExistTable(conn, "subjects") {
		subjectQuery := conn.Model().Table("subject_facilities").Column("facility_id")
		subjectQuery.ColumnExpr("? AS kind", facilities.Facility_Related_subject)
		subjectQuery.Join("JOIN subjects USING (subject_id)")
		subjectQuery.ColumnExpr("subject_id::varchar AS id")
		subjectQuery.ColumnExpr("display_name AS name")
		subjectQuery.ColumnExpr("'/api/subjects/' || subject_id AS link")
		relatedQuery.UnionAll(subjectQuery)
	}

	relatedQuery = relatedQuery.WrapWith("related").Table("related")
	relatedQuery.Group("facility_id").Column("facility_id")
	relatedQuery.ColumnExpr("JSONB_AGG(DISTINCT JSONB_BUILD_OBJECT('kind', kind, 'id', id, 'name', name, 'link', link)) as related")
	query.With("related", relatedQuery).Join("LEFT JOIN related USING (facility_id)").Column("related")
	return query
}

// 설비 조회
func getFacility(ctx context.Context, conn *pg.Conn, facilityID string) (*facilities.Facility, error) {
	query := facilityQuery(ctx, conn, false).Where("facility_id = ?", facilityID)
	var facility facilities.Facility
	if err := query.Select(&facility); err != nil {
		if err == pg.ErrNoRows {
			return nil, errors.New(facilities.ErrNotFoundFacility, "id", facilityID)
		}
		return nil, pgorm.GetError(ctx, err)
	}

	return &facility, nil
}
