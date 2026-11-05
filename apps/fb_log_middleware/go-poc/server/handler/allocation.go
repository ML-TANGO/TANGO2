package handler

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"strconv"
	"strings"
	"time"
	_ "time/tzdata"

	pb "acryl.ai/go-poc/proto/logquery"
	"github.com/elastic/go-elasticsearch/v8"
)

type AllocationServer struct {
	pb.UnimplementedLogQueryServiceServer
	esClient *elasticsearch.Client
}

func NewAllocationServer(esClient *elasticsearch.Client) *AllocationServer {
	return &AllocationServer{esClient: esClient}
}

func (s *AllocationServer) AllocationLogsQuery(ctx context.Context, query string) (*map[string]interface{}, error) {
	//log.Printf("%s", query)

	res, err := s.esClient.Search(
		s.esClient.Search.WithContext(ctx),
		s.esClient.Search.WithIndex("*jonathan-usage*"),
		s.esClient.Search.WithBody(strings.NewReader(query)),
		s.esClient.Search.WithTrackTotalHits(true),
		s.esClient.Search.WithPretty(),
	)
	if err != nil {
		log.Printf("[JFB/ERROR] (MLS) Error querying ElasticSearch: %v", err)
		log.Printf("%s", err)
		log.Printf("MultilineEnd")
		return nil, err
	}
	defer res.Body.Close()

	if res.IsError() {
		var e map[string]interface{}
		if err := json.NewDecoder(res.Body).Decode(&e); err != nil {
			log.Printf("[JFB/ERROR] (MLS) Error parsing the response body: %v", err)
			log.Printf("MultilineEnd")
		} else {
			log.Printf("[JFB/ERROR] [%s] %s: %s",
				res.Status(),
				e["error"].(map[string]interface{})["type"],
				e["error"].(map[string]interface{})["reason"],
			)
		}
		return nil, fmt.Errorf("error response from ElasticSearch")
	}

	var r map[string]interface{}
	if err := json.NewDecoder(res.Body).Decode(&r); err != nil {
		log.Printf("Error parsing the response body: %v", err)
		return nil, err
	}

	//log.Printf("ElasticSearch query returned %d hits", int(r["hits"].(map[string]interface{})["total"].(map[string]interface{})["value"].(float64)))

	return &r, nil
}

