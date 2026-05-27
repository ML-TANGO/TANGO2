package server

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/go-pg/pg/v10"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/services/notifications"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/structpb"

	"gitlab.suredatalab.kr/beymons/devices"
)

// 대상 설비 조회
func getTargetName(ctx context.Context, conn *pg.Conn, deviceID string) (targetID, targetName, groupName string, err error) {
	query := conn.ModelContext(ctx).Table("facility_devices")
	query.Where("device_id = ?", deviceID)
	query.Join("JOIN facilities USING (facility_id)")
	query.Join("LEFT JOIN groups USING (group_id)")
	if err = query.Column("facility_id", "facility_name", "group_name").
		Select(&targetID, &targetName, &groupName); err != nil {
		if err == pg.ErrNoRows {
			err = fmt.Errorf("No facilities were found to which the device '%s' was connected", deviceID)
		}
		return
	}

	return
}

// 재어 설정 조회
func getFacilityAttribute(ctx context.Context, conn *pg.Conn, targetID string) (map[string]any, error) {
	query := conn.ModelContext(ctx).Table("facility_attributes")
	query.Where("facility_id = ?", targetID)
	query.ColumnExpr("JSONB_OBJECT(ARRAY_AGG(attribute), ARRAY_AGG(value)) attributes")
	attributes := make(map[string]any)
	if err := query.Select(&attributes); err != nil {
		if err == pg.ErrNoRows {
			err = fmt.Errorf("There are no set attributes in the facility '%s'", targetID)
		}
		return nil, err
	}

	if temp, ok := attributes["attributes"].(json.RawMessage); ok {
		attributes = map[string]any{}
		if err := json.Unmarshal(temp, &attributes); err != nil {
			return nil, err
		}
	}

	log.Debugf("attributes: %+v", attributes)
	return attributes, nil
}

// 연결된 센서 확인
func checkSensorType(ctx context.Context, conn *pg.Conn, deviceID, channelID string) (uint32, error) {
	var (
		sensorType string
		nrProbe    uint32
	)
	query := conn.ModelContext(ctx, (*devices.Sensor)(nil))
	query.Where("device_id = ?", deviceID)
	query.Where("channel_id = ?", channelID)
	query.Column("sensor_type", "probes")
	count, err := query.SelectAndCount(&sensorType, &nrProbe)
	if err != nil {
		return 0, err
	} else if count == 0 {
		return 0, fmt.Errorf("Cannot find sensor [%s:%s]", deviceID, channelID)
	}

	if sensorType != "agsmotor" {
		return 0, fmt.Errorf("mismatch sensor type: %s", sensorType)
	}

	return nrProbe, nil
}

