package server

import (
	"context"
	"fmt"
	"os"
	"strconv"
	"strings"

	"github.com/go-pg/pg/v10"
	"github.com/nats-io/nats.go/jetstream"
	"gitlab.suredatalab.kr/sdlmicro/middleware/async"
	"gitlab.suredatalab.kr/sdlmicro/middleware/auth"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/types/known/structpb"

	"gitlab.suredatalab.kr/beymons/common/mqtt"
	"gitlab.suredatalab.kr/beymons/devices"
)

// MQTT 클라이언트를 생성하는 함수
func connectBroker(clientID string) (*mqtt.MqttClient, error) {
	insecure := false
	if os.Getenv("MQTT_INSECURE") == "yes" {
		insecure = true
	}

	mqttConn := &mqtt.MqttClient{
		ClientId: clientID,
	}
	log.Infof("new TLS config for MQTT Client")
	err := mqttConn.SetTLSConfig(os.Getenv("MQTT_ROOT_CA_FILE"), os.Getenv("MQTT_CERT_FILE"), os.Getenv("MQTT_PRIVATE_KEY_FILE"), insecure)
	if err != nil {
		log.Error(err)
		return nil, err
	}

	mqttConn.Endpoint = os.Getenv("MQTT_ENDPOINT")
	if len(mqttConn.Endpoint) == 0 {
		mqttConn.Endpoint = "mqtt://localhost:1883"
	}

	log.Infof("MQTT Client ID: %s", mqttConn.ClientId)
	if err := mqttConn.Connect(nil); err != nil {
		return nil, err
	}

	return mqttConn, nil
}

// DeviceConsumer 함수는 서버와 장치간 명령을 처리하기 위한 컨슈머를 실행한다.
func DeviceConsumer(close chan bool) {
	clientID, err := os.Hostname()
	if err != nil {
		log.Warnf("Cannot get hostname: %s", err.Error())
		clientID = "device-client"
	}

	mqttConn, err := connectBroker(clientID)
	if err != nil {
		log.Fatalf("Failed to connect MQTT broker: %s", err.Error())
	}

	// Consumer 시작
	cc, err := async.Consume(devices.PACKAGE_NAME, "command", 0, func(ctx context.Context, msg jetstream.Msg) {
		cmd := &devices.Command{}
		if err := proto.Unmarshal(msg.Data(), cmd); err != nil {
			log.Error(err, "action", "[]byte -> devices.Command")
			msg.Nak()
			return
		}

		msg.InProgress()

		history := &devices.DeviceCommandHistory{
			Command:  cmd.Command,
			Sequence: cmd.Sequence,
			DeviceId: cmd.GatewayId,
			Payload:  cmd.Origin,
		}

		if cmd.Downstream {
			history.Direction = devices.DeviceCommandHistory_downstream
		}

		// DB Connection
		conn := pgorm.Conn()
		defer conn.Close()

		switch cmd.Opcode.(type) {
		case *devices.Command_Request:
			// 이력 기록
			query := conn.Model(history)
			query.Where("device_id = ?device_id")
			query.Where("command = ?command")
			query.Where("sequence = ?sequence")
			query.Where("status = ?", devices.DeviceCommandHistory_PROCESSING)
			if _, err := query.Clone().Column("created_at").Limit(1).Order("created_at DESC").
				Returning("created_at").SelectOrInsert(); err != nil {
				log.Error(err, "action", "insert history")
				msg.Nak()
				return
			}

			query.Where("created_at = ?created_at")
			if err := processRequest(cmd, mqttConn, conn); err != nil {
				if _, err := query.
					Set("status = ?", devices.DeviceCommandHistory_FALLURE).
					Set("error = ?", err.Error()).
					Update(); err != nil {
					log.Error(err, "action", "update history.status to FALLURE")
					msg.Nak()
				} else {
					msg.Term()
				}
				return
			}

			if !cmd.Downstream {
				if _, err := query.
					Set("responded_at = NOW()").
					Set("response = ?", cmd.Origin).
					Set("status = ?", devices.DeviceCommandHistory_SUCCESS).
					Update(); err != nil {
					log.Warn(err, "action", "update history.status to SUCCESS")
					msg.Term()
					return
				}
			}

		case *devices.Command_Response:
			history.Command = devices.RequestCode_name[int32(devices.ResponseMap[cmd.GetResponse()])]
			query := conn.Model(history).Where("command = ?command").Where("sequence = ?sequence")
			query.Where("status = ?", devices.DeviceCommandHistory_PROCESSING)

			if exists, err := query.Exists(); err != nil {
				log.Error(err, "action", "search command history")
				msg.Nak()
				return
			} else if !exists {
				log.Errorf("Unknown message %s:%d", history.Command, history.Sequence)
				msg.Term()
				return
			}

			// Transaction
			tx, err := conn.Begin()
			if err != nil {
				log.Error(err, "action", "BEGIN")
				msg.Nak()
				return
			}
			defer tx.Close()

			response, err := processResponse(cmd, tx)
			if err != nil {
				query.Set("status = ?", devices.DeviceCommandHistory_FALLURE)
				query.Set("error = ?", err.Error())
				if len(response) > 0 {
					query.Set("response = ?", response)
				}
			} else {
				query.Set("responded_at = NOW()")
				query.Set("response = ?", response)
				query.Set("status = ?", devices.DeviceCommandHistory_SUCCESS)
			}

			if _, err := query.Model(history).Update(); err != nil {
				log.Error(err, "action", "update history.status to SUCCESS")
				msg.Nak()
				return
			}

			// Commit
			if err := tx.Commit(); err != nil {
				log.Error(err, "action", "COMMIT")
				msg.Nak()
				return
			}

		// 등록되지 않은 명령
		default:
			history.Status = devices.DeviceCommandHistory_UNKNOWN
			query := conn.Model(history)
			if _, err := query.Insert(); err != nil {
				log.Error(err, "action", "insert history")
				msg.Term()
				return
			}
		}

		msg.Ack()
	})
	if err != nil {
		log.Fatal("Cannot connect stream", "error", err)
	}

	for <-close == false {
	}
	cc.Stop()
	log.Info("Gracefully stopping consumer of 'devices.command'")
}

