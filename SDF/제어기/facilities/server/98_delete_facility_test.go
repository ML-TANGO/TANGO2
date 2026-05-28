package server

import (
	"testing"

	"context"

	"github.com/stretchr/testify/assert"

	"gitlab.suredatalab.kr/beymons/facilities"
)

func TestDeleteFacility(t *testing.T) {
	// 삭제
	for _, suite := range testFacilitySuite {
		t.Run(suite.FacilityId, func(t *testing.T) {
			res, err := facilities.Client().DeleteFacility(context.Background(), &facilities.FacilityRequest{
				FacilityId: suite.FacilityId,
			})
			assert.NoError(t, err)
			assert.NotNil(t, res)
		})
	}

	// 재삭제
	for _, suite := range testFacilitySuite {
		t.Run(suite.FacilityId, func(t *testing.T) {
			res, err := facilities.Client().DeleteFacility(context.Background(), &facilities.FacilityRequest{
				FacilityId: suite.FacilityId,
			})
			assert.NoError(t, err)
			assert.NotNil(t, res)
		})
	}
}
