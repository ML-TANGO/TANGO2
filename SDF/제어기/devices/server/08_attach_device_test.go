package server

import (
	"testing"

	"context"
	"fmt"

	"github.com/stretchr/testify/assert"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"gitlab.suredatalab.kr/beymons/devices"
)

var testGatewayID string

func TestAttachDevice(t *testing.T) {
	for _, dev := range testSuite {
		if dev.DeviceRole == devices.DeviceRole_GATEWAY {
			testGatewayID = dev.DeviceId
			break
		}
	}

	ctx := context.Background()

	for _, suite := range testSuite {
		if suite.DeviceRole != devices.DeviceRole_NODE {
			continue
		}

		desc := fmt.Sprintf("%s/children/%s", testGatewayID, suite.DeviceId)

		// 하위 장치 등록
		t.Run(desc, func(t *testing.T) {
			res, err := devices.Client().AttachDevice(ctx, &devices.ChildDeviceRequest{
				DeviceId: testGatewayID,
				Children: []string{suite.DeviceId},
			})
			assert.NoError(t, err)
			assert.NotNil(t, res)
		})

		// 중복 등록
		t.Run(desc, func(t *testing.T) {
			res, err := devices.Client().AttachDevice(ctx, &devices.ChildDeviceRequest{
				DeviceId: testGatewayID,
				Children: []string{suite.DeviceId},
			})
			assert.Nil(t, res)
			if assert.Error(t, err) {
				assert.Equal(t, status.Code(err), codes.AlreadyExists, err.Error())
			}
		})
	}
}