// 요청 처리
func processRequest(cmd *devices.Command, mqttConn *mqtt.MqttClient, conn *pg.Conn) (err error) {
	var payload string
	var statusCode uint32

	var ctx context.Context
	if os.Getenv("SECURE_MODE") == "disable" {
		ctx = context.TODO()
	} else {
		ctx, err = auth.ServiceAccount()
		if err != nil {
			log.Error(err, "action", "sign-in service account")
			statusCode = RESOURCE_TEMPORARILY_UNAVAILABLE
			goto FINISH
		}
	}

	switch cmd.GetRequest() {

	case devices.RequestCode_get_config_req:
		statusCode = FUNCTION_NOT_IMPLEMENTED

	/***************************************************************************
	 * Upstream only
	 **************************************************************************/

	case devices.RequestCode_get_certificate_req:
		// TODO: 사이트 서비스로부터 다운로드하여 전달
		return nil

	case devices.RequestCode_get_time_req:
		payload, err = devices.MarshalGetTimeResponse(cmd.Sequence)

	case devices.RequestCode_set_status_req:
		req := &devices.SetStatusRequest{}
		err = cmd.Payload.UnmarshalTo(req)
		if err != nil {
			log.Error(err, "action", "anypb.Any -> devices.SetStatusRequest")
			statusCode = INVALID_ARGUMENT
			break
		}

		// Transaction
		tx, err := conn.Begin()
		if err != nil {
			log.Error(err, "action", "BEGIN")
			break
		}
		defer tx.Close()

		var claims *auth.Claims
		claims, err = auth.GetClaim(ctx)
		if err != nil {
			log.Errorf("Failed to get claims: %s", err.Error())
			break
		}

		for deviceID, channel := range req.Nodes {
			for channelID, value := range channel.AsMap() {
				id, err := strconv.Atoi(channelID)
				if err != nil {
					log.Warnf("Invalid channel ID: %s", err.Error())
					continue
				}

				history := &devices.DeviceStatusHistory{
					Channel: uint32(id),
				}

				if tmpStatus, ok := value.(float64); ok {
					switch uint32(tmpStatus) {
					case 0:
						history.Status = devices.DeviceStatus_NORMAL
						// 마지막 상태와 동일하면 기록하지 않음
						var temp devices.DeviceStatus
						query := tx.Model((*devices.DeviceStatusHistory)(nil))
						query.Where("device_id = ?", deviceID)
						query.Where("Channel = ?", id)
						query.Order("created_at DESC")
						query.Limit(1)
						if err := query.Select(&temp); err != nil {
							switch err {
							case pg.ErrNoRows:
								continue
							}
						} else if temp == devices.DeviceStatus_NORMAL {
							continue
						}

					default:
						history.Status = devices.DeviceStatus_TROUBLE
						history.Description = fmt.Sprintf("status code: %d", uint32(tmpStatus))
					}

					if err := writeHistory(ctx, tx, deviceID, claims.UserID, devices.DeviceHistory_STATUS, history); err != nil {
						log.Error(err, "action", "insert history")
					}
				}
			}
		}

		// Commit
		err = tx.Commit()
		if err != nil {
			break
		}

		payload, err = devices.MarshalResponse(devices.RequestMap[cmd.GetRequest()], cmd.Sequence, SUCCESS)

	case devices.RequestCode_set_ags_action_req:
		payload, err = agsActionRequset(ctx, cmd, conn)

	case devices.RequestCode_set_ags_warn_req:
		payload, err = agsWarnRequset(ctx, cmd, conn)

	/***************************************************************************
	 * Downstream only
	 **************************************************************************/

	case devices.RequestCode_get_data_req:
		req := &devices.GetDataRequest{}
		err = cmd.Payload.UnmarshalTo(req)
		if err != nil {
			log.Error(err, "action", "anypb.Any -> devices.GetDataRequest")
			statusCode = INVALID_ARGUMENT
			break
		}

		payload, err = req.Marshal(cmd.Sequence)

	case devices.RequestCode_set_config_req:
		req := &devices.SetConfigRequest{}
		err = cmd.Payload.UnmarshalTo(req)
		if err != nil {
			log.Error(err, "action", "anypb.Any -> devices.SetConfigRequest")
			statusCode = INVALID_ARGUMENT
			break
		}

		payload, err = req.Marshal(cmd.Sequence)

	// 모든 명령은 structpb.Struct 타입으로 처리
	default:
		req := &structpb.Struct{}
		err = req.UnmarshalJSON([]byte(cmd.Origin))
		if err != nil {
			log.Error(err, "action", "json -> structpb.Struct")
			statusCode = INVALID_ARGUMENT
			break
		}

		var tmp []byte
		req.Fields["command"] = structpb.NewStringValue(cmd.Command)
		req.Fields["seq"] = structpb.NewStringValue(fmt.Sprint(cmd.Sequence))
		if len(cmd.Kind) > 0 {
			req.Fields["response_topic"] = structpb.NewStringValue(fmt.Sprintf("%s/%s/_upstream/%s", cmd.Kind, cmd.SiteId, cmd.GatewayId))
		} else {
			req.Fields["response_topic"] = structpb.NewStringValue(fmt.Sprintf("%s/_upstream/%s", cmd.SiteId, cmd.GatewayId))
		}

		tmp, err = req.MarshalJSON()
		payload = string(tmp)
	}

FINISH:
	if err != nil || statusCode != SUCCESS {
		if err != nil && status.Code(err) == codes.InvalidArgument {
			statusCode = INVALID_ARGUMENT
		} else if statusCode == SUCCESS {
			statusCode = RESOURCE_TEMPORARILY_UNAVAILABLE
		}

		if resp, err := devices.MarshalResponse(devices.RequestMap[cmd.GetRequest()], cmd.Sequence, statusCode); err != nil {
			return err
		} else {
			payload = resp
		}
	}

	var topic string
	if len(cmd.Kind) > 0 {
		topic = fmt.Sprintf("%s/%s/_downstream/%s", cmd.Kind, cmd.SiteId, cmd.GatewayId)
	} else {
		topic = fmt.Sprintf("%s/_downstream/%s", cmd.SiteId, cmd.GatewayId)
	}

	log.Debugf("send %s: %s", topic, payload)
	if token :REDACTED
		log.Error(token.Error())
		return token.Error()
	}

	cmd.Origin = payload
	return err
}

