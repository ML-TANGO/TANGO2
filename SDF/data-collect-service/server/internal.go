package server

import (
	"context"
	"fmt"

	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/services/notifications"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

const (
	filterQuery   = "user_id IN (SELECT user_id FROM site_users JOIN site_devices USING (site_id) WHERE device_id = SPLIT_PART(_.target_id, ':', 1) %s)"
	varQuery      = "SELECT COALESCE(devices.display_name, device_id) device_name, COALESCE(sensors.display_name, channel_id::varchar) sensor_name, sensors.description FROM sensors JOIN devices USING (device_id) WHERE device_id = '{{.device_id}}'"
	OutOfRangeMsg = `{{.device_id}} 장치의 채널 {{.channel}} {{if .probe}} (probe: {{.probe}}) {{end}}에서 {{.attribute}} 기준값 초과
장치명: {{.device_name}}
센서명: {{.sensor_name}}
정상 범위: {{.normal_min}} ~ {{.normal_max}}
경고 범위: {{.caution_min}} ~ {{.caution_max}}
현재 값 : {{.value}}
발생시간: {{datetime .occurred_at "2006-01-02 15:04:05" .zoneinfo}} ({{.zoneinfo}})
센서 설명: {{.description}}`
)

func registerMsgTemplate(ctx context.Context) {
	templates := []*notifications.MessageTemplate{
		{
			TemplateId:      "disconnect-device",
			Event:           notifications.MessageTemplate_ERROR,
			Summary:         "통신 끊김 알림",
			Description:     "통신 끊김이 발견된 시간(occurred_at)을 입력으로 받는다.",
			ResendCycle:     6,
			ResendCycleUnit: notifications.MessageTemplate_hour,
			Method: []notifications.MessageTemplate_Method{
				notifications.MessageTemplate_BASIC,
				notifications.MessageTemplate_EMAIL,
			},
			Title: "[알람 발생] {{.target_id}} 통신 끊김 발생",
			Message: map[string]string{
				"text": `{{.target_id}} 통신 끊김 발생
발생시간: {{datetime .occurred_at "2006-01-02 15:04:05" .zoneinfo}} ({{.zoneinfo}})
{{if .sensors}} 센서:
{{range .sensors}} - {{.address}}: {{.sensor_type}}
{{end}}{{end}}`,
			},
			Filter: fmt.Sprintf(filterQuery, "AND role = 'manager'"),
		},
		{
			TemplateId:      "reconnect-device",
			Event:           notifications.MessageTemplate_INFO,
			Summary:         "통신 끊김 해제 알림",
			Description:     "통신이 재개된 시간(released_at)을 입력으로 받는다.",
			ResendCycle:     6,
			ResendCycleUnit: notifications.MessageTemplate_hour,
			Method: []notifications.MessageTemplate_Method{
				notifications.MessageTemplate_BASIC,
				notifications.MessageTemplate_EMAIL,
			},
			Title: "[알람 해제] {{.target_id}} 통신 재개",
			Message: map[string]string{
				"text": `{{.target_id}} 통신 재개
발생시간: {{datetime .occurred_at "2006-01-02 15:04:05" .zoneinfo}} ({{.zoneinfo}})
종료시간: {{datetime .released_at "2006-01-02 15:04:05" .zoneinfo}} ({{.zoneinfo}})
{{if .sensors}} 센서:
{{range .sensors}} - {{.address}}: {{.sensor_type}}
{{end}}{{end}}`,
			},
			Filter:        fmt.Sprintf(filterQuery, "AND role = 'manager'"),
			VariableQuery: "SELECT variable->'fields'->'occurred_at' AS occurred_at FROM notifications WHERE template_id = 'disconnect-device' AND target_id = '{{.target_id}}' ORDER BY created_at DESC LIMIT 1",
		},
		{
			TemplateId: "out-of-normal-range",
			Summary:    "[주의] 정상 범위 초과 알림",
			Description: `다음에 대한 입력을 받는다:
- 고객 ID(site_id)
- 장치 ID(device_id)
- 채널 (channel)
- 센서 타입(sensor_type)
- 수집 항목(attribute)
- 현재 값(value)
- 발생시간(occurred_at)
- 정상 범위 하한값(normal_min)
- 정상 범위 상한값(normal_max)
- 주의 범위 하한값(caution_min)
- 주의 범위 상한값(caution_max)`,
			Event:           notifications.MessageTemplate_WARN,
			ResendCycle:     1,
			ResendCycleUnit: notifications.MessageTemplate_hour,
			Method: []notifications.MessageTemplate_Method{
				notifications.MessageTemplate_BASIC,
				notifications.MessageTemplate_EMAIL,
			},
			Title: "[주의] {{.target_id}} 정상 범위 초과",
			Message: map[string]string{
				"text": OutOfRangeMsg,
			},
			Filter:        fmt.Sprintf(filterQuery, ""),
			VariableQuery: varQuery,
		},
		{
			TemplateId: "out-of-caution-range",
			Summary:    "[경고] 정상 범위 초과 알림",
			Description: `다음에 대한 입력을 받는다:
- 고객 ID(site_id)
- 장치 ID(device_id)
- 채널 (channel)
- 센서 타입(sensor_type)
- 수집 항목(attribute)
- 현재 값(value)
- 발생시간(occurred_at)
- 정상 범위 하한값(normal_min)
- 정상 범위 상한값(normal_max)
- 주의 범위 하한값(caution_min)
- 주의 범위 상한값(caution_max)`,
			Event:           notifications.MessageTemplate_ERROR,
			ResendCycle:     1,
			ResendCycleUnit: notifications.MessageTemplate_hour,
			Method: []notifications.MessageTemplate_Method{
				notifications.MessageTemplate_BASIC,
				notifications.MessageTemplate_EMAIL,
			},
			Title: "[경고] {{.target_id}} 정상 범위 초과",
			Message: map[string]string{
				"text": OutOfRangeMsg,
			},
			Filter:        fmt.Sprintf(filterQuery, ""),
			VariableQuery: varQuery,
		},
	}

	for _, tmpl := range templates {
		if _, err := notifications.Client().CreateTemplate(ctx, tmpl); err != nil && status.Code(err) != codes.AlreadyExists {
			log.Error("Failed to create message template", "error", err)
		}
	}
}
