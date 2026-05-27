package server

import (
	"testing"

	"context"
	"fmt"
	"time"

	"github.com/go-pg/pg/v10"
	"github.com/stretchr/testify/assert"
	"gitlab.suredatalab.kr/sdlmicro/middleware/async"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"google.golang.org/protobuf/proto"

	"gitlab.suredatalab.kr/beymons/devices"
	"gitlab.suredatalab.kr/beymons/facilities"
)

func TestCommandFacilityControl(t *testing.T) {
	conn := pgorm.Conn()
	defer conn.Close()

	for _, suite := range testFacilitySuite {
		t.Run(suite.FacilityId, func(t *testing.T) {
			// 제어 설정 조회
			list, err := facilities.Client().ControlFacility(context.Background(), &facilities.ControlFacilityRequest{
				FacilityId: suite.FacilityId,
			})
			assert.NoError(t, err)
			if assert.NotNil(t, list) {
				assert.GreaterOrEqual(t, len(list.Entities), 1)
				t.Logf("entities: %+v", list.Entities)
			}

			for _, control := range list.Entities {
				payload := &facilities.CommandFacilityRequest_Control{
					ControlId:  []string{control.ControlId},
					Attributes: make(map[string]string),
				}

				switch control.Command {
				case "set_agsmotor_operation_req":
					payload.Attributes["ratio"] = "50"
				}

				close := make(chan bool, 1)
				go testSendResponse(t, conn, suite.FacilityId, control, close)
				res, err := facilities.Client().CommandFacility(context.Background(), &facilities.CommandFacilityRequest{
					FacilityId: suite.FacilityId,
					Command: &facilities.CommandFacilityRequest_Control_{
						Control: payload,
					},
				})
				assert.NoError(t, err)
				assert.NotNil(t, res)
				<-close
			}
		})
	}
}

func testSendResponse(t *testing.T, conn *pg.Conn, id string, control *facilities.FacilityControl, close chan bool) {
	time.Sleep(time.Second)

	query := conn.Model((*facilities.FacilityCommandHistory)(nil))
	query.Where("facility_id = ?", id)
	query.Where("control_id = ?", control.ControlId)
	query.Order("created_at DESC")

	var sequence uint64
	err := query.Limit(1).Column("sequence").Select(&sequence)
	assert.NoError(t, err)

	// 응답 전송
	command := devices.RequestMap[devices.RequestCode(devices.RequestCode_value[control.Command])]
	payload, err := proto.Marshal(&devices.Command{
		Command:    command.String(),
		Sequence:   sequence,
		Downstream: false,
		SiteId:     testSiteID,
		GatewayId:  testGateway,
		Opcode:     &devices.Command_Response{Response: command},
		Origin:     fmt.Sprintf(`{"node_id": %q}`, control.DeviceId),
	})
	assert.NoError(t, err)

	t.Logf("Send %s -> %s", control.Command, command.String())
	err = async.Push(context.Background(), "devices", "command", payload)
	assert.NoError(t, err)
	close <- true
}
