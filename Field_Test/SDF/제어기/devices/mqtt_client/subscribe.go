package main

import (
	"bytes"
	"context"
	"strings"

	mqtt "github.com/eclipse/paho.mqtt.golang"
	"github.com/golang/protobuf/jsonpb"
	"gitlab.suredatalab.kr/sdlmicro/middleware/async"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/types/known/anypb"
	"google.golang.org/protobuf/types/known/structpb"

	"gitlab.suredatalab.kr/beymons/devices"
)

func messageHandler(client mqtt.Client, msg mqtt.Message) {
	log.Infof("Receive %q", msg.Topic())

	cmd := newCommand(msg.Payload())
	if cmd == nil {
		return
	}

	switch strings.Count(msg.Topic(), "/") {
	case 2:
		// {region_id}/{message_type}/{gateway_id}
		entity := strings.Split(msg.Topic(), "/")
		cmd.SiteId = entity[0]
		cmd.GatewayId = entity[2]
	case 3:
		// {application}/{region_id}/{message_type}/{gateway_id}
		entity := strings.Split(msg.Topic(), "/")
		cmd.Kind = entity[0]
		cmd.SiteId = entity[1]
		cmd.GatewayId = entity[3]
	default:
		log.Errorf("Invalid Topic: %s", msg.Topic())
		return
	}

	// Message -> []byte
	payload, err := proto.Marshal(cmd)
	if err != nil {
		log.Errorf("Failed to marshaling: %s", err.Error())
		return
	}

	if err := async.Push(context.TODO(), devices.PACKAGE_NAME, "command", payload); err != nil {
		log.Errorf("Failed to push: %s", err.Error())
	}
}

var unmarshaler = jsonpb.Unmarshaler{
	AllowUnknownFields: true,
}

// 명령 생성
func newCommand(payload []byte) *devices.Command {
	cmd := &devices.Command{}
	if err := unmarshaler.Unmarshal(bytes.NewBuffer(payload), cmd); err != nil {
		log.Error(err, "action", "payload(JSON) -> Command")
		return nil
	}

	cmd.Origin = string(payload)

	var msg proto.Message
	switch cmd.Command {

	// 장치 설정 조회에 대한 응답
	case devices.ResponseCode_name[int32(devices.ResponseCode_get_config_resp)]:
		cmd.Opcode = &devices.Command_Response{Response: devices.ResponseCode_get_config_resp}
		msg = &devices.GetConfigResponse{}
		if err := jsonpb.UnmarshalString(string(payload), msg.(*devices.GetConfigResponse)); err != nil {
			log.Error(err, "action", "payload(JSON) -> devices.GetConfigResponse")
			return nil
		}

	// 장치 설정에 대한 응답
	case devices.ResponseCode_name[int32(devices.ResponseCode_set_config_resp)]:
		cmd.Opcode = &devices.Command_Response{Response: devices.ResponseCode_set_config_resp}
		msg = &devices.SetConfigResponse{}
		if err := jsonpb.UnmarshalString(string(payload), msg.(*devices.SetConfigResponse)); err != nil {
			log.Error(err, "action", "payload(JSON) -> devices.SetConfigResponse")
			return nil
		}

	// 장치 설정 요청
	case devices.RequestCode_name[int32(devices.RequestCode_set_config_req)]:
		cmd.Opcode = &devices.Command_Request{Request: devices.RequestCode_set_config_req}
		msg = &devices.SetConfigRequest{}
		if err := jsonpb.UnmarshalString(string(payload), msg.(*devices.SetConfigRequest)); err != nil {
			log.Error(err, "action", "payload(JSON) -> devices.SetConfigRequest")
			return nil
		}

	// 상태 보고
	case devices.RequestCode_name[int32(devices.RequestCode_set_status_req)]:
		cmd.Opcode = &devices.Command_Request{Request: devices.RequestCode_set_status_req}
		msg = &devices.SetStatusRequest{}
		if err := jsonpb.UnmarshalString(string(payload), msg.(*devices.SetStatusRequest)); err != nil {
			log.Error(err, "action", "payload(JSON) -> devices.SetStatusRequest")
			return nil
		}

	// Payload가 필요 없는 명령
	case devices.RequestCode_name[int32(devices.RequestCode_get_certificate_req)],
		devices.RequestCode_name[int32(devices.RequestCode_get_time_req)],
		devices.RequestCode_name[int32(devices.RequestCode_get_config_req)]:
		cmd.Opcode = &devices.Command_Request{Request: devices.RequestCode(devices.RequestCode_value[cmd.Command])}
		return cmd

	// 서버에서 처리되지 않는 코드
	case devices.RequestCode_name[int32(devices.RequestCode_set_relay_req)],
		devices.RequestCode_name[int32(devices.RequestCode_get_data_req)],
		devices.ResponseCode_name[int32(devices.ResponseCode_get_certificate_resp)],
		devices.ResponseCode_name[int32(devices.ResponseCode_get_time_resp)],
		devices.ResponseCode_name[int32(devices.ResponseCode_get_latest_value_resp)],
		devices.ResponseCode_name[int32(devices.ResponseCode_set_status_resp)]:
		return nil

	// 기본은 structpb.Struct으로 처리
	default:
		if strings.HasSuffix(cmd.Command, "_req") {
			code := devices.RequestCode(devices.RequestCode_value[cmd.Command])
			cmd.Opcode = &devices.Command_Request{Request: code}
		} else {
			code := devices.ResponseCode(devices.ResponseCode_value[cmd.Command])
			cmd.Opcode = &devices.Command_Response{Response: code}
		}
		msg = &structpb.Struct{}
		if err := msg.(*structpb.Struct).UnmarshalJSON(payload); err != nil {
			log.Error(err, "action", "payload(JSON) -> structpb.Struct")
			return nil
		}
	}

	if msg != nil {
		cmd.Payload, _ = anypb.New(msg)
	}
	return cmd
}
