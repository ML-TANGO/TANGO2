package devices

import (
	"time"

	"github.com/golang/protobuf/jsonpb"
	"google.golang.org/protobuf/runtime/protoiface"
)

var RequestMap = map[RequestCode]ResponseCode{
	RequestCode_get_certificate_req:        ResponseCode_get_certificate_resp,
	RequestCode_get_time_req:               ResponseCode_get_time_resp,
	RequestCode_get_latest_value_req:       ResponseCode_get_latest_value_resp,
	RequestCode_set_relay_req:              ResponseCode_set_relay_resp,
	RequestCode_get_data_req:               ResponseCode_get_data_resp,
	RequestCode_get_config_req:             ResponseCode_get_config_resp,
	RequestCode_set_config_req:             ResponseCode_set_config_resp,
	RequestCode_set_status_req:             ResponseCode_set_status_resp,
	RequestCode_set_agsmotor_req:           ResponseCode_set_agsmotor_resp,
	RequestCode_set_ags_action_req:         ResponseCode_set_ags_action_resp,
	RequestCode_set_ags_warn_req:           ResponseCode_set_ags_warn_resp,
	RequestCode_set_agsmotor_mode_req:      ResponseCode_set_agsmotor_mode_resp,
	RequestCode_set_agsmotor_operation_req: ResponseCode_set_agsmotor_operation_resp,
	RequestCode_set_agsmotor_error_req:     ResponseCode_set_agsmotor_error_resp,
	RequestCode_set_mc_switch_req:          ResponseCode_set_mc_switch_resp,
}

var ResponseMap = map[ResponseCode]RequestCode{
	ResponseCode_get_certificate_resp:        RequestCode_get_certificate_req,
	ResponseCode_get_time_resp:               RequestCode_get_time_req,
	ResponseCode_get_latest_value_resp:       RequestCode_get_latest_value_req,
	ResponseCode_set_relay_resp:              RequestCode_set_relay_req,
	ResponseCode_get_data_resp:               RequestCode_get_data_req,
	ResponseCode_get_config_resp:             RequestCode_get_config_req,
	ResponseCode_set_config_resp:             RequestCode_set_config_req,
	ResponseCode_set_status_resp:             RequestCode_set_status_req,
	ResponseCode_set_agsmotor_resp:           RequestCode_set_agsmotor_req,
	ResponseCode_set_ags_action_resp:         RequestCode_set_ags_action_req,
	ResponseCode_set_ags_warn_resp:           RequestCode_set_ags_warn_req,
	ResponseCode_set_agsmotor_mode_resp:      RequestCode_set_agsmotor_mode_req,
	ResponseCode_set_agsmotor_operation_resp: RequestCode_set_agsmotor_operation_req,
	ResponseCode_set_agsmotor_error_resp:     RequestCode_set_agsmotor_error_req,
	ResponseCode_set_mc_switch_resp:          RequestCode_set_mc_switch_req,
}

var marshaler = jsonpb.Marshaler{
	OrigName:     true,
	EnumsAsInts:  false,
	EmitDefaults: false,
}

// 기본 응답 처리
func MarshalResponse(command ResponseCode, sequence uint64, status uint32) (string, error) {
	jsonMarshaler := marshaler
	jsonMarshaler.EnumsAsInts = false
	return jsonMarshaler.MarshalToString(&CommandResponse{
		Command: command,
		Seq:     sequence,
		Status:  status,
	})
}

func MarshalGetTimeResponse(sequence uint64) (string, error) {
	current := time.Now()
	return marshaler.MarshalToString(&GetTimeResponse{
		Command:  ResponseCode_get_time_resp,
		Seq:      sequence,
		Ts:       uint64(current.UnixMilli()),
		Timezone: current.Location().String(),
	})
}

func (req *GetDataRequest) Marshal(sequence uint64) (string, error) {
	req.Command = RequestCode_get_data_req
	req.Seq = sequence
	return marshaler.MarshalToString(req)
}

func (req *SetConfigRequest) Marshal(sequence uint64) (string, error) {
	req.Command = RequestCode_set_config_req
	req.Seq = sequence
	return marshaler.MarshalToString(req)
}

func MarshalToString(msg protoiface.MessageV1) (string, error) {
	return marshaler.MarshalToString(msg)
}
