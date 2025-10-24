package main

import (
	"context"
	"strings"

	mqtt "github.com/eclipse/paho.mqtt.golang"
	"gitlab.suredatalab.kr/sdlmicro/middleware/async"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/types/known/structpb"
	"google.golang.org/protobuf/types/known/timestamppb"

	"gitlab.suredatalab.kr/beymons/collects"
)

func messageHandler(client mqtt.Client, msg mqtt.Message) {
	log.Infof("Receive %q", msg.Topic())

	data := &collects.ReceiveData{
		ReceivedAt: timestamppb.Now(),
		Size:       uint32(len(msg.Payload())),
		Data:       &structpb.Struct{},
	}

	switch strings.Count(msg.Topic(), "/") {
	case 2:
		// {region_id}/{message_type}/{gateway_id}
		entity := strings.Split(msg.Topic(), "/")
		data.SiteId = entity[0]
		data.GatewayId = entity[2]
	case 3:
		// {application}/{region_id}/{message_type}/{gateway_id}
		entity := strings.Split(msg.Topic(), "/")
		data.SiteId = entity[1]
		data.GatewayId = entity[3]
	default:
		log.Errorf("Invalid Topic: %s", msg.Topic())
		return
	}

	// JSON -> structpb.Struct
	if err := data.Data.UnmarshalJSON(msg.Payload()); err != nil {
		log.Errorf("Failed to unmarshaling: %s", err.Error())
		return
	}

	// Message -> []byte
	payload, err := proto.Marshal(data)
	if err != nil {
		log.Errorf("Failed to marshaling: %s", err.Error())
		return
	}

	if err := async.Push(context.TODO(), collects.PACKAGE_NAME, "data", payload); err != nil {
		log.Errorf("Failed to push: %s", err.Error())
	}
}