func GetAllocationQueryFilters(workspaceName string, usageType string, startTime string, endTime string, searchKey string, searchTerm string) ([]map[string]interface{}, error) {
	filter := []map[string]interface{}{
		{
			"term": map[string]interface{}{
				"log_type.keyword": "allocation",
			},
		},
	}

	if workspaceName != "" {
		// 다양한 데이터 구조를 모두 처리하기 위해 bool should 쿼리 사용
		filter = append(filter, map[string]interface{}{
			"bool": map[string]interface{}{
				"should": []map[string]interface{}{
					// 1. 개별 필드로 저장된 경우
					{
						"term": map[string]interface{}{
							"workspace_name.keyword": workspaceName,
						},
					},
					// 2. allocation_info 객체 내에 저장된 경우
					{
						"term": map[string]interface{}{
							"allocation_info.workspace_name.keyword": workspaceName,
						},
					},
					// 3. allocation_info.raw 문자열 내에 저장된 경우
					{
						"wildcard": map[string]interface{}{
							"allocation_info.raw.keyword": "*\"workspace_name\":\"" + workspaceName + "\"*",
						},
					},
					// 4. allocation_info 문자열 내에 저장된 경우 (기존 방식)
					{
						"wildcard": map[string]interface{}{
							"allocation_info.keyword": "*\"workspace_name\":\"" + workspaceName + "\"*",
						},
					},
				},
				"minimum_should_match": 1,
			},
		})
	}

	if usageType != "" {
		// 다양한 데이터 구조를 모두 처리하기 위해 bool should 쿼리 사용
		filter = append(filter, map[string]interface{}{
			"bool": map[string]interface{}{
				"should": []map[string]interface{}{
					// 1. 개별 필드로 저장된 경우
					{
						"term": map[string]interface{}{
							"type.keyword": usageType,
						},
					},
					// 2. allocation_info 객체 내에 저장된 경우
					{
						"term": map[string]interface{}{
							"allocation_info.type.keyword": usageType,
						},
					},
					// 3. allocation_info.raw 문자열 내에 저장된 경우
					{
						"wildcard": map[string]interface{}{
							"allocation_info.raw.keyword": "*\"type\":\"" + usageType + "\"*",
						},
					},
					// 4. allocation_info 문자열 내에 저장된 경우 (기존 방식)
					{
						"wildcard": map[string]interface{}{
							"allocation_info.keyword": "*\"type\":\"" + usageType + "\"*",
						},
					},
				},
				"minimum_should_match": 1,
			},
		})
	}

	if startTime != "" && endTime != "" {
		startTime, err := time.Parse("2006-01-02 15:04:05", startTime)
		if err != nil {
			log.Printf("Error parsing start time: %s", err)
			return nil, err
		}
		endTime, err := time.Parse("2006-01-02 15:04:05", endTime)
		if err != nil {
			log.Printf("Error parsing end time: %s", err)
			return nil, err
		}

		// 시간 범위 필터링은 @timestamp 사용 (allocation_info의 datetime 필드는 문자열 검색이 복잡함)
		filter = append(filter, map[string]interface{}{
			"range": map[string]interface{}{
				"@timestamp": map[string]interface{}{
					"gte": startTime.Format("2006-01-02T15:04:05Z"),
					"lte": endTime.Format("2006-01-02T15:04:05Z"),
				},
			},
		})
	}

	if searchKey != "" && searchTerm != "" {
		if searchKey == "workspace" {
			// workspace 검색 시 다양한 데이터 구조를 모두 처리
			filter = append(filter, map[string]interface{}{
				"bool": map[string]interface{}{
					"should": []map[string]interface{}{
						// 1. 개별 필드로 저장된 경우
						{
							"wildcard": map[string]interface{}{
								"workspace_name.keyword": "*" + searchTerm + "*",
							},
						},
						// 2. allocation_info 객체 내에 저장된 경우
						{
							"wildcard": map[string]interface{}{
								"allocation_info.workspace_name.keyword": "*" + searchTerm + "*",
							},
						},
						// 3. allocation_info.raw 문자열 내에 저장된 경우
						{
							"wildcard": map[string]interface{}{
								"allocation_info.raw.keyword": "*\"workspace_name\":\"*" + searchTerm + "*\"*",
							},
						},
						// 4. allocation_info 문자열 내에 저장된 경우 (기존 방식)
						{
							"wildcard": map[string]interface{}{
								"allocation_info.keyword": "*\"workspace_name\":\"*" + searchTerm + "*\"*",
							},
						},
					},
					"minimum_should_match": 1,
				},
			})
		}
	}

	return filter, nil
}

// [start, end] 구간에서
// 1번째 반환값: [rangeStart, rangeEnd] 기간 내의 전체 업타임을 초로 합산해 반환합니다.
// 2번째 반환값: [rangeStart, rangeEnd] 기간 내의 평일 월~금, 매일 09:00–18:00 사이에 해당하는 초를 합산해 반환합니다.
func calcOfficeHourSeconds(start, end, rangeStart, rangeEnd time.Time) (int64, int64) {
	// start/end: UTC
	// rangeStart/rangeEnd: KST(UTC+9)
	timeZone := time.FixedZone("KST", 9*60*60) // 타임존 반영, 의존성 고려하여 9시간 하드코딩

	start = start.In(timeZone)
	end = end.In(timeZone) // start와 end는 UTC로 들어오므로 KST로 변환

	var globalTotal, workTotal int64

	// 날짜 루프: start가 속한 날짜부터 end가 속한 날짜까지
	dayCursor := time.Date(start.Year(), start.Month(), start.Day(), 0, 0, 0, 0, timeZone)
	endDate := time.Date(end.Year(), end.Month(), end.Day(), 23, 59, 59, 0, timeZone)

	rangeStart = time.Date(rangeStart.Year(), rangeStart.Month(), rangeStart.Day(), 0, 0, 0, 0, timeZone)
	rangeEnd = time.Date(rangeEnd.Year(), rangeEnd.Month(), rangeEnd.Day(), 23, 59, 59, 0, timeZone)

	overlapStart := maxTime(start, rangeStart)
	overlapEnd := minTime(end, rangeEnd)
	if overlapStart.Before(overlapEnd) {
		globalTotal += int64(overlapEnd.Sub(overlapStart).Seconds())
	}

	for !dayCursor.After(endDate) {
		// 평일 체크
		wd := dayCursor.Weekday()

		if !dayCursor.Before(rangeStart) && !dayCursor.After(rangeEnd) && wd >= time.Monday && wd <= time.Friday {
			// 그 날의 업무시간 윈도우
			workStart := time.Date(dayCursor.Year(), dayCursor.Month(), dayCursor.Day(), 9, 0, 0, 0, timeZone)
			workEnd := time.Date(dayCursor.Year(), dayCursor.Month(), dayCursor.Day(), 18, 0, 0, 0, timeZone)

			// 구간 겹침 계산
			segStart := maxTime(start, workStart)
			segEnd := minTime(end, workEnd)
			if segStart.Before(segEnd) {
				// 실제 경과 시간 계산
				dur := segEnd.Sub(segStart)
				// 8시간(=8*time.Hour)보다 크면 8시간으로 강제 설정
				max := 8 * time.Hour
				if dur > max {
					dur = max
				}
				workTotal += int64(dur.Seconds())
			}

		}
		// 다음 날
		dayCursor = dayCursor.AddDate(0, 0, 1)
	}

	return globalTotal, workTotal
}

