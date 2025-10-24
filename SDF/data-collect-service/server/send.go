package server

import (
	"context"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/go-pg/pg/v10"
	"github.com/nats-io/nats.go/jetstream"
	"gitlab.suredatalab.kr/sdlmicro/middleware/async"
	"gitlab.suredatalab.kr/sdlmicro/middleware/errors"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"gitlab.suredatalab.kr/services/notifications"
	"google.golang.org/protobuf/proto"
	"google.golang.org/protobuf/types/known/emptypb"
	"google.golang.org/protobuf/types/known/structpb"
	"google.golang.org/protobuf/types/known/timestamppb"

	"gitlab.suredatalab.kr/beymons/collects"
	"gitlab.suredatalab.kr/beymons/devices"
	"gitlab.suredatalab.kr/beymons/sites"
)

// Send - 데이터 전송
func (s CollectsServer) Send(ctx context.Context, req *collects.ReceiveData) (*emptypb.Empty, error) {
	if req.ReceivedAt == nil {
		req.ReceivedAt = timestamppb.Now()
	}

	// Message -> []byte
	payload, err := proto.Marshal(req)
	if err != nil {
		log.Errorf("Failed to marshaling: %s", err.Error())
		return nil, log.InternalError(ctx, err)
	}

	log.Debugf("Send data to NATS: %s/%s %s", req.SiteId, req.GatewayId, req.ReceivedAt.AsTime().Format(time.RFC3339Nano))
	if err := async.Push(ctx, collects.PACKAGE_NAME, "data", payload); err != nil {
		log.Errorf("Failed to push: %s", err.Error())
		return nil, log.InternalError(ctx, err)
	}

	// DB Connection
	conn := pgorm.Conn()
	defer conn.Close()

	// 처리 확인
	ch := make(chan error)
	go func() {
		query := conn.ModelContext(ctx, (*collects.ReceiveHistory)(nil))
		query.Where("site_id = ?", req.SiteId)
		query.Where("gateway_id = ?", req.GatewayId)
		query.Where("received_at = ?", req.ReceivedAt.AsTime().Format(time.RFC3339Nano))
		query.Where("processed_at IS NOT NULL")

		for i := 0; i < 100; i++ {
			time.Sleep(time.Millisecond * 100)
			exists, err := query.Exists()
			if err != nil {
				ch <- pgorm.GetError(ctx, err)
				return
			} else if exists {
				ch <- nil
				return
			}
		}
		ch <- errors.New(collects.ErrTimeout)
	}()

	if err := <-ch; err != nil {
		return nil, err
	}

	return &emptypb.Empty{}, nil
}

var (
	ErrInvalidDataFormat = fmt.Errorf("Invalid format of received data")
	ErrNoData            = fmt.Errorf("No data")
	ErrInvalidTimestamp  = fmt.Errorf("Not a valid timestamp range")
)

