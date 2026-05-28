package server

import (
	"context"
	"fmt"
	"strconv"
	"time"

	"gitlab.suredatalab.kr/sdlmicro/middleware/async"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"google.golang.org/genproto/googleapis/rpc/errdetails"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/types/known/anypb"
	"google.golang.org/protobuf/types/known/structpb"

	"gitlab.suredatalab.kr/beymons/devices"
)

const (
	relayInsertStat    = "INSERT INTO relay (site_id, sensor_id, probe, is_closed) SELECT ?, sensor_id, ?, ? FROM sensors WHERE device_id = ? AND channel_id = ?"
	agsmotorInsertStat = "INSERT INTO agsmotor (site_id, sensor_id, probe, mode, action, motor_act) SELECT ?, sensor_id, ?, ?, ?, TRUE FROM sensors WHERE device_id = ? AND channel_id = ?"
)

// Command - 단말 제어 명령 전송
func (s DevicesServer) Command(ctx context.Context, req *devices.CommandRequest) (*structpb.Struct, error) {
	cmd := &devices.Command{
		Downstream: true,
		Sequence:   uint64(time.Now().UnixMilli()),
	}
	if req.Sequence > 0 {
		cmd.Sequence = req.Sequence
	}

	var err error
	switch req.Operand.(type) {
	case *devices.CommandRequest_Configure:
		cmd.Command = devices.RequestCode_set_config_req.String()
		cmd.Opcode = &devices.Command_Request{
			Request: devices.RequestCode_set_config_req,
		}

		if payload := req.GetConfigure(); payload != nil {
			// TODO: 장치 설정 조회

			cmd.Payload, err = anypb.New(&devices.SetConfigRequest{
				Command: devices.RequestCode_set_config_req,
				Seq:     cmd.Sequence,
			})
			cmd.Origin, err = devices.MarshalToString(payload)
		} else {
			err = status.Error(codes.InvalidArgument, "Invalid argument")
		}

	// AGS 개폐기 제어
	case *devices.CommandRequest_Agsmotor:
		cmd.Command = devices.RequestCode_set_agsmotor_req.String()
		cmd.Opcode = &devices.Command_Request{
			Request: devices.RequestCode_set_agsmotor_req,
		}

		if payload := req.GetAgsmotor(); payload != nil {
			relayReq := &structpb.Struct{
				Fields: make(map[string]*structpb.Value),
			}
			relayReq.Fields["node_id"] = structpb.NewStringValue(req.DeviceId)
			for ch, chValue := range payload.Channels {
				var flags uint64
				for i := 0; i < 32; i++ {
					if probe, ok := chValue.Probe[uint32(i+1)]; ok && probe {
						flags |= 0x00000001 << i
					}
				}
				if flags == 0 {
					return nil, status.Errorf(codes.InvalidArgument, "Invalid argument on channel '%d': %+v", ch, chValue)
				}

				body := &structpb.Struct{
					Fields: map[string]*structpb.Value{
						"action":    structpb.NewStringValue(payload.Action.String()),
						"motor_act": structpb.NewStringValue(fmt.Sprintf("0x%08X", flags)),
					},
				}
				if payload.Period > 0 {
					body.Fields["period"] = structpb.NewNumberValue(float64(payload.Period))
				}
				relayReq.Fields[fmt.Sprint(ch)] = structpb.NewStructValue(body)
			}

			var origin []byte
			origin, err = relayReq.MarshalJSON()
			cmd.Origin = string(origin)
		} else {
			err = status.Error(codes.InvalidArgument, "Invalid argument")
		}

	// AGS 개폐기 제어모듈 동작 모드 변경
	case *devices.CommandRequest_AgsmotorMode:
		cmd.Command = devices.RequestCode_set_agsmotor_mode_req.String()
		cmd.Opcode = &devices.Command_Request{
			Request: devices.RequestCode_set_agsmotor_mode_req,
		}

		body := &structpb.Struct{
			Fields: map[string]*structpb.Value{
				"node_id": structpb.NewStringValue(req.DeviceId),
			},
		}

		if payload := req.GetAgsmotorMode(); payload != nil {
			for k, v := range payload.Address {
				body.Fields[fmt.Sprint(k)] = structpb.NewStructValue(&structpb.Struct{
					Fields: map[string]*structpb.Value{
						"mode": structpb.NewStringValue(v.String()),
					},
				})
			}
		} else {
			err = status.Error(codes.InvalidArgument, "Invalid argument")
		}
		var origin []byte
		origin, err = body.MarshalJSON()
		cmd.Origin = string(origin)

	default:
		cmd.Command = req.Command.String()
		cmd.Opcode = &devices.Command_Request{
			Request: devices.RequestCode(devices.RequestCode_value[cmd.Command]),
		}

		// Structpb 타입으로 처리
		if payload := req.GetPayload(); payload != nil && req.Command != devices.CommandRequest_unspecified {
			payload.Fields["node_id"] = structpb.NewStringValue(req.DeviceId)
			var origin []byte
			origin, err = payload.MarshalJSON()
			cmd.Origin = string(origin)
		} else {
			err = status.Error(codes.InvalidArgument, "Invalid argument")
		}
	}

	if err != nil {
		return nil, err
	}

	// DB Connection
	conn := pgorm.Conn()
	defer conn.Close()

	// 사이트 연결 정보
	query := conn.ModelContext(ctx, (*devices.Device)(nil))
	query.Where("device_role = ? OR device_role = ?", devices.DeviceRole_GATEWAY, devices.DeviceRole_NODEGATEWAY)
	query.Join("LEFT JOIN device_relations dr").JoinOn("dr.parent_id = device_id AND dr.child_id = ?", req.DeviceId) // DEPRECATED: 제거 예정
	query.Join("JOIN site_devices USING (device_id)")
	query.Join("JOIN sites USING (site_id)")
	query.Column("sites.application", "site_id")
	if pgorm.ExistTable(conn, "last_received_histories") {
		// 데이터 수신 기록을 활용하여 게이트웨이 확인
		query.Join("LEFT JOIN last_received_histories lrh").JoinOn("gateway_id = device.device_id AND lrh.device_id = ?", req.DeviceId)
		query.ColumnExpr("COALESCE(gateway_id, device.device_id)")
		query.Where("lrh.device_id IS NOT NULL OR dr.child_id IS NOT NULL") // DEPRECATED: dr은 제거 예정
	} else {
		query.Column("device_id")
		query.Where("dr.child_id IS NOT NULL") // DEPRECATED: 제거 예정
	}

	if err := query.Limit(1).Select(&cmd.Kind, &cmd.SiteId, &cmd.GatewayId); err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	// Message -> []byte
	payload, err := proto.Marshal(cmd)
	if err != nil {
		log.Error(err, "action", "devices.Command -> []byte")
	}

	if err := async.Push(ctx, devices.PACKAGE_NAME, "command", payload); err != nil {
		log.Error(err, "action", "async.Push to devices/command")
		return nil, log.InternalError(ctx, err)
	}

	// 명령이 끝나는 것을 기다리지 않음
	if req.NoWait {
		return &structpb.Struct{Fields: make(map[string]*structpb.Value)}, nil
	}

	// 처리 대기
	query = conn.ModelContext(ctx, (*devices.DeviceCommandHistory)(nil))
	query.Column("status", "response", "error")
	query.Where("device_id = ?", cmd.GatewayId)
	query.Where("sequence = ?", cmd.Sequence)

	log.Debugf("Wait for response %s:%d", cmd.Command, cmd.Sequence)
	var (
		ch     = make(chan error)
		res    = &structpb.Struct{}
		errMsg string
	)
	go func() {
		for i := 0; i < 30; i++ {
			var state devices.DeviceCommandHistory_Status
			time.Sleep(time.Millisecond * 500)
			exists, err := query.Exists()
			if err != nil {
				log.Warnf("[%d] Failed to check command: %s", i, err.Error())
				continue
			}

			if !exists {
				continue
			}

			if err := query.Select(&state, res, &errMsg); err != nil {
				log.Errorf("[%d] Failed to check command: %s", i, err.Error())
				return
			}

			switch state {
			// 완료
			case devices.DeviceCommandHistory_SUCCESS:
				ch <- nil
			case devices.DeviceCommandHistory_PROCESSING:
				continue
			case devices.DeviceCommandHistory_UNKNOWN:
				// 잘못된 메시지
				ch <- status.Error(codes.InvalidArgument, "Invalid control command format")
			case devices.DeviceCommandHistory_FALLURE:
				ch <- parseErrorMessage(cmd.GetRequest(), res, errMsg)
			}
			return
		}
		ch <- status.Error(codes.DeadlineExceeded, "response timeout")
	}()

	if err := <-ch; err == nil {
		return parseResponse(cmd.GetRequest(), res)
	} else {
		return nil, err
	}
}