func maxTime(a, b time.Time) time.Time {
	if a.After(b) {
		return a
	}
	return b
}

func minTime(a, b time.Time) time.Time {
	if a.Before(b) {
		return a
	}
	return b
}

func (s *AllocationServer) QuerySummaryAllocationUptime(ctx context.Context, req *pb.SummaryAllocationUptimeRequest) (*pb.SummaryAllocationUptimeResponse, error) {
	workspaceName := req.WorkspaceName
	startTime := req.StartTime
	endTime := req.EndTime

	// 전체 문서 쿼리 진행, QueryAllocationHistory 활용
	queryStartTime := time.Now()
	logs := make([]*pb.LogEntry, 0)
	for {
		recentResult, err := s.QueryAllocationHistory(ctx, &pb.AllocationHistoryRequest{
			Workspace:  workspaceName,
			StartTime:  startTime,
			EndTime:    endTime,
			Count:      2000,
			Offset:     int64(len(logs)),
			UsageType:  "",
			SearchKey:  "",
			SearchTerm: "",
		})
		if err != nil {
			log.Printf("Error querying allocation history: %s", err)
			return nil, err
		}
		if recentResult == nil || len(recentResult.Logs) == 0 {
			break
		}
		logs = append(logs, recentResult.Logs...)
		if int64(len(logs)) >= recentResult.TotalCount {
			break
		}
	}

	//log.Printf("Total logs: %d", len(logs))
	//log.Printf("Total count: %d", recentResult.TotalCount)
	//log.Printf("Current count: %d", recentResult.CurrentCount)

	type ProjectKey struct {
		WorkspaceName string
		Type          string
		TypeDetail    string
	}

	// 결과 파싱
	workspaceMap := make(map[string]*pb.WorkspaceUptimeEntry)
	projectMap := make(map[ProjectKey]*pb.ProjectUptimeEntry)
	rangeStartTime, err := time.Parse("2006-01-02 15:04:05", startTime)
	if err != nil {
		log.Printf("Error parsing start time: %s", err)
		return nil, err
	}
	rangeEndTime, err := time.Parse("2006-01-02 15:04:05", endTime)
	if err != nil {
		log.Printf("Error parsing end time: %s", err)
		return nil, err
	}
	for _, logEntry := range logs {
		current_period := logEntry.Fields["period"]
		end_datetime := logEntry.Fields["end_datetime"]

		//log.Printf("allocation_info.period: %s", current_period)

		// period와 end_datetime가 유효한지 확인
		if current_period == "" || current_period == "<nil>" || end_datetime == "" || end_datetime == "<nil>" {
			// 유효하지 않은 엔트리는 건너뛰기
			continue
		}
		
		// 정수형 확인
		current_period_int, err := strconv.Atoi(current_period)
		if err != nil {
			log.Printf("Error converting period to int: %s", err)
			continue
		}

		// allocation_info.end_datetime을 끝, allocation_info.period를 시간으로 하는 평일 9~6시 중 업타임 측정
		allocationEndTime, err := time.Parse("2006-01-02 15:04:05", end_datetime)
		if err != nil {
			log.Printf("Error parsing end time: %s", err)
			continue
		}

		allocationStartTime := allocationEndTime.Add(-time.Duration(current_period_int) * time.Second)
		globalPeriod, officeHourPeriod := calcOfficeHourSeconds(allocationStartTime, allocationEndTime, rangeStartTime, rangeEndTime)

		workspaceName := logEntry.Fields["workspace_name"]
		workspaceUptimeEntry, ok := workspaceMap[workspaceName]
		if !ok {
			workspaceUptimeEntry = &pb.WorkspaceUptimeEntry{
				WorkspaceName:           workspaceName,
				GlobalUptimeSeconds:     0,
				OfficeHourUptimeSeconds: 0,
			}
			workspaceMap[workspaceName] = workspaceUptimeEntry
		}
		workspaceUptimeEntry.GlobalUptimeSeconds += globalPeriod
		workspaceUptimeEntry.OfficeHourUptimeSeconds += officeHourPeriod

		// project_name 우선 사용, 없으면 type_detail 사용 (하위 호환성)
		projectName := logEntry.Fields["project_name"]
		if projectName == "" {
			projectName = logEntry.Fields["type_detail"]
		}
		
		projectKey := ProjectKey{
			WorkspaceName: workspaceName,
			Type:          logEntry.Fields["type"],
			TypeDetail:    projectName,
		}
		projectUptimeEntry, ok := projectMap[projectKey]
		if !ok {
			projectUptimeEntry = &pb.ProjectUptimeEntry{
				WorkspaceName:           workspaceName,
				Type:                    logEntry.Fields["type"],
				ProjectName:             projectName,
				GlobalUptimeSeconds:     0,
				OfficeHourUptimeSeconds: 0,
			}
			projectMap[projectKey] = projectUptimeEntry
		}
		projectUptimeEntry.GlobalUptimeSeconds += globalPeriod
		projectUptimeEntry.OfficeHourUptimeSeconds += officeHourPeriod
	}

	// 결과를 SummaryAllocationUptimeResponse로 변환하여 반환
	workspaceUptimeEntries := make([]*pb.WorkspaceUptimeEntry, 0)
	for _, entry := range workspaceMap {
		workspaceUptimeEntries = append(workspaceUptimeEntries, entry)
	}
	projectUptimeEntries := make([]*pb.ProjectUptimeEntry, 0)
	for _, entry := range projectMap {
		projectUptimeEntries = append(projectUptimeEntries, entry)
	}

	// 쿼리 성능 정보
	log.Printf("Uptime query processed %d workspaces, %d projects in %.2f ms", 
		len(workspaceUptimeEntries), len(projectUptimeEntries), 
		(time.Now().Sub(queryStartTime).Seconds() * 1000))
	
	return &pb.SummaryAllocationUptimeResponse{
		WorkspaceUptimes: workspaceUptimeEntries,
		ProjectUptimes:   projectUptimeEntries,
	}, nil
}