func CollectConsumer(close chan bool) {
	// Consumer 시작
	cc, err := async.Consume(collects.PACKAGE_NAME, "data", 0, func(ctx context.Context, msg jetstream.Msg) {
		payload := &collects.ReceiveData{}
		if err := proto.Unmarshal(msg.Data(), payload); err != nil {
			log.Errorf("Failed to decoding: %s", err.Error())
			msg.Nak()
			return
		}

		msg.InProgress()

		// DB Connection
		conn := pgorm.Conn()
		defer conn.Close()

		// 수신 이력
		history := &collects.ReceiveHistory{
			ReceivedAt: payload.ReceivedAt,
			SiteId:     payload.SiteId,
			GatewayId:  payload.GatewayId,
			Size:       payload.Size,
			Origin:     msg.Data(),
		}
		result, err := conn.Model(history).OnConflict("DO NOTHING").Insert()
		if err != nil {
			log.Error(err)
			msg.Nak()
			return
		}

		if result.RowsAffected() == 0 {
			log.Warnf("Duplicate message received from GW %s at Site %s on %s",
				payload.GatewayId, payload.SiteId, payload.ReceivedAt.AsTime().Format(time.RFC3339Nano))
			msg.Term()
			return
		}

		// 사이트 및 GW 확인
		if exists, err := conn.Model((*sites.SiteDevice)(nil)).
			Where("site_id = ?", payload.SiteId).
			Where("device_id = ?", payload.GatewayId).
			Join("JOIN devices USING (device_id)").
			Where("device_role IN (?, ?)", devices.DeviceRole_GATEWAY, devices.DeviceRole_NODEGATEWAY).
			Exists(); err != nil {
			msg.Nak()
			return
		} else if !exists {
			err = fmt.Errorf("Gateway %q does not exist or is not connected to site %q", payload.GatewayId, payload.SiteId)
			log.Error(err)
			if _, err := conn.Model(history).Set("error = ?", err.Error()).WherePK().Update(); err != nil {
				log.Warn(err.Error())
			}
			msg.Term()
			return
		}

		if recorded, nodes, sensors, err := process(conn, payload, pgorm.ExistTable(conn, "sensor_limits")); err != nil {
			log.Error("Failed to process received data", "error", err)
			// 에러 메시지 상태 갱신
			if _, err := conn.Model(history).Set("error = ?", err.Error()).WherePK().Update(); err != nil {
				log.Warn(err.Error())
			}

			// TODO: 처리 실패 알림
			msg.Term()
			return
		} else {
			// 처리 완료 기록
			if _, err := conn.Model(history).WherePK().
				Set("nodes = ?", nodes).
				Set("sensors = ?", sensors).
				Set("recorded = ?", recorded).
				Set("processed_at = ?", timestamppb.Now()).Update(); err != nil {
				log.Error(err)
				msg.Nak()
				return
			}
			msg.Ack()
		}
	})
	if err != nil {
		log.Fatal("Cannot connect stream", "error", err)
	}

	for <-close == false {
	}
	cc.Stop()
	log.Info("Gracefully stopping consumer of 'collects.data'")
}

// 수신 데이터 처리
func process(conn *pg.Conn, payload *collects.ReceiveData, existLimitTbl bool) (recorded int, nodes uint32, sensors uint32, err error) {
	data, ok := payload.Data.AsMap()["data"].([]any)
	if !ok {
		return recorded, nodes, sensors, ErrInvalidDataFormat
	}

	// Transaction
	tx, err := conn.Begin()
	if err != nil {
		return 0, 0, 0, err
	}
	defer tx.Close()

	var reconnMsg []*notifications.Notification

	for _, entity := range data {
		nodeData, ok := entity.(map[string]any)
		if !ok {
			return recorded, nodes, sensors, ErrInvalidDataFormat
		}

		nodeID, ok := nodeData["node_id"].(string)
		if !ok {
			return recorded, nodes, sensors, fmt.Errorf("missing 'node_id'")
		}

		// 장치에 대한 재연결 상태 확인
		if msg := checkReconnected(tx, nodeID, nodeData); msg != nil {
			reconnMsg = append(reconnMsg, msg)
		}

		// 채널 데이터
		nrChannel := 0
		for k, v := range nodeData {
			switch k {
			case "node_id":
				continue

			case "rssi":
				value, ok := v.([]any)
				if ok {
					processRssi(tx, payload.SiteId, nodeID, value)
				}
				continue
			}

			// 센서 확인
			query := tx.Model((*devices.Sensor)(nil))
			query.Where("device_id = ?", nodeID)
			query.Where("channel_id = ?", k)
			exists, err := query.Exists()
			if err != nil {
				return recorded, nodes, sensors, err
			}

			if !exists {
				log.Warnf("Cannot find node %q or channel %q", nodeID, k)
				continue
			}

			if value, ok := v.([]any); ok {
				// 채널에 대한 임계치 확인
				sensorLimit := make(map[string]*devices.SensorLimit)
				if existLimitTbl {
					query := tx.Model((*devices.SensorLimit)(nil))
					query.Where("device_id = ?", nodeID)
					query.Where("channel = ?", k)
					query.ForEach(func(tuple *devices.SensorLimit) error {
						sensorLimit[tuple.Attribute] = proto.Clone(tuple).(*devices.SensorLimit)
						return nil
					})
				}

				rec, err := processSensor(tx, payload.SiteId, payload.GatewayId, nodeID, k, value, sensorLimit)
				if err != nil {
					if err != ErrNoData {
						return recorded, nodes, sensors, err
					}
				} else {
					sensors++
					recorded += rec
				}
				nrChannel++
			} else {
				return recorded, nodes, sensors, ErrInvalidDataFormat
			}
		}
		nodes++
	}

	// Commit
	if err = tx.Commit(); err != nil {
		return
	}

	// 재연결 메시지 전송
	for _, msg := range reconnMsg {
		msg.Send(context.TODO())
	}

	return recorded, nodes, sensors, nil
}

