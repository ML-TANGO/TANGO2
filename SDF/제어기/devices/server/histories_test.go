package server

import (
	"testing"

	"context"

	"github.com/stretchr/testify/assert"

	"gitlab.suredatalab.kr/beymons/devices"
)

func TestHistories(t *testing.T) {
	ctx := context.Background()

	for _, suite := range testSuite {
		t.Run(suite.DeviceId, func(t *testing.T) {
			res, err := devices.Client().Histories(ctx, &devices.DeviceRequest{DeviceId: suite.DeviceId})
			if assert.NoError(t, err) && assert.NotNil(t, res) {
				assert.GreaterOrEqual(t, len(res.Histories), 2)
			}
		})
	}
}