// 모터 동작 완료 알림
func agsActionRequset(ctx context.Context, cmd *devices.Command, conn *pg.Conn) (payload string, err error) {
	req := &structpb.Struct{}
	err = cmd.Payload.UnmarshalTo(req)
	if err != nil {
		log.Error(err, "action", "anypb.Any -> structpb.Struct")
		return
	}

	defer func() {
		if r := recover(); r != nil {
			err = status.Errorf(codes.InvalidArgument, "invalid argument: %+v", recover())
			log.Error(err)
		}
	}()

	deviceID := req.Fields["node_id"].GetStringValue()

	// 대상 설비 조회
	var targetID, targetName, groupName string
	if targetID, targetName, groupName, err = getTargetName(ctx, conn, deviceID); err != nil {
		return
	}

	attributes, err := getFacilityAttribute(ctx, conn, targetID)
	if err != nil {
		log.Error("Failed to get facility attributes", "error", err)
		return payload, err
	}

	noti := &notifications.Notification{
		TemplateId: "ags-action-noti",
		TargetId:   deviceID,
		Variable: &structpb.Struct{
			Fields: make(map[string]*structpb.Value),
		},
	}

	if len(groupName) > 0 {
		noti.Variable.Fields["target"] = structpb.NewStringValue(fmt.Sprintf("%s - %s", groupName, targetName))
	} else {
		noti.Variable.Fields["target"] = structpb.NewStringValue(targetName)
	}

	// 동작 정보 추가
	log.Debugf("command_from: %s", req.Fields["command_from"].GetStringValue())
	commandFrom := req.Fields["command_from"].GetStringValue()

	// 채널(modbus)만 남기고 삭제
	delete(req.Fields, "command")
	delete(req.Fields, "response_topic")
	delete(req.Fields, "seq")
	delete(req.Fields, "command_from")
	delete(req.Fields, "node_id")

	// 알림 메시지 작성
	var (
		actionMsg   []string
		channelList []string
	)
	for channelID, channel := range req.Fields {
		var nrProbe uint32
		nrProbe, err = checkSensorType(ctx, conn, deviceID, fmt.Sprint(channelID))
		if err != nil {
			log.Warn(err)
			continue
		}
		if nrProbe == 0 {
			continue
		}

		channelList = append(channelList, fmt.Sprintf("'%s'", channelID))
		log.Debugf("Channel %v: %s", channelID, fmt.Sprintf("channel_%s", channelID))
		channelName, ok := attributes[fmt.Sprintf("channel_%s", channelID)]
		if !ok {
			channelName = channelID
		}

		probes := channel.GetStructValue()
		if probes == nil || probes.Fields == nil || len(probes.Fields) == 0 {
			continue
		}

		var msg []string
		for probeID, probe := range probes.Fields {
			probeName, ok := attributes[fmt.Sprintf("%s-ch%s", channelID, probeID)]
			if !ok {
				probeName = probeID
			}

			log.Debugf("Probe %v: %s", probeID, probeName)
			msg = append(msg, fmt.Sprintf("%v %d%%", probeName, int(probe.GetNumberValue())))
		}

		if len(msg) > 0 {
			actionMsg = append(actionMsg, fmt.Sprintf("%s: %s", channelName, strings.Join(msg, ", ")))
		}
	}

	if len(actionMsg) == 0 {
		err = status.Error(codes.InvalidArgument, "No message")
		return
	}

	if commandFrom == "beymons" {
		var actionTime time.Time
		query := conn.ModelContext(ctx, (*devices.DeviceCommandHistory)(nil))
		query.Where("device_id = ?", cmd.GatewayId)
		query.Where("command = ?", devices.RequestCode_name[int32(devices.RequestCode_set_agsmotor_req)])
		query.Where("status <> ?", devices.DeviceCommandHistory_FALLURE)
		query.Where("created_at > NOW() - INTERVAL '1 day'")
		query.Where("payload->>'node_id' = ?", deviceID)
		query.Where(fmt.Sprintf("payload ?& ARRAY[%s]", strings.Join(channelList, ",")))
		query.OrderExpr("created_at DESC").Limit(1)
		query.ColumnExpr("COALESCE(responded_at, created_at)")
		var count int
		if count, err = query.SelectAndCount(&actionTime); err != nil {
			return
		} else if count == 0 {
			err = fmt.Errorf("No history of sending commands")
			return
		}

		duration := time.Now().Sub(actionTime)
		noti.Variable.Fields["action_time"] = structpb.NewStringValue(actionTime.Format("2006-01-02 15:04:05 (MST)"))
		noti.Variable.Fields["duration"] = structpb.NewStringValue(fmt.Sprint(duration.Truncate(time.Second)))
		hour := duration.Truncate(time.Hour)
		min := duration.Truncate(time.Second)
		switch {
		case duration.Hours() > 1:
			noti.Variable.Fields["dur_hour"] = structpb.NewStringValue(fmt.Sprint(hour.Hours()))
			fallthrough
		case duration.Minutes() > 1:
			min = duration - hour
			noti.Variable.Fields["dur_min"] = structpb.NewStringValue(fmt.Sprint(min.Truncate(time.Minute).Minutes()))
			fallthrough
		default:
			sec := min - min.Truncate(time.Minute)
			noti.Variable.Fields["dur_sec"] = structpb.NewStringValue(fmt.Sprint(sec.Truncate(time.Second).Seconds()))
		}
	}

	noti.Variable.Fields["message"] = structpb.NewStringValue(strings.Join(actionMsg, "\n"))

	// 알림 발송
	if err := noti.Send(ctx); err != nil {
		log.Warn("Failed to send message", "error", err)
	}

	// 응답 메시지 작성
	res := &structpb.Struct{Fields: map[string]*structpb.Value{
		"command": structpb.NewStringValue(devices.ResponseCode_name[int32(devices.ResponseCode_set_ags_action_resp)]),
		"seq":     structpb.NewNumberValue(float64(cmd.Sequence)),
	}}
	var tmp []byte
	tmp, err = res.MarshalJSON()
	payload = string(tmp)
	return
}