// 응답 처리
func processResponse(cmd *devices.Command, tx *pg.Tx) (response string, err error) {
	switch cmd.GetResponse() {
	case devices.ResponseCode_set_relay_resp:
		req := &structpb.Struct{}
		err = cmd.Payload.UnmarshalTo(req)
		if err != nil {
			log.Error(err, "action", "anypb.Any -> structpb.Struct")
			break
		}

		// 처리 완료 확인
		payload := req.AsMap()
		delete(payload, "command")
		delete(payload, "seq")
		nodeID, ok := payload["node_id"].(string)
		if !ok {
			log.Warnf("Cannot read node ID. Received: (%T) %v", payload["node_id"], payload["node_id"])
		}
		delete(payload, "node_id")

		for channel, value := range payload {
			probe, ok := value.(map[string]any)
			if !ok {
				log.Warnf("Cannot read probe info of node '%s:%s'. Received: (%T) %v", nodeID, channel, value, value)
				continue
			}

			for probeID, value := range probe {
				probeData, ok := value.(map[string]any)
				if !ok {
					log.Warnf("Cannot read probe %q info of node '%s:%s'. Received: (%T) %v", probeID, nodeID, channel, value, value)
					continue
				}

				isClosed, ok := probeData["is_closed"].(bool)
				if !ok {
					log.Warnf("Cannot read probe %q state of node '%s:%s'. Received: (%T) %v", probeID, nodeID, channel, probeData["is_closed"], probeData["is_closed"])
					continue
				}

				_, err := tx.Exec(relayInsertStat, cmd.SiteId, probeID, isClosed, nodeID, channel)
				if err != nil {
					log.Warn(err)
				}
			}
		}

		response, err = devices.MarshalToString(req)

	case devices.ResponseCode_get_data_resp:
		response, err = devices.MarshalResponse(devices.ResponseCode_get_data_resp, cmd.Sequence, SUCCESS)

	// 데이터 조회 응답
	case devices.ResponseCode_get_config_resp:
		req := &devices.GetConfigResponse{}
		err = cmd.Payload.UnmarshalTo(req)
		if err != nil {
			log.Error(err, "action", "anypb.Any -> devices.GetConfigResponse")
			break
		}

		// TODO: 로드한 데이터 활용?

		response, err = devices.MarshalToString(req)

	case devices.ResponseCode_set_config_resp:
		req := &devices.SetConfigResponse{}
		err = cmd.Payload.UnmarshalTo(req)
		if err != nil {
			log.Error("Failed to unmarshaling:", err.Error())
			break
		}

		// TODO: 처리 완료 확인
		if req.Gateway != SUCCESS {
			log.Errorf("Failed to set gateway config: error code %d", req.Gateway)
		}

		for nodeID, code := range req.Nodes {
			if code != SUCCESS {
				log.Errorf("Failed to set node %q config: error code %d", nodeID, req.Gateway)
			}
		}

		response, err = devices.MarshalToString(req)

	case devices.ResponseCode_get_certificate_resp:
		// 사이트 서비스로부터 받은 응답 처리
		response, err = devices.MarshalToString(cmd.Payload)

	case devices.ResponseCode_set_agsmotor_resp:
		req := &structpb.Struct{}
		err = cmd.Payload.UnmarshalTo(req)
		if err != nil {
			log.Error(err, "action", "anypb.Any -> structpb.Struct")
			break
		}

		// 처리 완료 확인
		payload := req.AsMap()
		delete(payload, "command")
		delete(payload, "seq")
		nodeID, ok := payload["node_id"].(string)
		if !ok {
			log.Warnf("Cannot read node ID. Received: (%T) %v", payload["node_id"], payload["node_id"])
		}
		delete(payload, "node_id")

		for channel, value := range payload {
			probe, ok := value.(map[string]any)
			if !ok {
				log.Warnf("Cannot read probe info of node '%s:%s'. Received: (%T) %v", nodeID, channel, value, value)
				continue
			}

			// action 코드 확인
			action, ok := probe["action"].(string)
			if !ok {
				log.Warnf("Cannot read action of node '%s:%s'. Received: %v", nodeID, channel, probe)
				continue
			}
			switch action {
			case "open":
			case "close":
			case "stop":
			default:
				log.Warnf("Unknown 'action' of node '%s:%s'. Received: %v", nodeID, channel, action)
				continue
			}

			// mode 코드 확인
			mode, ok := probe["mode"].(string)
			if !ok {
				log.Warnf("Cannot read mode of node '%s:%s'. Received: %v", nodeID, channel, probe)
				continue
			}
			if mode != "manual" && mode != "beymons" {
				log.Warnf("Unknown 'mode' of node '%s:%s'. Received: %v", nodeID, channel, mode)
				continue
			}

			motorAct, ok := probe["motor_act"].(string)
			if !ok {
				log.Warnf("Cannot read motor_act of node '%s:%s'. Received: %v", nodeID, channel, probe)
				continue
			}

			// 최대 프로브수 확인
			var probes int
			if err := tx.Model((*devices.Sensor)(nil)).
				Where("device_id = ?", nodeID).Where("channel_id = ?", channel).
				Column("probes").Select(&probes); err != nil {
				log.Warnf("Cannot get probes of node '%s:%s'. Error: %v", nodeID, channel, err.Error())
				break
			}

			// 프로브 상태
			stat, err := strconv.ParseUint(motorAct[2:], 16, 64)
			if err != nil {
				log.Warnf("Cannot read motor_act of node '%s:%s'. Received: %v", nodeID, channel, motorAct)
				continue
			}
			for i := 0; i < probes || stat>>i != 0; i++ {
				if stat>>i&0x00000001 == 1 {
					_, err := tx.Exec(agsmotorInsertStat, cmd.SiteId, i+1, mode, action, nodeID, channel)
					if err != nil {
						log.Warn(err)
						break
					}
				}
			}
		}

		response, err = devices.MarshalToString(req)

	// 불가능한 코드 리스트
	case devices.ResponseCode_get_latest_value_resp,
		devices.ResponseCode_get_time_resp,
		devices.ResponseCode_set_status_resp:
		err = fmt.Errorf("Unknown command %q", cmd.GetResponse())
		log.Warn(err)

	case devices.ResponseCode_set_agsmotor_operation_resp:
		payload := &structpb.Struct{}
		err = payload.UnmarshalJSON([]byte(cmd.Origin))
		if err != nil {
			log.Error(err, "action", "json -> structpb.Struct")
			break
		}

		// 처리할 필요가 없는 필드 제거
		delete(payload.Fields, "command")
		delete(payload.Fields, "seq")
		delete(payload.Fields, "node_id")

		var tmp []byte
		tmp, err = payload.MarshalJSON()
		response = string(tmp)

		for _, result := range payload.Fields {
			if text := result.GetStringValue(); strings.ToLower(text) != "ok" {
				err = fmt.Errorf("There was an error reported by the device")
				break
			}
		}

	// 기본은 structpb.Struct으로 처리
	default:
		response = cmd.Origin
	}

	return response, err
}
