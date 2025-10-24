package server

import (
	"context"
	"fmt"
	"time"

	"github.com/go-pg/pg/v10"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"gitlab.suredatalab.kr/services/notifications"
	"google.golang.org/protobuf/types/known/structpb"

	"gitlab.suredatalab.kr/beymons/devices"
)

type DisconnectedDevice struct {
	DeviceRole devices.DeviceRole
	DeviceID   string
	ChannelID  uint32
	SensorType string
}

// 1시간 이상 데이터를 미수신한 장치의 상태를 변경하는 함수
func CheckDisconnected() {
	log.Info("Search for disconnected devices")
	// DB Connection
	conn := pgorm.Conn()
	defer conn.Close()
	// Transaction
	tx, err := conn.Begin()
	if err != nil {
		log.Error(err)
		return
	}
	defer tx.Close()

	// 수신 이력이 없는 센서
	query := tx.Model((*devices.Device)(nil)).Column("device_role", "device.device_id", "channel_id", "sensor_type")
	query.Join("JOIN site_devices USING (device_id)")
	query.Join("JOIN sensors USING (device_id)")
	query.Join("LEFT JOIN last_received_histories h").JoinOn("h.device_id = device.device_id AND channel = channel_id")
	query.Where("device_role IN (?, ?)", devices.DeviceRole_NODE, devices.DeviceRole_NODEGATEWAY)
	query.Where("received_at < NOW() - INTERVAL '1 hour' OR received_at IS NULL")

	// 수신 이력이 없는 GW
	gwQuery := tx.Model((*devices.Device)(nil)).Distinct()
	gwQuery.Join("JOIN site_devices USING (device_id)")
	gwQuery.Column("device_role", "device.device_id")
	gwQuery.ColumnExpr("0 AS channel_id")
	gwQuery.ColumnExpr("NULL AS sensor_type")
	gwQuery.Where("device_role IN (?, ?)", devices.DeviceRole_GATEWAY, devices.DeviceRole_NODEGATEWAY)
	gwQuery.Join("LEFT JOIN last_received_histories h").JoinOn("h.gateway_id = device.device_id")
	gwQuery.Where("received_at < NOW() - INTERVAL '1 hour' OR received_at IS NULL")
	query.Union(gwQuery)

	var disconnectedDevice []*DisconnectedDevice
	if err := query.Select(&disconnectedDevice); err != nil {
		log.Warn(err)
	}

	log.Debugf("disconnected device: %v", disconnectedDevice)
	messages := make(map[string]*notifications.Notification)
	for _, device := range disconnectedDevice {
		if err := changeDeviceStatus(tx, device.DeviceID, device.ChannelID, devices.DeviceStatus_NOT_RECEIVED); err != nil {
			log.Warn(err)
			continue
		}

		// 알림 메시지 작성
		if _, ok := messages[device.DeviceID]; !ok {
			variable := &structpb.Struct{
				Fields: map[string]*structpb.Value{
					"device_role": structpb.NewStringValue(device.DeviceRole.String()),
					"occurred_at": structpb.NewStringValue(time.Now().Format(time.RFC3339)),
				},
			}
			messages[device.DeviceID] = &notifications.Notification{
				TemplateId: "disconnect-device",
				TargetId:   device.DeviceID,
				Variable:   variable,
			}
		}

		if device.ChannelID > 0 {
			list := messages[device.DeviceID].Variable.Fields["channels"].GetListValue()
			if list == nil {
				list = &structpb.ListValue{}
			}
			list.Values = append(list.Values, structpb.NewStructValue(&structpb.Struct{
				Fields: map[string]*structpb.Value{
					"address":     structpb.NewNumberValue(float64(device.ChannelID)),
					"sensor_type": structpb.NewStringValue(device.SensorType),
				},
			}))
			messages[device.DeviceID].Variable.Fields["channels"] = structpb.NewListValue(list)
		}
	}

	// 모든 센서가 데이터 수신이 확인되지 않는 경우 노드의 상태 변경
	var target []string
	query = tx.Model((*devices.Device)(nil)).Group("device_id").Column("device_role", "device_id")
	query.Join("JOIN sensors USING (device_id)")
	query.Having("COUNT(1) = COUNT(1) FILTER(WHERE sensors.status = ?)", devices.DeviceStatus_NOT_RECEIVED)
	if err := query.Select(&target); err != nil {
		log.Warn("Failed to change status", "error", err)
	}
	for _, deviceID := range target {
		if err := changeDeviceStatus(tx, deviceID, 0, devices.DeviceStatus_NOT_RECEIVED); err != nil {
			log.Warn(err)
		}
	}

	if len(messages) > 0 {
		if err := tx.Commit(); err != nil {
			log.Error(err)
		}

		for _, msg := range messages {
			// 메시지 전송
			if err := msg.Send(context.TODO()); err != nil {
				log.Warn(err)
			}
		}
	}
}