// 모터 동작 이상 알림
func agsWarnRequset(ctx context.Context, cmd *devices.Command, conn *pg.Conn) (payload string, err error) {
	req := &structpb.Struct{}
	err = cmd.Payload.UnmarshalTo(req)
	if err != nil {
		log.Error(err, "action", "anypb.Any -> structpb.Struct")
		return
	}

	defer func() {
		if r := recover(); r != nil {
			err = status.Errorf(codes.InvalidArgument, "invalid argument: %+v", recover())
			log.Error(err)
		}
	}()

	deviceID := req.Fields["node_id"].GetStringValue()

	// 대상 설비 조회
	var targetID, targetName, groupName string
	if targetID, targetName, groupName, err = getTargetName(ctx, conn, deviceID); err != nil {
		return
	}

	attributes, err := getFacilityAttribute(ctx, conn, targetID)
	if err != nil {
		log.Error("Failed to get facility attributes", "error", err)
		return payload, err
	}

	noti := &notifications.Notification{
		TemplateId: "ags-action-error",
		TargetId:   deviceID,
		Variable: &structpb.Struct{
			Fields: map[string]*structpb.Value{
				"occurred_at": structpb.NewStringValue(time.Now().Format(time.RFC3339)),
			},
		},
	}

	if len(groupName) > 0 {
		noti.Variable.Fields["target"] = structpb.NewStringValue(fmt.Sprintf("%s - %s", groupName, targetName))
	} else {
		noti.Variable.Fields["target"] = structpb.NewStringValue(targetName)
	}

	// 채널만 남기고 삭제
	delete(req.Fields, "command")
	delete(req.Fields, "response_topic")
	delete(req.Fields, "seq")
	delete(req.Fields, "command_from")
	delete(req.Fields, "node_id")

	// 알림 메시지 작성
	var actionMsg, trouble []string
	for channelID, channel := range req.Fields {
		var nrProbe uint32
		nrProbe, err = checkSensorType(ctx, conn, deviceID, fmt.Sprint(channelID))
		if err != nil {
			log.Warn(err)
			continue
		}
		_ = nrProbe // TODO: 나중에 프로브 번호까지 확인

		channelName, ok := attributes[fmt.Sprintf("channel_%s", channelID)]
		if !ok {
			channelName = channelID
		}

		probes := channel.GetStructValue()
		if probes == nil || probes.Fields == nil || len(probes.Fields) == 0 {
			continue
		}

		var msg []string
		for probeID, probe := range probes.Fields {
			probeName, ok := attributes[fmt.Sprintf("ch%s-probe_%s", channelID, probeID)]
			if !ok {
				probeName = probeID
			}

			msg = append(msg, fmt.Sprint(probeName))
			trouble = append(trouble, probe.GetStringValue())
		}

		if len(msg) > 0 {
			actionMsg = append(actionMsg, fmt.Sprintf("%s - %s", channelName, strings.Join(msg, ", ")))
		}
	}

	if len(actionMsg) == 0 {
		err = status.Error(codes.InvalidArgument, "No message")
		return
	}

	noti.Variable.Fields["location"] = structpb.NewStringValue(strings.Join(actionMsg, "; "))
	noti.Variable.Fields["trouble"] = structpb.NewStringValue(strings.Join(trouble, ", "))

	// 알림 발송
	if err := noti.Send(ctx); err != nil {
		log.Warn("Failed to send message", "error", err)
	}

	// 응답 메시지 작성
	res := &structpb.Struct{Fields: map[string]*structpb.Value{
		"command": structpb.NewStringValue(devices.ResponseCode_name[int32(devices.ResponseCode_set_ags_warn_resp)]),
		"seq":     structpb.NewNumberValue(float64(cmd.Sequence)),
	}}
	var tmp []byte
	tmp, err = res.MarshalJSON()
	payload = string(tmp)
	return
}
