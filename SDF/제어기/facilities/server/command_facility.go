package server

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"sync"
	"sync/atomic"
	"text/template"
	"time"

	"github.com/go-pg/pg/v10"
	"gitlab.suredatalab.kr/sdlmicro/middleware/auth"
	"gitlab.suredatalab.kr/sdlmicro/middleware/errors"
	"gitlab.suredatalab.kr/sdlmicro/middleware/log"
	"gitlab.suredatalab.kr/sdlmicro/middleware/pgorm"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
	"google.golang.org/protobuf/types/known/structpb"

	"gitlab.suredatalab.kr/beymons/devices"
	"gitlab.suredatalab.kr/beymons/facilities"
)

// CommandFacility - 설비 상태 변경 API
func (s FacilitiesServer) CommandFacility(ctx context.Context, req *facilities.CommandFacilityRequest) (*facilities.CommandFacilityResponse, error) {
	// DB Connection
	conn := pgorm.Conn()
	defer conn.Close()

	var resp facilities.CommandFacilityResponse

	// 기존 정보 조회
	log.Debug("load origin model...")
	origin, err := getFacility(ctx, conn, req.FacilityId)
	if err != nil {
		return nil, err
	}

	if !origin.Writable {
		return nil, auth.ErrAccessDenied.Err()
	}

	switch req.Command.(type) {

	case *facilities.CommandFacilityRequest_Control_:
		resp.Count, err = sentFacilityCommand(ctx, conn, req.FacilityId, req.GetControl())
		if err != nil {
			return nil, err
		}
	}

	return &resp, nil
}

// 설비 제어 명령 전송
func sentFacilityCommand(ctx context.Context, conn *pg.Conn, id string, req *facilities.CommandFacilityRequest_Control) (uint32, error) {
	var (
		cmd     string
		// success uint32
		success atomic.Uint32
	)

	// Transaction
	tx, err := conn.Begin()
	if err != nil {
		return 0, log.InternalError(ctx, err)
	}
	defer tx.Close()

	command := make(map[string]*structpb.Struct)
	sequence := uint64(time.Now().UnixMilli())
	for _, controlID := range req.ControlId {
		// 제어 명령 조회
		control, err := getControlFacility(ctx, conn, id, controlID)
		if err != nil {
			return 0, err
		}

		if cmd == "" {
			cmd = control.Command
		} else if cmd != control.Command {
			return 0, errors.New(facilities.ErrCmdNotMatch)
		}

		if _, ok := command[control.DeviceId]; !ok {
			command[control.DeviceId] = &structpb.Struct{Fields: make(map[string]*structpb.Value)}
		}

		for _, name := range control.Attributes {
			if _, ok := req.Attributes[name]; !ok {
				return 0, errors.New(facilities.ErrMustSetField, "name", name)
			}
		}

		// 템플릿 파싱
		tmpl, err := template.New("test").Parse(control.Payload)
		if err != nil {
			return 0, status.Errorf(codes.InvalidArgument, "Payload validation failed: %s", err.Error())
		}

		buf := &bytes.Buffer{}
		if err := tmpl.Execute(buf, req.Attributes); err != nil {
			return 0, log.InternalError(ctx, err)
		}

		result := make(map[string]any)
		if err := json.Unmarshal(buf.Bytes(), &result); err != nil {
			return 0, log.InternalError(ctx, err)
		}

		payload, err := structpb.NewStruct(result)
		if err != nil {
			return 0, log.InternalError(ctx, err)
		}

		if _, ok := command[control.DeviceId].Fields[fmt.Sprint(control.Modbus)]; !ok {
			command[control.DeviceId].Fields[fmt.Sprint(control.Modbus)] = structpb.NewStructValue(payload)
		} else {
			fields := command[control.DeviceId].Fields[fmt.Sprint(control.Modbus)].GetStructValue()
			for k, v := range payload.Fields {
				fields.Fields[k] = v
			}
		}

		// 이력 기록
		history := &facilities.FacilityCommandHistory{
			FacilityId: id,
			ControlId:  controlID,
			DeviceId:   control.DeviceId,
			Command:    control.Command,
			Sequence:   sequence,
			Payload:    string(buf.Bytes()),
		}
		if _, err := conn.ModelContext(ctx, history).Insert(); err != nil {
			return 0, pgorm.GetError(ctx, err)
		}
	}

	// Commit Transaction
	if err = tx.Commit(); err != nil {
		return 0, log.InternalError(ctx, err)
	}

	wg := sync.WaitGroup{}
	wg.Add(len(command))
	var failed []error
	for deviceID, payload := range command {
		go func(id string) {
			// 명령 전송
			resp, err := devices.Client().Command(ctx, &devices.CommandRequest{
				DeviceId: id,
				Sequence: sequence,
				Command:  devices.CommandRequest_Command(devices.CommandRequest_Command_value[cmd]),
				Operand: &devices.CommandRequest_Payload{
					Payload: payload,
				},
			})
			if err != nil {
				log.Errorf("Failed to control of device %s: %s", id, err.Error())
				failed = append(failed, err)
			} else {
				success.Add(1)
				log.Debugf("Response %s: %v", id, resp)
			}
			wg.Done()
		}(deviceID)
	}

	wg.Wait()

	// 모든 명령 실패
	if success.Load() == 0 {
		switch len(failed) {
		case 0:
			return 0, errors.New(facilities.ErrControlUnknown)

		case 1:
			return 0, failed[0]

		default:
			var errMsg []string
			for _, err := range failed {
				errMsg = append(errMsg, err.Error())
				
			}
			return 0, status.Errorf(codes.Aborted, "An error occurred in some or all items within the requested operation:\n%s", strings.Join(errMsg, "\n"))
		}
	}

	return success.Load(), nil
}
