package server

import (
	"testing"

	"github.com/stretchr/testify/assert"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"

	"gitlab.suredatalab.kr/beymons/devices"
)

func TestCheckDisconnected(t *testing.T) {
	CheckDisconnected()
}

func TestChangeDeviceStatus(t *testing.T) {
	// DB Connection
	conn := pgorm.Conn()
	defer conn.Close()
	// Transaction
	tx, err := conn.Begin()
	if !assert.NoError(t, err) {
		t.Fail()
	}
	defer tx.Close()

	assert.NoError(t, changeDeviceStatus(tx, testNodeID, 1, devices.DeviceStatus_CAUTION))
}
