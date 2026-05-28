package server

import (
	"math/rand"
	"testing"

	"context"
	"fmt"

	"github.com/stretchr/testify/assert"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"

	"gitlab.suredatalab.kr/beymons/facilities"
)

func TestStat(t *testing.T) {
	// DB Connection
	conn := pgorm.Conn()
	defer conn.Close()

	for _, dev := range testDevices {
		for _, sensor := range dev.Sensors {
			if sensor.SensorType != testSensorType {
				continue
			}
			// 온습도 데이터 설정
			_, err := conn.Exec(fmt.Sprintf("INSERT INTO %s (site_id, sensor_id, probe, temp, humi) VALUES (?, ?, ?, ?, ?)", testSensorType), testSiteID, sensor.SensorId, 1, rand.Int31n(40)-10, rand.Int31n(100))
			assert.NoError(t, err)
		}
	}

	for _, suite := range testFacilitySuite {
		t.Run(suite.FacilityId, func(t *testing.T) {
			res, err := facilities.Client().Stat(context.Background(), &facilities.FacilityRequest{
				FacilityId: suite.FacilityId,
			})
			if assert.NoError(t, err) && assert.NotNil(t, res) {
				t.Logf("resp: %+v", res.GetStat())
			}
		})
	}
}