// 재연결 확인 쿼리
func checkReconnected(tx *pg.Tx, nodeID string, payload map[string]any) (msg *notifications.Notification) {
	// 센서의 기존 상태 확인
	var sensors []*devices.Sensor
	query := tx.Model((*devices.Sensor)(nil))
	query.Where("device_id = ?", nodeID)
	query.Order("channel_id")
	if err := query.Select(&sensors); err != nil {
		log.Warn("Failed to check sensor status", "error", err)
		return
	}

	list := &structpb.ListValue{}
	for _, sensor := range sensors {
		if _, ok := payload[fmt.Sprint(sensor.ChannelId)]; !ok {
			continue
		}

		// 기존에 연결이 끊긴 상태인 경우 정상 처리
		if sensor.Status == devices.DeviceStatus_NOT_RECEIVED {
			if err := changeDeviceStatus(tx, nodeID, sensor.ChannelId, devices.DeviceStatus_NORMAL); err != nil {
				log.Warn(err)
				return
			}

			list.Values = append(list.Values, structpb.NewStructValue(&structpb.Struct{
				Fields: map[string]*structpb.Value{
					"address":     structpb.NewNumberValue(float64(sensor.ChannelId)),
					"sensor_type": structpb.NewStringValue(sensor.SensorType),
				},
			}))
		}
	}

	if len(list.Values) > 0 {
		// 노드 데이터가 확인되었으므로 정상 처리
		if err := changeDeviceStatus(tx, nodeID, 0, devices.DeviceStatus_NORMAL); err != nil {
			log.Warn(err)
			return
		}

		msg = &notifications.Notification{
			TemplateId: "reconnect-device",
			TargetId:   nodeID,
			Variable: &structpb.Struct{
				Fields: map[string]*structpb.Value{
					"released_at": structpb.NewStringValue(time.Now().Format(time.RFC3339)),
					"sensors":     structpb.NewListValue(list),
				},
			},
		}
	}

	return
}

// 장치 상태 변경
func changeDeviceStatus(tx *pg.Tx, deviceID string, channel uint32, status devices.DeviceStatus) error {
	// 마지막 상태 확인
	var old devices.DeviceStatus
	var query *pg.Query
	if channel > 0 {
		query = tx.Model((*devices.Sensor)(nil))
		query.Where("channel_id = ?", channel)
	} else {
		query = tx.Model((*devices.Device)(nil))
	}
	query.Where("device_id = ?", deviceID)
	query.ColumnExpr("COALESCE(status, ?)", devices.DeviceStatus_NORMAL)
	if err := query.Select(&old); err != nil {
		if err != pg.ErrNoRows {
			return err
		}
	}

	if old == status {
		return nil
	}

	// 이력으로 등록
	history := &devices.DeviceHistory{
		DeviceId:      deviceID,
		Action:        devices.DeviceHistory_STATUS,
		CreatedUserId: serviceAccountID,
	}
	if _, err := tx.Model(history).Returning("created_at").Insert(); err != nil {
		return err
	}

	if _, err := tx.Model(&devices.DeviceStatusHistory{
		CreatedAt: history.CreatedAt,
		DeviceId:  history.DeviceId,
		Channel:   channel,
		Status:    status,
	}).Insert(); err != nil {
		return err
	}

	return nil
}
