package server

import (
	"bytes"
	"context"
	"encoding/json"
	"text/template"
	"text/template/parse"

	"github.com/go-pg/pg/v10"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/proto"

	"gitlab.suredatalab.kr/beymons/facilities"
)

// ControlProduct - 제품 설정 조회 API
func (s FacilitiesServer) ControlProduct(ctx context.Context, req *facilities.ControlProductRequest) (*facilities.ControlProductResponse, error) {
	// DB 연결
	conn := pgorm.Conn()
	defer conn.Close()

	query := controlProductQuery(ctx, conn)
	query.Where("manufacture_id = ?", req.ManufactureId)
	query.Where("model_number = ?", req.ModelNumber)
	if len(req.ControlId) > 0 {
		query.Where("control_id = ?", req.ControlId)
	}

	var resp facilities.ControlProductResponse
	if err := query.ForEach(func(tuple *facilities.ProductControl) error {
		// 템플릿 파싱
		tmpl, err := template.New("test").Parse(tuple.Payload)
		if err != nil {
			return err
		}

		tuple.Channels = findChannels(tmpl, findVariables(tmpl.Root))
		resp.Entities = append(resp.Entities, proto.Clone(tuple).(*facilities.ProductControl))
		tuple = nil
		return nil
	}); err != nil {
		return nil, pgorm.GetError(ctx, err)
	}

	return &resp, nil
}

// 제품 제어 설정 쿼리
func controlProductQuery(ctx context.Context, conn *pg.Conn) *pg.Query {
	query := conn.ModelContext(ctx, (*facilities.ProductControl)(nil))
	query.Column("control_id", "manufacture_id", "model_number")
	query.Column("control_name", "modbus", "sensor_type")
	query.Column("command", "payload", "updated_at")

	// 센서 타입 조인
	query.Join("LEFT JOIN sensor_types").JoinOn("type_id = sensor_type")
	query.ColumnExpr("type_name AS sensor_type_name")
	return query
}

// 모든 변수들을 인덱스 번호로 치환하여 채널 정보를 찾는 함수
func validatePayload(payload string) error {
	// 템플릿 파싱
	tmpl, err := template.New("test").Parse(payload)
	if err != nil {
		return status.Errorf(codes.InvalidArgument, "Payload validation failed: %s", err.Error())
	}

	vars := findVariables(tmpl.Root)
	log.Debugf("vars: %v", vars)

	tempVars := make(map[string]any)
	for i, key := range vars {
		tempVars[key] = i
	}

	buf := &bytes.Buffer{}
	if err := tmpl.Execute(buf, tempVars); err != nil {
		return status.Errorf(codes.InvalidArgument, "Payload validation failed: %s", err.Error())
	}

	result := make(map[string]any)
	if err := json.Unmarshal(buf.Bytes(), &result); err != nil {
		return status.Errorf(codes.InvalidArgument, "Payload validation failed: %s", err.Error())
	}

	return nil
}

// 모든 변수들을 인덱스 번호로 치환하여 채널 정보를 찾는 함수
func findChannels(tmpl *template.Template, vars []string) []string {
	log.Debugf("vars: %v", vars)
	if vars == nil {
		return nil
	}

	tempVars := make(map[string]any)
	for i, key := range vars {
		tempVars[key] = i
	}

	buf := &bytes.Buffer{}
	if err := tmpl.Execute(buf, tempVars); err != nil {
		log.Warn("Failed to execute template", "error", err)
		return nil
	}

	result := make(map[string]any)
	if err := json.Unmarshal(buf.Bytes(), &result); err != nil {
		log.Warn("Failed to unmarshalling json", "error", err)
		return nil
	}

	keys := make([]string, 0, len(result))
	for k := range result {
		keys = append(keys, k)
	}

	log.Debugf("keys: %v", keys)
	return keys
}

// 재귀적으로 노드 트리를 탐색하여 변수를 찾는 함수
func findVariables(node parse.Node) []string {
	var variables []string

	switch n := node.(type) {
	case *parse.ListNode:
		for _, subNode := range n.Nodes {
			variables = append(variables, findVariables(subNode)...)
		}

	case *parse.ActionNode:
		for _, cmd := range n.Pipe.Cmds {
			for _, arg := range cmd.Args {
				if fn, ok := arg.(*parse.FieldNode); ok {
					name := fn.String()
					if len(name) > 0 {
						variables = append(variables, name[1:])
					}
				}
			}
		}
	}

	keys := make(map[string]bool)
	for _, name := range variables {
		keys[name] = true
	}

	variables = make([]string, 0, len(keys))
	for k := range keys {
		variables = append(variables, k)
	}

	return variables
}
