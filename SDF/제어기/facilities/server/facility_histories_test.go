package server

import (
	"testing"

	"context"

	"github.com/stretchr/testify/assert"

	"gitlab.suredatalab.kr/beymons/facilities"
)

func TestFacilityHistories(t *testing.T) {
	for _, suite := range testFacilitySuite {
		t.Run(suite.FacilityId, func(t *testing.T) {
			res, err := facilities.Client().FacilityHistories(context.Background(), &facilities.FacilityRequest{
				FacilityId: suite.FacilityId,
			})
			if assert.NoError(t, err) && assert.NotNil(t, res) {
				t.Logf("histories: %+v", res.Histories)
			}
		})
	}
}
