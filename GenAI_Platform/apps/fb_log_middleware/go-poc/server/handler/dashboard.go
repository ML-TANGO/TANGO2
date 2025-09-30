package handler

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"strings"
	"time"

	pb "acryl.ai/go-poc/proto/logquery"
	"acryl.ai/go-poc/server/utils"
	"github.com/elastic/go-elasticsearch/v8"
)

type DashboardServer struct {
	pb.UnimplementedLogQueryServiceServer
	esClient *elasticsearch.Client
}

func NewDashboardServer(esClient *elasticsearch.Client) *DashboardServer {
	return &DashboardServer{esClient: esClient}
}

func (s *DashboardServer) SummaryLogsQuery(ctx context.Context, query string) (*pb.SummaryLogsResponse, error) {
	//log.Printf("%s", query)
	res, err := s.esClient.Search(
		s.esClient.Search.WithContext(ctx),
		s.esClient.Search.WithIndex("*usage*"),
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
			log.Printf("[%s] %s: %s",
				res.Status(),
				e["error"].(map[string]interface{})["type"],
				e["error"].(map[string]interface{})["reason"],
			)
		}
		return nil, fmt.Errorf("error response from ElasticSearch")
	}

	var r map[string]interface{}
	if err := json.NewDecoder(res.Body).Decode(&r); err != nil {
		log.Printf("[JFB/ERROR] (MLS)Error parsing the response body: %v", err)
		log.Printf("MultilineEnd")
		return nil, err
	}

	//log.Printf("ElasticSearch query returned %d hits", int(r["hits"].(map[string]interface{})["total"].(map[string]interface{})["value"].(float64)))

	var logs []*pb.LogEntry
	for _, hit := range r["hits"].(map[string]interface{})["hits"].([]interface{}) {
		source := hit.(map[string]interface{})["_source"]
		logEntry := &pb.LogEntry{Fields: make(map[string]string)}
		for k, v := range source.(map[string]interface{}) {
			if !strings.HasPrefix(k, "_") {
				// Replace @timestmp to time_stamp
				if k == "@timestamp" {
					k = "time_stamp"
				}
				logEntry.Fields[k] = fmt.Sprintf("%v", v)
			}
		}
		logs = append(logs, logEntry)
	}

	totalCount, _ := r["hits"].(map[string]interface{})["total"].(map[string]interface{})["value"].(float64)
	return &pb.SummaryLogsResponse{
		Logs:         logs,
		TotalCount:   int64(totalCount),
		CurrentCount: int32(len(logs)),
	}, nil
}

func (s *DashboardServer) QueryWorkspaceDashboardLogs(ctx context.Context, req *pb.WorkspaceDashboardRequest) (*pb.SummaryLogsResponse, error) {
	/*   string workspace = 1;
	string timespan = 2; // default 1w
	string startTime = 3;
	int32 count = 4; // default 10
	int64 offset = 5;
	bool ascending = 6;
	*/
	workspace := req.Workspace
	timespan := req.Timespan
	startTime := req.StartTime
	count := req.Count
	offset := req.Offset
	ascending := req.Ascending

	if count == 0 {
		count = 10
	}
	sortOrder := "desc"
	if ascending {
		sortOrder = "asc"
	}

	// Calculate the time range if startTime is empty
	if startTime == "" {
		if timespan == "" {
			timespan = "1w"
		}
		parsedTime, err := utils.CalculateTimeAgo(timespan)
		if err != nil {
			fmt.Printf("Error parsing timespan %s: %v\n", timespan, err)
			return nil, err
		}
		timeformat := time.RFC3339
		startTime = parsedTime.Format(timeformat)
	}

	//log.Printf("Querying logs from %s to now", startTime)
	query := fmt.Sprintf(`{
		"from": %d,
		"size": %d,
		"query": {
			"bool": {
				"filter": [
					{"range": { "@timestamp": { "gte": "%s" } }},
					{"term": { "workspace.keyword": "%s" }}
				]
			}
		},
		"sort": [ { "@timestamp": {"order": "%s" } }, "_doc" ],
		"_source": {
			"includes": [
				"workspace", "task", "task_name", "update_details", "user", "action", "@timestamp"
			]
		}
	}`, offset, count, startTime, workspace, sortOrder)

	return s.SummaryLogsQuery(ctx, query)
}

func (s *DashboardServer) QueryAdminDashboardLogs(ctx context.Context, req *pb.AdminDashboardRequest) (*pb.SummaryLogsResponse, error) {
	timespan := req.Timespan
	startTime := req.StartTime
	count := req.Count
	offset := req.Offset
	ascending := req.Ascending

	if count == 0 {
		count = 10
	}
	sortOrder := "desc"
	if ascending {
		sortOrder = "asc"
	}

	// Calculate the time range if startTime is empty
	if startTime == "" {
		if timespan == "" {
			timespan = "1w"
		}
		parsedTime, err := utils.CalculateTimeAgo(timespan)
		if err != nil {
			fmt.Printf("Error parsing timespan %s: %v\n", timespan, err)
			return nil, err
		}
		timeformat := time.RFC3339
		startTime = parsedTime.Format(timeformat)
	}

	//log.Printf("Querying logs from %s to now", startTime)
	query := fmt.Sprintf(`{
		"from": %d,
		"size": %d,
		"query": {
			"bool": {
				"filter": [
					{"range": { "@timestamp": { "gte": "%s" } }}
				]
			}
		},
		"sort": [ { "@timestamp": "%s" } ],
		"_source": {
			"includes": [
				"workspace", "task", "task_name", "update_details", "user", "action", "@timestamp"
			]
		}
	}`, offset, count, startTime, sortOrder)

	return s.SummaryLogsQuery(ctx, query)
}

func (s *DashboardServer) QueryAdminDetailLogs(ctx context.Context, req *pb.AdminDetailRequest) (*pb.SummaryLogsResponse, error) {
	timespan := req.Timespan
	startTime := req.StartTime
	count := req.Count
	offset := req.Offset
	ascending := req.Ascending
	action := req.Action
	task := req.Task

	if count == 0 {
		count = 10
	}
	sortOrder := "desc"
	if ascending {
		sortOrder = "asc"
	}

	// Calculate the time range if startTime is empty
	if startTime == "" {
		if timespan == "" {
			timespan = "1w"
		}
		parsedTime, err := utils.CalculateTimeAgo(timespan)
		if err != nil {
			fmt.Printf("Error parsing timespan %s: %v\n", timespan, err)
			return nil, err
		}
		timeformat := time.RFC3339
		startTime = parsedTime.Format(timeformat)
	}

	filterTerm := ""
	if action != "" {
		filterTerm = fmt.Sprintf(` {"term": {"action.keyword": "%s"}} `, action)
	}
	if task != "" {
		if filterTerm != "" {
			filterTerm += ", "
		}
		filterTerm += fmt.Sprintf(` {"term": {"task.keyword": "%s"}} `, task)
	}

	if filterTerm != "" {
		filterTerm = fmt.Sprintf(`, %s`, filterTerm)
	}

	//log.Printf("Querying logs from %s to now", startTime)
	query := fmt.Sprintf(`{
		"from": %d,
		"size": %d,
		"query": {
			"bool": {
				"filter": [
					{"range": { "@timestamp": { "gte": "%s" } }} %s
				]
			}
		},
		"sort": [ { "@timestamp": "%s" } ],
		"_source": {
			"includes": [
				"workspace", "task", "task_name", "update_details", "user", "action", "@timestamp"
			]
		}
	}`, offset, count, startTime, filterTerm, sortOrder)

	return s.SummaryLogsQuery(ctx, query)
}
