// gRPC 기반 API
package server

import (
	"gitlab.suredatalab.kr/sdlmicro/middleware/auth"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"google.golang.org/protobuf/encoding/protojson"

	"gitlab.suredatalab.kr/beymons/facilities"
)

var jsonMarshaler = protojson.MarshalOptions{
	UseProtoNames:     true,
	UseEnumNumbers:    false,
	EmitUnpopulated:   false,
	EmitDefaultValues: false,
}

const checkProductDocumentationQuery = `-- documentations에 정의가 되어있는지 확인하는 함수
CREATE OR REPLACE FUNCTION check_product_attribute_name()
RETURNS TRIGGER AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM documentations WHERE kind = ? AND name = NEW.attribute) THEN
        RAISE EXCEPTION 'Invalid name: The attribute name "%" must exist in documentations.', NEW.attribute;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_check_product_attribute_name
BEFORE INSERT OR UPDATE ON product_attributes
FOR EACH ROW
EXECUTE FUNCTION check_product_attribute_name();
`

const checkFacilityDocumentationQuery = `-- documentations에 정의가 되어있는지 확인하는 함수
CREATE OR REPLACE FUNCTION check_facility_attribute_name()
RETURNS TRIGGER AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM documentations WHERE kind = ? AND name = NEW.attribute) THEN
        RAISE EXCEPTION 'Invalid name: The attribute name "%" must exist in documentations.', NEW.attribute;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_check_facility_attribute_name
BEFORE INSERT OR UPDATE ON facility_attributes
FOR EACH ROW
EXECUTE FUNCTION check_facility_attribute_name();
`

type FacilityProvider struct {
	auth.VerifyProvider
}

func (p FacilityProvider) Verify(name string, claims *auth.Claims, payload any) error {
	if claims.IsAdmin() {
		return nil
	}

	// 기본 권한 확인
	result := false
	for _, role := range auth.GetRole(name) {
		if claims.HasRole(role) {
			result = true
		}
	}
	if !result {
		return auth.ErrAccessDenied.Err()
	}

	// DB Connection
	conn := pgorm.Conn()
	defer conn.Close()

	query := conn.Model((*facilities.Facility)(nil))
	query.Join("JOIN site_users USING (site_id)")

	switch name {
	// case "/facilities.Products/SearchProduct":
	// case "/facilities.Products/CreateProduct":
	// case "/facilities.Products/Products":
	// case "/facilities.Products/ProductHistories":
	// case "/facilities.Products/ReplaceProduct":
	// case "/facilities.Products/UpdateProduct":
	// case "/facilities.Products/CommandProduct":
	// case "/facilities.Products/DeleteProduct":

	case "/facilities.Facilities/SearchFacility":
	case "/facilities.Facilities/CreateFacility":
	case "/facilities.Facilities/Facilities":
	case "/facilities.Facilities/FacilityHistories":
	case "/facilities.Facilities/ReplaceFacility":
	case "/facilities.Facilities/UpdateFacility":
	case "/facilities.Facilities/CommandFacility":
	case "/facilities.Facilities/DeleteFacility":

	default:
		// API 내부에서 확인
		return nil
	}

	if exists, err := query.Exists(); err != nil {
		log.Error("Failed to check rbac", "error", err)
	} else if exists {
		return nil
	}
	return auth.ErrAccessDenied.Err()
}
