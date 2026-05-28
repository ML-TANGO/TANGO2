package server

import (
	"testing"

	"context"
	"os"

	"github.com/stretchr/testify/assert"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"gitlab.suredatalab.kr/beymons/facilities"
)

func TestFacilities(t *testing.T) {
	for _, suite := range testFacilitySuite {
		t.Run(suite.FacilityId, func(t *testing.T) {
			res, err := facilities.Client().Facilities(context.Background(), &facilities.FacilityRequest{
				FacilityId: suite.FacilityId,
			})
			if assert.NoError(t, err) && assert.NotNil(t, res) {
				validFacility(t, suite, res.Facility)
			}
		})
	}

	// 존재하지 않는 설비
	facilityID := "UUID_000010"
	t.Run(facilityID, func(t *testing.T) {
		_, err := facilities.Client().Facilities(context.Background(), &facilities.FacilityRequest{
			FacilityId: facilityID,
		})
		if assert.Error(t, err) {
			assert.Equal(t, codes.NotFound, status.Code(err))
		}
	})

	os.Setenv("SECURE_MODE", "enable")
	defer os.Setenv("SECURE_MODE", "disable")

	// 인증 테스트
	for _, suite := range testFacilitySuite {
		t.Run(suite.FacilityId, func(t *testing.T) {
			res, err := facilities.Client().Facilities(sa, &facilities.FacilityRequest{
				FacilityId: suite.FacilityId,
			})

			if assert.NoError(t, err) && assert.NotNil(t, res) {
				validFacility(t, suite, res.Facility)
			}
		})
	}

	// 권한 테스트
	os.Setenv("SECURE_MODE", "enforce")
	for _, suite := range testFacilitySuite {
		t.Run(suite.FacilityId, func(t *testing.T) {
			res, err := facilities.Client().Facilities(sa, &facilities.FacilityRequest{
				FacilityId: suite.FacilityId,
			})

			assert.Nil(t, res)
			if assert.Error(t, err) {
				assert.Equal(t, codes.PermissionDenied, status.Code(err))
			}
		})
	}
}
