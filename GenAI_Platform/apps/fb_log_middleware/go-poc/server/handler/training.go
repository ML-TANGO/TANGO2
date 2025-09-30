package handler

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"slices"
	"strings"

	pb "acryl.ai/go-poc/proto/logquery"
	"github.com/elastic/go-elasticsearch/v8"
)

type TrainingServer struct {
	pb.UnimplementedLogQueryServiceServer
	esClient *elasticsearch.Client
}

func NewTrainingServer(esClient *elasticsearch.Client) *TrainingServer {
	return &TrainingServer{esClient: esClient}
}

func (s *TrainingServer) UserLogsQuery(ctx context.Context, query string) (*pb.SummaryLogsResponse, error) {
	//log.Printf("%s", query)
	res, err := s.esClient.Search(
		s.esClient.Search.WithContext(ctx),
		s.esClient.Search.WithIndex("*user*"),
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
		log.Printf("[JFB/ERROR] (MLS) Error parsing the response body: %v", err)
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
				if k == "@timestamp" {
					k = "timestamp"
				}
				if k == "jfb_user_json" {
					// Unmarshal JSON string to map
					var userJson map[string]interface{}
					err := json.Unmarshal([]byte(fmt.Sprintf("%v", v)), &userJson)
					if err != nil {
						log.Printf("[JFB/ERROR] (MLS) Error parsing user_json: %v", err)
						log.Printf("MultilineEnd")
						continue
					}
					for uk, uv := range userJson {
						if uk == "timestamp" || uk == "log" {
							continue
						}
						logEntry.Fields[uk] = fmt.Sprintf("%v", uv)
					}
					continue
				}
				logEntry.Fields[k] = fmt.Sprintf("%v", v)
			}
		}
		// logEntry.Fields["log"] = fmt.Sprintf("%s | %s", logEntry.Fields["timestamp"], logEntry.Fields["log"])
		logs = append(logs, logEntry)
	}

	totalCount, _ := r["hits"].(map[string]interface{})["total"].(map[string]interface{})["value"].(float64)
	slices.Reverse(logs) // Return logs reversed
	return &pb.SummaryLogsResponse{
		Logs:         logs,
		TotalCount:   int64(totalCount),
		CurrentCount: int32(len(logs)),
	}, nil
}

func (s *TrainingServer) QueryTrainingFigureLogs(ctx context.Context, req *pb.TrainingFigureRequest) (*pb.SummaryLogsResponse, error) {
	/*
		message TrainingFigureRequest {
		string trainingItemId = 1;
		}
	*/
	trainingTool := req.TrainingTool
	trainingItemId := req.TrainingItemId
	count := req.Count
	offset := req.Offset

	query := fmt.Sprintf(`{
		"from": %d,
		"size": %d,
		"query": {
			"bool": {
				"filter": [
					{"term": { "kubernetes.labels.work_func_type.keyword": "%s" }},
					{"term": { "kubernetes.labels.project_item_id.keyword": "%d" }},
					{"exists": { "field": "jfb_user_json" }}
				]
			}
		},
		"sort": [ { "@timestamp": {"order": "desc"} } ],
		"fields": [ { "field": "@timestamp", "format": "strict_date_optional_time_nanos"} ],
		"_source": {
			"includes": [
				"@timestamp", "jfb_user_json", "log"
			]
		}
	}`, offset, count, trainingTool, trainingItemId)

	return s.UserLogsQuery(ctx, query)
}

func (s *TrainingServer) QueryTrainingAllLogs(ctx context.Context, req *pb.TrainingAllRequest) (*pb.SummaryLogsResponse, error) {
	/*
		message TrainingFigureRequest {
		  string trainingTool = 1;
		  string trainingItemId = 2;
		  int32 count = 3;
		  int64 offset = 4;
	*/
	trainingTool := req.TrainingTool
	trainingItemId := req.TrainingItemId
	count := req.Count
	offset := req.Offset

	query := fmt.Sprintf(`{
		"from": %d,
		"size": %d,
		"query": {
			"bool": {
				"filter": [
					{"term": { "kubernetes.labels.work_func_type.keyword": "%s" }},
					{"term": { "kubernetes.labels.project_item_id.keyword": "%d" }}
				]
			}
		},
		"sort": [ { "@timestamp": "desc" } ],
		"_source": {
			"includes": [
				"@timestamp", "log"
			]
		}
	}`, offset, count, trainingTool, trainingItemId)

	return s.UserLogsQuery(ctx, query)
}
