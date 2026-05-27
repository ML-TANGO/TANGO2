package server

import (
	"testing"

	"context"

	"github.com/stretchr/testify/assert"

	"gitlab.suredatalab.kr/beymons/facilities"
)

func TestDeleteControlFacility(t *testing.T) {
	for _, suite := range testFacilitySuite {
		t.Run(suite.FacilityId, func(t *testing.T) {
			// 제어 설정 조회
			list, err := facilities.Client().ControlFacility(context.Background(), &facilities.ControlFacilityRequest{
				FacilityId: suite.FacilityId,
			})
			if !assert.NoError(t, err) && !assert.NotNil(t, list) {
				t.FailNow()
			}

			for _, control := range list.Entities {
				t.Run(control.ControlId, func(t *testing.T) {
					res, err := facilities.Client().DeleteControlFacility(context.Background(), &facilities.ControlFacilityRequest{
						FacilityId: suite.FacilityId,
						ControlId:  control.ControlId,
					})
					assert.NoError(t, err)
					assert.NotNil(t, res)
				})
			}
		})
	}
}