// UI 응답 처리
func parseResponse(cmd devices.RequestCode, res *structpb.Struct) (*structpb.Struct, error) {
	switch cmd {
	case devices.RequestCode_set_agsmotor_req:
		payload := res.AsMap()
		for channel, value := range payload {
			switch channel {
			case "command", "node_id", "seq":
				continue
			}

			probe, ok := value.(map[string]any)
			if !ok {
				log.Warnf("Cannot read probe info of node '%v:%s'. Received: %v", payload["node_id"], channel, probe)
				continue
			}

			motorAct, ok := probe["motor_act"].(string)
			if !ok {
				log.Warnf("Cannot read motor_act of node '%v:%s'. Received: %v", payload["node_id"], channel, probe)
				continue
			}
			delete(probe, "motor_act")

			// 프로브 상태
			closed, err := strconv.ParseUint(motorAct[2:], 16, 64)
			if err != nil {
				log.Warnf("Cannot read motor_act of node '%v:%s'. Received: %v", payload["node_id"], channel, motorAct)
				continue
			}
			for i := 0; i < 64 || closed>>i != 0; i++ {
				if closed>>i&0x00000001 == 1 {
					probe[fmt.Sprint(i+1)] = true
				}
			}

			log.Debugf("%+v", probe)
			if provData, err := structpb.NewStruct(probe); err != nil {
				log.Warn(err)
			} else {
				res.Fields[channel] = structpb.NewStructValue(provData)
			}
		}

		return res, nil
	}

	return res, nil
}

// 에러 메시지 처리
func parseErrorMessage(cmd devices.RequestCode, res *structpb.Struct, message string) error {
	switch cmd {
	case devices.RequestCode_set_agsmotor_operation_req:
		details := &errdetails.PreconditionFailure{}
		for addr, result := range res.Fields {
			if text := result.GetStringValue(); text != "" {
				details.Violations = append(details.Violations, &errdetails.PreconditionFailure_Violation{
					Type:    text,
					Subject: fmt.Sprintf("modbus %s", addr),
				})
			}
		}

		if len(details.GetViolations()) > 0 {
			st := status.New(codes.FailedPrecondition, message)
			st, err := st.WithDetails(details)
			if err != nil {
				log.Warn(err.Error())
			} else {
				return st.Err()
			}
		}
	}

	return status.Error(codes.FailedPrecondition, message)
}