// 채널 데이터 처리를 위한 타입
type ChannelData struct {
	siteID     string
	nodeID     string
	channel    uint32
	sensorType string
	nrProbe    uint32
	multiProbe bool
	alert      map[string]*notifications.Notification
	attributes []*devices.SensorTypeAttribute
	origin     map[string]map[time.Time][]any
	tuples     map[string]map[time.Time][]string
	invalid    map[string]map[time.Time]bool
	limits     map[string]*devices.SensorLimit
}

// 센서 데이터 처리
func processSensor(tx *pg.Tx, siteID, gatewayID, nodeID, channel string, payload []any, limits map[string]*devices.SensorLimit) (int, error) {
	if len(payload) == 0 {
		return 0, nil
	}

	cd := &ChannelData{
		siteID:  siteID,
		nodeID:  nodeID,
		alert:   make(map[string]*notifications.Notification),
		origin:  make(map[string]map[time.Time][]any),
		tuples:  make(map[string]map[time.Time][]string),
		invalid: make(map[string]map[time.Time]bool),
		limits:  limits,
	}

	// 채널 정보 확인
	query := tx.Model((*devices.Sensor)(nil)).Column("sensor_type", "sensor_id", "probes")
	query.Where("device_id = ?", nodeID)
	query.Where("channel_id = ?", channel)
	var sensorID string
	if err := query.Select(&cd.sensorType, &sensorID, &cd.nrProbe); err != nil {
		return 0, err
	}

	// 센서 타입 정보 조회
	if err := tx.Model((*devices.SensorType)(nil)).Where("type_id = ?", cd.sensorType).Column("multi_probe").Select(&cd.multiProbe); err != nil {
		return 0, err
	}

	var columns []string
	if cd.multiProbe {
		columns = append(columns, "probe")
	} else {
		cd.nrProbe = 0
	}

	boolColumn := map[string]int64{} // bit array 확인 용도

	// 채널 정보 조회
	if err := tx.Model((*devices.SensorTypeAttribute)(nil)).Where("type_id = ?", cd.sensorType).
		Order("attribute").
		ForEach(func(tuple *devices.SensorTypeAttribute) error {
			cd.attributes = append(cd.attributes, proto.Clone(tuple).(*devices.SensorTypeAttribute))
			columns = append(columns, tuple.Attribute)
			if tuple.TypeName == "boolean" {
				boolColumn[tuple.Attribute] = -1
			}
			return nil
		}); err != nil {
		return 0, err
	}

	ch, err := strconv.ParseUint(channel, 10, 32)
	if err != nil {
		log.Warn("Cannot convert channel", "error", err)
	}

	// 데이터 처리
	for _, entity := range payload {
		data, ok := entity.(map[string]any)
		if !ok {
			continue
		}

		// 비정상 데이터인지 확인
		var invalid bool
		if tmp, ok := data["invalid"].(bool); ok {
			invalid = tmp
		}
		delete(data, "invalid")

		// 시리즈 데이터
		var samplingRate time.Duration
		temp, isArray := data["sampling_rate"]
		delete(data, "sampling_rate")
		if isArray {
			tmp, err := strconv.ParseInt(fmt.Sprintf("%v", temp), 10, 64)
			if err != nil {
				return 0, ErrInvalidDataFormat
			}
			samplingRate = time.Millisecond * (time.Duration)(tmp)
		}

		// 측정 시간 확인
		var ts time.Time
		if value, ok := data["ts"]; ok {
			delete(data, "ts")
			var tempTS string
			switch value.(type) {
			case uint64, uint32, int64, int32, int:
				tempTS = fmt.Sprintf("%d", value)
			case float64, float32:
				tempTS = fmt.Sprintf("%f", value)
				tempTS = tempTS[0:strings.Index(tempTS, ".")]
			default:
				tempTS = fmt.Sprintf("%v", value)
			}

			tmp, err := strconv.ParseInt(tempTS, 10, 64)
			if err != nil {
				log.Errorf("Invalid format of ts %q: %s", tempTS, err.Error())
				continue
			}

			if time.Now().Add(-720*time.Hour).UnixMilli() > tmp {
				return 0, ErrInvalidTimestamp
			}

			ts = time.UnixMilli(tmp)
		} else {
			ts = time.Now()
		}

		isBitArray := false
		for key := range boolColumn {
			tmp := fmt.Sprint(data[key])
			if strings.HasPrefix(strings.ToLower(tmp), "0x") {
				boolColumn[key], err = strconv.ParseInt(tmp[2:], 16, 64)
				isBitArray = true
			} else {
				boolColumn[key] = -1
			}
		}
		if isBitArray {
			cd.processBitArray(ts, boolColumn, data)
			continue
		}

		// 데이터 처리 함수
		parseData := func(name, typeName string, contents map[string]any, probe string) error {
			value, ok := contents[name]
			if !ok {
				return ErrInvalidDataFormat
			}

			if _, ok := cd.tuples[probe]; !ok {
				cd.origin[probe] = make(map[time.Time][]any)
				cd.tuples[probe] = make(map[time.Time][]string)
				cd.invalid[probe] = make(map[time.Time]bool)
			}

			if isArray {
				arrayValue, ok := value.([]any)
				if !ok {
					return ErrInvalidDataFormat
				}

				start := ts
				for _, v := range arrayValue {
					cd.origin[probe][start] = append(cd.origin[probe][start], v)
					cd.tuples[probe][start] = append(cd.tuples[probe][start], fmt.Sprintf("'%v'::%s", v, typeName))
					cd.invalid[probe][start] = invalid
					cd.checkLimit(tx, name, start, v, probe)
					start = start.Add(samplingRate)
				}
			} else {
				cd.origin[probe][ts] = append(cd.origin[probe][ts], value)
				cd.tuples[probe][ts] = append(cd.tuples[probe][ts], fmt.Sprintf("'%v'::%s", value, typeName))
				cd.invalid[probe][ts] = invalid
				cd.checkLimit(tx, name, ts, value, probe)
			}

			return nil
		}

		for _, columnType := range cd.attributes {
			name := columnType.Attribute
			typeName := columnType.TypeName
			if cd.multiProbe {
				for probe, probeData := range data {
					if probe == "ts" {
						continue
					}

					contents, ok := probeData.(map[string]any)
					if !ok {
						return 0, ErrInvalidDataFormat
					}

					if err := parseData(name, typeName, contents, probe); err != nil {
						return 0, err
					}
				}
			} else {
				if err := parseData(name, typeName, data, "NULL"); err != nil {
					return 0, err
				}
			}

			// 발견된 알림이 없으면 정상 상태로 변경
			if _, ok := cd.alert[fmt.Sprintf("%s:%s", nodeID, channel)]; ch > 0 && !ok {
				if err := changeDeviceStatus(tx, nodeID, uint32(ch), devices.DeviceStatus_NORMAL); err != nil {
					log.Warn("Cannot change status to %s", "error", err)
				}
			}
		}
	}

	if len(cd.tuples) == 0 {
		return 0, ErrNoData
	}

	// 쿼리 작성
	var values []string
	for probe, data := range cd.tuples {
		for ts, tuple := range data {
			invalid := cd.invalid[probe][ts]
			if cd.multiProbe {
				values = append(values, fmt.Sprintf("('%s', '%s', '%s', %s, %s, %v)", ts.Format(time.RFC3339Nano), siteID, sensorID, probe, strings.Join(tuple, ", "), invalid))
			} else {
				values = append(values, fmt.Sprintf("('%s', '%s', '%s', %s, %v)", ts.Format(time.RFC3339Nano), siteID, sensorID, strings.Join(tuple, ", "), invalid))
			}
		}
	}

	// NATS에 이벤트로 기록
	for probe, data := range cd.origin {
		payload := map[string]any{
			"site_id":     siteID,
			"sensor_id":   sensorID,
			"sensor_typr": cd.sensorType,
			"modbus":      ch,
		}

		for ts, tuple := range data {
			payload["ts"] = ts.Format(time.RFC3339Nano)
			payload["invalid"] = cd.invalid[probe][ts]
			if cd.multiProbe {
				payload["channel"] = probe
			}
			for i, v := range tuple {
				payload[columns[i]] = v
			}

			event, err := structpb.NewStruct(payload)
			if err != nil {
				log.Error("Failed to create event data", "error", err)
				continue
			}

			rawdata, err := proto.Marshal(event)
			if err != nil {
				log.Error("Failed to marshalling event data", "error", err)
				continue
			}

			// 이벤트 전송
			if err := async.PushEvent(context.Background(), async.Event_create, rawdata); err != nil {
				log.Error("Failed to push event", "error", err)
			}
		}
	}

	insertQuery := fmt.Sprintf("INSERT INTO %s (ts, site_id, sensor_id, %s, invalid) VALUES %s", cd.sensorType, strings.Join(columns, ", "), strings.Join(values, ", "))
	res, err := tx.Exec(insertQuery)
	if err != nil {
		return 0, err
	}

	// 알림 발송
	for _, noti := range cd.alert {
		if err := noti.Send(context.TODO()); err != nil {
			log.Warn(err)
		}
	}

	// 채널 데이터 수신 확인
	if ch > 0 {
		if _, err := tx.Model(&collects.LastReceivedHistory{
			DeviceId:  nodeID,
			Channel:   uint32(ch),
			GatewayId: gatewayID,
		}).OnConflict("(device_id, channel) DO UPDATE").
			Set("received_at = NOW()").Insert(); err != nil {
			log.Warn("Failed to update received time", "error", err)
		}
	}

	return res.RowsAffected(), nil
}

