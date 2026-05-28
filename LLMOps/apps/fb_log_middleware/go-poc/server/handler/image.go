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

type ImageServer struct {
	pb.UnimplementedLogQueryServiceServer
	esClient *elasticsearch.Client
}

func NewImageServer(esClient *elasticsearch.Client) *ImageServer {
	return &ImageServer{esClient: esClient}
}

func (s *ImageServer) AllLogsQuery(ctx context.Context, query string) (*pb.SummaryLogsResponse, error) {
	//log.Printf("%s", query)
	res, err := s.esClient.Search(
		s.esClient.Search.WithContext(ctx),
		s.esClient.Search.WithIndex("*-all"),
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

	var logs []*pb.LogEntry
	for _, hit := range r["hits"].(map[string]interface{})["hits"].([]interface{}) {
		source := hit.(map[string]interface{})["_source"]
		logEntry := &pb.LogEntry{Fields: make(map[string]string)}
		for k, v := range source.(map[string]interface{}) {
			if !strings.HasPrefix(k, "_") {
				if k == "@timestamp" {
					k = "timestamp"
				}
				logEntry.Fields[k] = fmt.Sprintf("%v", v)
			}
		}
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

func (s *ImageServer) QueryImageAllLogs(ctx context.Context, req *pb.ImageAllRequest) (*pb.SummaryLogsResponse, error) {
	/*
		rpc QueryImageAllLogs (ImageAllRequest) returns (SummaryLogsResponse) {
		    option (google.api.http) = {
		      post: "/v1/image/all"
		      body: "*"
		    };

			message ImageAllRequest{
		  string imageJobName = 1;
		  int32 count = 2;
		  int64 offset = 3;
		}

	*/
	imageJobName := req.ImageJobName
	count := req.Count
	offset := req.Offset

	query := fmt.Sprintf(`{
		"from": %d,
		"size": %d,
		"query": {
			"bool": {
				"filter": [
					{"term": { "kubernetes.namespace_name.keyword": "jonathan-system-image" }},
					{"term": { "kubernetes.labels.job-name.keyword": "%s" }}
				]
			}
		},
		"sort": [ { "@timestamp": {"order": "desc"} }, "_doc" ],
		"_source": {
			"includes": [
				"@timestamp", "log"
			]
		}
	}`, offset, count, imageJobName)

	return s.AllLogsQuery(ctx, query) // TODO 이미지쪽 로그 처리 후 인덱스 범위 좁히기
}
