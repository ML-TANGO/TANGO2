package server

import (
	"testing"

	"context"
	"time"

	"github.com/go-pg/pg/v10"
	"github.com/stretchr/testify/assert"
	"gitlab.suredatalab.kr/sdlmicro/middleware/async"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/proto"

	"gitlab.suredatalab.kr/beymons/devices"
)

func TestCommand(t *testing.T) {
	testCases := []struct {
		desc     string
		args     *devices.CommandRequest
		expected codes.Code
	}{
		{
			desc:     "잘못된 명령 (unspecified)",
			args:     &devices.CommandRequest{},
			expected: codes.InvalidArgument,
		},
		{
			desc: "잘못된 명령 (payload 오류)",
			args: &devices.CommandRequest{
				Operand: &devices.CommandRequest_Agsmotor{},
			},
			expected: codes.InvalidArgument,
		},
	}

	for _, suite := range testCases {
		t.Run(suite.desc, func(t *testing.T) {
			res, err := devices.Client().Command(context.Background(), suite.args)
			if suite.expected == codes.OK {
				assert.NoError(t, err)
				assert.NotNil(t, res)
			} else if assert.Error(t, err, "Request: %+v", suite.args) {
				assert.Equal(t, suite.expected, status.Code(err), err.Error())
			}
		})
	}

	conn := pgorm.Conn()
	defer conn.Close()

	for _, suite := range testSuite {
		if suite.DeviceRole != devices.DeviceRole_NODE {
			continue
		}

		t.Run(suite.DeviceId, func(t *testing.T) {
			cmd := &devices.Command{
				SiteId:    TEST_SITE_ID,
				GatewayId: testGatewayID,
				Command:   devices.RequestCode_get_time_req.String(),
				Opcode:    &devices.Command_Request{Request: devices.RequestCode_get_time_req},
				Sequence:  uint64(time.Now().UnixMilli()),
				Origin:    `{"command": "get_time_req"}`,
			}

			// 시간 조회 요청
			t.Run(cmd.Command, func(t *testing.T) {
				payload, err := proto.Marshal(cmd)
				assert.NoError(t, err)
				err = async.Push(context.Background(), devices.PACKAGE_NAME, "command", payload)
				assert.NoError(t, err)

				close := make(chan bool, 1)
				go func() {
					// 전송한 명령 확인
					for {
						time.Sleep(time.Second)
						query := conn.Model((*devices.DeviceCommandHistory)(nil))
						query.Where("command = ?", cmd.Command)
						query.Where("device_id = ?", testGatewayID)
						query.Where("sequence = ?", cmd.Sequence)
						query.Order("device_command_history.created_at DESC")
						var resp string
						err := query.Column("response").Limit(1).Select(&resp)
						if err == pg.ErrNoRows {
							continue
						}
						if assert.NoError(t, err) && assert.Greater(t, len(resp), 1) {
							t.Logf("resp: %s", resp)
						}
						break
					}
					close <- true
				}()
				<-close
			})

			// TODO: 사이트 연결 문제로 테스트 불가
			// // 제어 명령
			// addr := uint32(0)
			// for _, sensor := range suite.Sensors {
			// 	if strings.HasPrefix(sensor.SensorType, "test_ags_") {
			// 		addr = sensor.ChannelId
			// 		break
			// 	}
			// }

			// if addr > 0 {
			// 	close := make(chan bool, 1)
			// 	sequence := uint64(time.Now().UnixMilli())
			// 	go testSendResponse(t, sequence, devices.ResponseCode_set_agsmotor_mode_resp, close)
			// 	t.Run(devices.RequestCode_set_agsmotor_mode_req.String(), func(t *testing.T) {
			// 		res, err := devices.Client().Command(context.Background(), &devices.CommandRequest{
			// 			DeviceId: suite.DeviceId,
			// 			Sequence: sequence,
			// 			Operand: &devices.CommandRequest_AgsmotorMode{
			// 				AgsmotorMode: &devices.CommandRequest_AgsMotorMode{
			// 					Address: map[uint32]devices.CommandRequest_AgsMotorMode_Mode{
			// 						addr: devices.CommandRequest_AgsMotorMode_beymons_auto,
			// 					},
			// 				},
			// 			},
			// 		})
			// 		assert.NoError(t, err)
			// 		assert.NotNil(t, res)
			// 	})
			// 	<-close
			// }
		})
	}
}

func testSendResponse(t *testing.T, sequence uint64, command devices.ResponseCode, close chan bool) {
	time.Sleep(time.Second)

	// 응답 전송
	payload, err := proto.Marshal(&devices.Command{
		Command:   command.String(),
		Sequence:  sequence,
		SiteId:    TEST_SITE_ID,
		GatewayId: testGatewayID,
		Opcode:    &devices.Command_Response{Response: command},
	})
	assert.NoError(t, err)

	err = async.Push(context.Background(), devices.PACKAGE_NAME, "command", payload)
	assert.NoError(t, err)
	close <- true
}
