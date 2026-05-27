package server

import (
	"context"

	"github.com/go-pg/pg/v10"
	"gitlab.suredatalab.kr/sdlmicro/middleware/auth"
	"gitlab.suredatalab.kr/sdlmicro/middleware/errors"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"

	"gitlab.suredatalab.kr/beymons/facilities"
	"gitlab.suredatalab.kr/beymons/sites"
)

// Products - 제품 조회 API
func (s FacilitiesServer) Products(ctx context.Context, req *facilities.ProductRequest) (*facilities.Product, error) {
	// DB Connection
	conn := pgorm.Conn()
	defer conn.Close()

	return getProduct(ctx, conn, req.ManufactureId, req.ModelNumber)
}

// 제품 조회 쿼리
func productQuery(ctx context.Context, conn *pg.Conn, isSearh bool) *pg.Query {
	query := conn.ModelContext(ctx, (*facilities.Product)(nil))
	query.Column("manufacture_id", "model_number", "product_name", "product.created_at")

	// 제조사 정보
	if pgorm.ExistTable(conn, "sites") {
		siteQuery := conn.Model((*sites.Site)(nil))
		siteQuery.Column("site_id")
		siteQuery.ColumnExpr("JSONB_BUILD_OBJECT('id', site_id, 'name', site_name) AS manufacture")
		query.With("site", siteQuery).Join("LEFT JOIN site").JoinOn("site.site_id = manufacture_id")
		query.Column("manufacture")
	} else {
		query.ColumnExpr("JSONB_BUILD_OBJECT('id', manufacture_id) AS manufacture")
	}

	// 사용자화 메타데이터
	if pgorm.ExistTable(conn, "documentations") {
		docQuery := conn.Model().Table("documentations")
		docQuery.Where("kind = ?", facilities.PACKAGE_NAME)
		docQuery.Column("kind", "name", "ratio")

		// 추가 메타데이터
		attributeQuery := conn.Model((*facilities.ProductAttribute)(nil)).Group("manufacture_id", "model_number")
		attributeQuery.Column("manufacture_id", "model_number")
		attributeQuery.ColumnExpr("JSONB_OBJECT(ARRAY_AGG(d.name), ARRAY_AGG(value)) attributes")
		attributeQuery.Join("JOIN documentations d").JoinOn("d.kind = ? AND d.name = product_attribute.attribute", PRODUCT_NAME)
		if isSearh {
			attributeQuery.Where("search IS FALSE")
		}
		query.With("attribute", attributeQuery).Join("LEFT JOIN attribute USING (manufacture_id, model_number)")
		query.Column("attributes")
	}

	// 권한 확인
	if claims, err := auth.GetClaim(ctx); err == nil {
		if claims.IsAdmin() || claims.HasRole("manage-products") {
			query.ColumnExpr("TRUE AS writable")
		} else {
			query.ColumnExpr("FALSE AS writable")
		}
	} else {
		query.Where("product IS NULL")
	}

	return query
}

// 제품 조회
func getProduct(ctx context.Context, conn *pg.Conn, manufactureID, modelNumber string) (*facilities.Product, error) {
	query := productQuery(ctx, conn, false)
	query.Where("manufacture_id = ?", manufactureID).Where("model_number = ?", modelNumber)
	var product facilities.Product
	if err := query.Select(&product); err != nil {
		if err == pg.ErrNoRows {
			return nil, errors.New(facilities.ErrNotFoundProduct, "id", manufactureID, "model", modelNumber)
		}
		return nil, pgorm.GetError(ctx, err)
	}

	return &product, nil
}