// RSSI 값 처리
func processRssi(tx *pg.Tx, siteID, nodeID string, entities []any) {
	for i, entity := range entities {
		data, ok := entity.(map[string]any)
		if !ok {
			continue
		}

		log.Debugf("Device (%T)%s: (%T)%f", data["device"], data["device"], data["rssi"], data["rssi"])

		// 장치 ID 확인
		var deviceID string
		if err := tx.Model((*devices.Device)(nil)).Column("device_id").
			Where(fmt.Sprintf("device_id LIKE '%%%s'", data["device"])).
			Join("JOIN site_devices USING (device_id)").
			Where("device_role IN (?, ?, ?)", devices.DeviceRole_GATEWAY, devices.DeviceRole_NODEGATEWAY, devices.DeviceRole_REPEATER).
			Where("site_id = ?", siteID).
			Limit(1).
			Select(&deviceID); err != nil {
			log.Warn("Cannot find device ID", "error", err)
			continue
		}

		// RSSI 기록
		if _, err := tx.Model(&collects.ReceiveRssiHistory{
			NodeId:   nodeID,
			Index:    int32(i) + 1,
			DeviceId: deviceID,
			Rssi:     int32(data["rssi"].(float64)),
		}).OnConflict("DO NOTHING").Insert(); err != nil {
			log.Warn("Failed to write RSS ", "error", err)
		}
	}
}

