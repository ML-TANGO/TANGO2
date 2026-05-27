package server

import (
	"testing"

	"context"

	"github.com/stretchr/testify/assert"

	"gitlab.suredatalab.kr/beymons/devices"
)

func TestDeleteType(t *testing.T) {
	ctx := context.Background()

	for _, suite := range testTypeSuite {
		t.Run(suite.TypeId, func(t *testing.T) {
			res, err := devices.Client().DeleteType(ctx, &devices.SensorTypeRequest{TypeId: suite.TypeId})
			assert.NoError(t, err)
			assert.NotNil(t, res)
		})
	}

	// 중복 삭제
	for _, suite := range testTypeSuite {
		t.Run(suite.TypeId, func(t *testing.T) {
			res, err := devices.Client().DeleteType(ctx, &devices.SensorTypeRequest{TypeId: suite.TypeId})
			assert.NoError(t, err)
			assert.NotNil(t, res)
		})
	}
}
