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

type DeploymentServer struct {
	pb.UnimplementedLogQueryServiceServer
	esClient *elasticsearch.Client
}

func NewDeploymentServer(esClient *elasticsearch.Client) *DeploymentServer {
	return &DeploymentServer{esClient: esClient}
}

func (s *DeploymentServer) UserLogsQuery(ctx context.Context, query string) (*pb.SummaryLogsResponse, error) {
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

func (s *DeploymentServer) QueryDeploymentAllLogs(ctx context.Context, req *pb.DeploymentAllRequest) (*pb.SummaryLogsResponse, error) {
	/*
		rpc QueryDeploymentAllLogs (DeploymentAllRequest) returns (SummaryLogsResponse) {
		    option (google.api.http) = {
		      post: "/v1/deployment/all"
		      body: "*"
		    };
		  }

		message DeploymentAllRequest{
		  string deploymentWorkerId = 1;
		  int32 count = 2;
		  int64 offset = 3;
		}

	*/
	deploymentWorkerId := req.DeploymentWorkerId
	count := req.Count
	offset := req.Offset

	query := fmt.Sprintf(`{
		"from": %d,
		"size": %d,
		"query": {
			"bool": {
				"filter": [
					{"term": { "kubernetes.labels.deployment_worker_id.keyword": "%d" }}
				]
			}
		},
		"sort": [ { "@timestamp": {"order": "desc"} }, "_doc" ],
		"_source": {
			"includes": [
				"@timestamp", "log"
			]
		}
	}`, offset, count, deploymentWorkerId)

	return s.UserLogsQuery(ctx, query)
}