// bool 타입에 대한 bit array 처리
func (cd *ChannelData) processBitArray(ts time.Time, boolColumn map[string]int64, contents map[string]any) {
	log.Debug("process BitArray data")
	// probe 별 bit array
	tuple := make(map[int][]string)
	for _, columnType := range cd.attributes {
		name := columnType.Attribute
		typeName := columnType.TypeName
		if value, ok := boolColumn[name]; ok {
			for i := 0; i < int(cd.nrProbe); i++ {
				if value>>i&0x00000001 == 1 {
					tuple[i+1] = append(tuple[i+1], "TRUE")
				} else {
					tuple[i+1] = append(tuple[i+1], "FALSE")
				}
			}
		} else {
			for i := 0; i < int(cd.nrProbe); i++ {
				tuple[i+1] = append(tuple[i+1], fmt.Sprintf("'%v'::%s", contents[name], typeName))
			}
		}
	}

	// 프로브 데이터 처리
	for p, value := range tuple {
		cd.tuples[fmt.Sprint(p)] = map[time.Time][]string{
			ts: value,
		}
	}
}

// 임계치 확인
func (cd *ChannelData) checkLimit(tx *pg.Tx, name string, ts time.Time, value any, probe string) {
	targetID := fmt.Sprintf("%s:%d", cd.nodeID, cd.channel)
	if limit, ok := cd.limits[name]; ok {
		tmp, err := strconv.ParseFloat(fmt.Sprint(value), 64)
		if err != nil {
			log.Warn("Cannot convert float64", "error", err)
			return
		}

		noti := &notifications.Notification{
			TargetId: targetID,
			Variable: &structpb.Struct{
				Fields: map[string]*structpb.Value{
					"site_id":   structpb.NewStringValue(cd.siteID),
					"device_id": structpb.NewStringValue(cd.nodeID),
					"channel":   structpb.NewStringValue(fmt.Sprint(cd.channel)),
					// "sensor_type": structpb.NewStringValue(cd.sensorType),
					"attribute":   structpb.NewStringValue(name),
					"value":       structpb.NewNumberValue(tmp),
					"normal_min":  structpb.NewNumberValue(limit.NormalMin),
					"normal_max":  structpb.NewNumberValue(limit.NormalMax),
					"caution_min": structpb.NewNumberValue(limit.CautionMin),
					"caution_max": structpb.NewNumberValue(limit.CautionMax),
					"occurred_at": structpb.NewStringValue(ts.Format(time.RFC3339)),
				},
			},
		}

		if probe != "NULL" {
			noti.Variable.Fields["probe"] = structpb.NewStringValue(probe)
		}

		if _, ok := cd.alert[noti.TargetId]; ok {
			return
		}

		switch {
		case
			tmp < limit.NormalMin && tmp >= limit.CautionMin,
			tmp > limit.NormalMax && tmp <= limit.CautionMax:
			noti.TemplateId = "out-of-normal-range"
			cd.alert[noti.TargetId] = noti
			if cd.channel > 0 {
				if err := changeDeviceStatus(tx, cd.nodeID, cd.channel, devices.DeviceStatus_CAUTION); err != nil {
					log.Warn("Cannot change status to %s", "error", err)
				}
			}

		case
			tmp < limit.CautionMin,
			tmp > limit.CautionMax:
			noti.TemplateId = "out-of-caution-range"
			cd.alert[noti.TargetId] = noti
			if cd.channel > 0 {
				if err := changeDeviceStatus(tx, cd.nodeID, cd.channel, devices.DeviceStatus_WARNING); err != nil {
					log.Warn("Cannot change status to %s", "error", err)
				}
			}
		}
	}
}
