package server

import (
	"testing"

	"context"

	"github.com/stretchr/testify/assert"

	"gitlab.suredatalab.kr/beymons/devices"
)

func TestGetCommand(t *testing.T) {
	// TODO: 제어 명령 추가 후 처리
	t.SkipNow()
	for _, suite := range testSuite {
		t.Run(suite.DeviceId, func(t *testing.T) {
			res, err := devices.Client().GetCommand(context.Background(), &devices.GetCommandRequest{})
			assert.NoError(t, err)
			assert.NotNil(t, res)
		})
	}
}