/*
	message AllocationHistoryRequest {
	  string workspace = 1;
	  string usageType = 2;
	  string startTime = 3;
	  string endTime = 4;
	  string searchKey = 5;
	  string searchTerm = 6;
	  int32 count = 7;
	  int64 offset = 8;
	}

	message AllocationHistoryResponse {
	  repeated LogEntry logs = 1;
	  int64 totalCount = 2;
	  int32 currentCount = 3;
	}
*/
func (s *AllocationServer) QueryAllocationHistory(ctx context.Context, req *pb.AllocationHistoryRequest) (*pb.AllocationHistoryResponse, error) {
	workspaceName := req.Workspace
	usageType := req.UsageType
	startTime := req.StartTime
	endTime := req.EndTime
	searchKey := req.SearchKey
	searchTerm := req.SearchTerm
	count := req.Count
	if count == 0 {
		count = 10
	}

	offset := req.Offset

	filter, err := GetAllocationQueryFilters(workspaceName, usageType, startTime, endTime, searchKey, searchTerm)
	if err != nil {
		log.Printf("Error getting query filters: %s", err)
		return nil, err
	}

	query := map[string]interface{}{
		"size": count,
		"from": offset,
		"query": map[string]interface{}{
			"bool": map[string]interface{}{
				"filter": filter,
			},
		},
		"sort": []map[string]interface{}{
			{
				"@timestamp": map[string]interface{}{
					"order": "desc",
				},
			},
		},
		"_source": map[string]interface{}{
			"includes": []string{
				"@timestamp",
				"workspace_name",
				"start_datetime", 
				"end_datetime",
				"period",
				"type",
				"type_detail",
				"project_name",
				"item_name",
				"item_type",
				"total_gpu_count",
				"total_used_cpu", 
				"total_used_ram",
				"instance_info.*",
				"allocation_info",  // 호환성을 위해 유지
			},
		},
	}

	// 쿼리 JSON으로 변환
	var buf bytes.Buffer
	if err := json.NewEncoder(&buf).Encode(query); err != nil {
		log.Printf("Error encoding query: %s", err)
		return nil, err
	}

	queryString, err := json.Marshal(query)
	if err != nil {
		log.Printf("Error marshaling query to string: %s", err)
		return nil, err
	}

	//log.Printf("Query: %s", queryString)

	resultMap, err := s.AllocationLogsQuery(ctx, string(queryString))
	if err != nil {
		log.Printf("Error querying allocation logs: %s", err)
		return nil, err
	}

	//log.Printf("Result: %v", resultMap)

	// 결과 파싱
	hits := (*resultMap)["hits"].(map[string]interface{})["hits"].([]interface{})
	if len(hits) == 0 {
		return &pb.AllocationHistoryResponse{
			Logs:         nil,
			TotalCount:   0,
			CurrentCount: 0,
		}, nil
	}

	logs := make([]*pb.LogEntry, 0)
	for _, hit := range hits {
		source := hit.(map[string]interface{})["_source"].(map[string]interface{})
		logEntry := &pb.LogEntry{Fields: make(map[string]string)}
		
		for k, v := range source {
			if !strings.HasPrefix(k, "_") {
				if k == "@timestamp" {
					k = "timestamp"
				}
				
				// allocation_info 처리 (다양한 데이터 구조 지원)
				if k == "allocation_info" {
					var allocationInfo map[string]interface{}
					
					// allocation_info가 문자열인 경우 JSON 파싱
					if allocationInfoStr, ok := v.(string); ok {
						// 먼저 JSON 파싱 시도
						if err := json.Unmarshal([]byte(allocationInfoStr), &allocationInfo); err != nil {
							// JSON 파싱 실패 시 Python dict 문자열을 JSON으로 변환
							jsonStr := strings.ReplaceAll(allocationInfoStr, "'", "\"")
							jsonStr = strings.ReplaceAll(jsonStr, "None", "null")
							jsonStr = strings.ReplaceAll(jsonStr, "True", "true")
							jsonStr = strings.ReplaceAll(jsonStr, "False", "false")
							
							if err := json.Unmarshal([]byte(jsonStr), &allocationInfo); err != nil {
								log.Printf("Failed to parse allocation_info string: %s", err)
								continue
							}
						}
						
					} else if allocationInfoObj, ok := v.(map[string]interface{}); ok {
						// allocation_info가 객체인 경우
						
						// allocation_info.raw 필드가 있는지 확인
						if rawValue, hasRaw := allocationInfoObj["raw"]; hasRaw {
							// raw 필드가 있으면 이를 파싱
							if rawStr, ok := rawValue.(string); ok {
								if err := json.Unmarshal([]byte(rawStr), &allocationInfo); err != nil {
									log.Printf("Failed to parse allocation_info.raw: %s", err)
									// raw 파싱 실패 시 기존 객체 사용
									allocationInfo = allocationInfoObj
								}
							} else {
								// raw가 문자열이 아닌 경우 기존 객체 사용
								allocationInfo = allocationInfoObj
							}
						} else {
							// raw 필드가 없으면 기존 객체 사용
							allocationInfo = allocationInfoObj
						}
					} else {
						log.Printf("allocation_info is neither string nor object: %T", v)
						continue
					}
					
					// 파싱된 allocation_info를 필드로 추가
					for kk, vv := range allocationInfo {
						// raw 필드는 제외 (이미 파싱했으므로)
						if kk == "raw" {
							continue
						}
						
						switch vv.(type) {
						case string:
							logEntry.Fields[kk] = vv.(string)
						case int8, uint8, int16, uint16, int32, uint32, int64, uint64:
							logEntry.Fields[kk] = fmt.Sprintf("%d", vv)
						case float32, float64:
							logEntry.Fields[kk] = fmt.Sprintf("%.0f", vv)
						case nil:
							// nil 값은 빈 문자열로 처리
							logEntry.Fields[kk] = ""
						case map[string]interface{}:
							// 중첩 객체는 문자열로 변환 (예: instance_info)
							logEntry.Fields[kk] = fmt.Sprintf("%v", vv)
						default:
							logEntry.Fields[kk] = fmt.Sprintf("%v", vv)
						}
					}
					continue
				}
				logEntry.Fields[k] = fmt.Sprintf("%v", v)
			}
		}
		logs = append(logs, logEntry)
	}

	return &pb.AllocationHistoryResponse{
		Logs:         logs,
		TotalCount:   int64((*resultMap)["hits"].(map[string]interface{})["total"].(map[string]interface{})["value"].(float64)),
		CurrentCount: int32(len(logs)),
	}, nil

}
