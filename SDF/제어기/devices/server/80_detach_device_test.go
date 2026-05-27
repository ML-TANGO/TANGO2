package server

import (
	"testing"

	"context"
	"fmt"

	"github.com/stretchr/testify/assert"

	"gitlab.suredatalab.kr/beymons/devices"
)

func TestDetachDevice(t *testing.T) {
	ctx := context.Background()

	for _, suite := range testSuite {
		if suite.DeviceRole != devices.DeviceRole_NODE {
			continue
		}

		desc := fmt.Sprintf("%s/children/%s", testGatewayID, suite.DeviceId)

		// 하위 장치 해제
		t.Run(desc, func(t *testing.T) {
			res, err := devices.Client().DetachDevice(ctx, &devices.ChildDeviceRequest{
				DeviceId: testGatewayID,
				Children: []string{suite.DeviceId},
			})
			assert.NoError(t, err)
			assert.NotNil(t, res)
		})

		// 중복 해제
		t.Run(desc, func(t *testing.T) {
			res, err := devices.Client().DetachDevice(ctx, &devices.ChildDeviceRequest{
				DeviceId: testGatewayID,
				Children: []string{suite.DeviceId},
			})
			assert.NoError(t, err)
			assert.NotNil(t, res)
		})
	}
}
