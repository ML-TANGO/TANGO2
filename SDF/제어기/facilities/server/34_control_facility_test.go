package server

import (
	"testing"

	"context"

	"github.com/stretchr/testify/assert"

	"gitlab.suredatalab.kr/beymons/facilities"
)

func TestControlFacility(t *testing.T) {
	for _, suite := range testFacilitySuite {
		t.Run(suite.FacilityId, func(t *testing.T) {
			// 제어 설정 조회
			res, err := facilities.Client().ControlFacility(context.Background(), &facilities.ControlFacilityRequest{
				FacilityId: suite.FacilityId,
			})
			assert.NoError(t, err)
			if assert.NotNil(t, res) {
				assert.GreaterOrEqual(t, len(res.Entities), 1)
				t.Logf("entities: %+v", res.Entities)
			}
		})
	}
}
