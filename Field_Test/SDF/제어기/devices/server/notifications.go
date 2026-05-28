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
	filterQuery = "user_id IN (SELECT user_id FROM site_users JOIN facilities USING (site_id) JOIN device_links l ON (l.target_id = facility_id::varchar AND kind = 'facilities' %s) WHERE device_id = _.target_id)"
)

func registerMsgTemplate(ctx context.Context) {
	templates := []*notifications.MessageTemplate{
		{
			TemplateId:      "ags-action-noti",
			Event:           notifications.MessageTemplate_INFO,
			Summary:         "모터 동작 완료 알림",
			ResendCycle:     0,
			ResendCycleUnit: notifications.MessageTemplate_hour,
			Method: []notifications.MessageTemplate_Method{
				notifications.MessageTemplate_BASIC,
				notifications.MessageTemplate_EMAIL,
			},
			Title: "[Beymons Green] {{.target}} 제어 동작이 완료되었습니다",
			Message: map[string]string{
				"text": `{{.target}} 제어 동작이 완료되었습니다
{{if .action_time}}제어 일시: {{.action_time}}
제어 동작을 {{if .dur_hour}}{{.dur_hour}}{{.hour}}{{end}} {{if .dur_min}}{{.dur_min}}{{.minute}}{{end}} {{if .dur_sec}}{{.dur_sec}}{{.second}}{{end}} 동안 수행했습니다.{{end}}
{{.message}}`,
				"html": `{{.target}} 제어 동작이 완료되었습니다
{{if .action_time}}제어 일시: {{.action_time}}
제어 동작을 {{if .dur_hour}}{{.dur_hour}}{{.hour}}{{end}} {{if .dur_min}}{{.dur_min}}{{.minute}}{{end}} {{if .dur_sec}}{{.dur_sec}}{{.second}}{{end}} 동안 수행했습니다.{{end}}
{{.message}}`,
			},
			Filter:        fmt.Sprintf(filterQuery, ""),
			VariableQuery: "SELECT '시간' AS hour, '분' AS minute, '초' AS second",
		},
		{
			TemplateId:      "ags-action-error",
			Event:           notifications.MessageTemplate_ERROR,
			Summary:         "모터 동작 이상 알림",
			ResendCycle:     0,
			ResendCycleUnit: notifications.MessageTemplate_hour,
			Method: []notifications.MessageTemplate_Method{
				notifications.MessageTemplate_BASIC,
				notifications.MessageTemplate_EMAIL,
			},
			Title: "[Beymons Green] {{.target}} 제어 모터를 확인 해 주세요",
			Message: map[string]string{
				"text": `{{.target}}의 제어 모터에 이상이 발생했습니다.
이상 발생 일시: {{.occurred_at}}
이상 발생 위치: {{.location}}
이상 발생 상황: {{.trouble}}`,
			},
			Filter: fmt.Sprintf(filterQuery, ""),
		},
	}

	for _, tmpl := range templates {
		if _, err := notifications.Client().CreateTemplate(ctx, tmpl); err != nil && status.Code(err) != codes.AlreadyExists {
			log.Error(err)
		}
	}
}
