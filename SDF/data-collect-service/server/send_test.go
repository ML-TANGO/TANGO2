package server

import (
	"context"
	"testing"
	"time"

	"fmt"

	"github.com/stretchr/testify/assert"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"google.golang.org/protobuf/types/known/structpb"

	"gitlab.suredatalab.kr/beymons/collects"
)

func TestSend(t *testing.T) {
	testCases := []struct {
		desc string
		args string
	}{
		{
			desc: "데이터 전송",
			args: fmt.Sprintf(`{
  "data": [
    {
      "node_id": %q,
      "1": [
        {
        	"invalid": true,
          "1": {
            "temp": 39.2
          },
          "2": {
            "temp": 51
          }
        }
      ],
      "2": [
        {
        	"ts": %d,
        	"sampling_rate": 1000,
          "1": {
            "temp": [39.2, 39]
          },
          "2": {
            "temp": [51.3, 51]
          }
        }
      ],
      "rssi": [
          {
              "device": %q,
              "rssi": -50
          },
          {
              "device": "02",
              "rssi": -50
          }
      ]
    }
  ]
}`, testNodeID, time.Now().UnixMilli(), testNodeID[len(testNodeID)-2:]),
		},
	}

	// DB Connection
	conn := pgorm.Conn()
	defer conn.Close()

	// 데이터 전송
	for _, tc := range testCases {
		t.Run(tc.desc, func(t *testing.T) {
			req := &collects.ReceiveData{
				SiteId:    "sdl",
				GatewayId: testGwID,
				Size:      uint32(len(tc.args)),
				Data:      &structpb.Struct{},
			}

			err := req.Data.UnmarshalJSON([]byte(tc.args))
			if !assert.NoError(t, err) {
				t.FailNow()
			}

			// 전송 테스트
			res, err := collects.Client().Send(context.Background(), req)
			assert.NoError(t, err)
			assert.NotNil(t, res)

			// 데이터 추가 확인
			ch := make(chan bool)
			go func() {
				var count int
				for i := 0; count == 0 && i < 10; i++ {
					time.Sleep(time.Millisecond * 500)
					count, err = conn.Model().Table(testSensorType).Where("site_id = ?", req.SiteId).Count()
					assert.NoError(t, err)
				}
				ch <- assert.GreaterOrEqual(t, count, 2)
			}()

			<-ch
			// 처리 이력 확인
			var stat collects.ReceiveHistory
			err = conn.Model(&stat).
				Where("site_id = ?", req.SiteId).
				Where("gateway_id = ?", req.GatewayId).
				Order("received_at").Limit(1).Select()
			if assert.NoError(t, err) {
				assert.Greater(t, stat.Nodes, uint32(0))
				assert.Greater(t, stat.Sensors, uint32(0))
				assert.Greater(t, stat.Recorded, uint32(0))
			}
		})
	}
}
