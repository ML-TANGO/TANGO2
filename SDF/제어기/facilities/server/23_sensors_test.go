package server

import (
	"testing"

	"context"

	"github.com/stretchr/testify/assert"

	"gitlab.suredatalab.kr/beymons/facilities"
)

func TestSensors(t *testing.T) {
	for _, suite := range testFacilitySuite {
		t.Run(suite.FacilityId, func(t *testing.T) {
			for _, dev := range testDevices {
				t.Run(dev.DeviceId, func(t *testing.T) {
					res, err := facilities.Client().Sensors(context.Background(), &facilities.FacilityRequest{
						FacilityId: suite.FacilityId,
					})
					if assert.NoError(t, err) && assert.NotNil(t, res) {
						assert.GreaterOrEqual(t, len(res.Entities), 1)
					}
				})
			}
		})
	}
}
