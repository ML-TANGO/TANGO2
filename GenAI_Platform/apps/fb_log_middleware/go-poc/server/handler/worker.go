package handler

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"strings"

	pb "acryl.ai/go-poc/proto/logquery"
	"github.com/elastic/go-elasticsearch/v8"

	"google.golang.org/protobuf/types/known/structpb"
)

type WorkerServer struct {
	pb.UnimplementedLogQueryServiceServer
	esClient *elasticsearch.Client
}

func NewWorkerServer(esClient *elasticsearch.Client) *WorkerServer {
	return &WorkerServer{esClient: esClient}
}

func (s *WorkerServer) WorkerLogsQuery(ctx context.Context, query string) (*pb.RecentWorkerInfoResponse, error) {
	//log.Printf("%s", query)

	res, err := s.esClient.Search(
		s.esClient.Search.WithContext(ctx),
		s.esClient.Search.WithIndex("*jonathan-worker*"),
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

	resp := &pb.RecentWorkerInfoResponse{}

	aggs, ok := r["aggregations"].(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("aggregations not found in response")
	}

	latestByCatLevel, ok := aggs["latest_by_cat_level"].(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("latest_by_cat_level not found in response")
	}

	buckets, ok := latestByCatLevel["buckets"].([]interface{})
	if !ok {
		return nil, fmt.Errorf("buckets not found in response")
	}

	for _, bucket := range buckets {
		bucketMap, ok := bucket.(map[string]interface{})
		if !ok {
			return nil, fmt.Errorf("bucket not found in response")
		}

		catLevel, ok := bucketMap["key"].(string)
		if !ok {
			return nil, fmt.Errorf("key not found in response")
		}

		topDoc, ok := bucketMap["top_doc"].(map[string]interface{})
		if !ok {
			return nil, fmt.Errorf("top_doc not found in response")
		}

		hits, ok := topDoc["hits"].(map[string]interface{})
		if !ok {	
			return nil, fmt.Errorf("hits not found in response")
		}

		hitsArray, ok := hits["hits"].([]interface{})
		if !ok {
			return nil, fmt.Errorf("hits not found in response")
		}

		if len(hitsArray) == 0 {
			continue
		}

		hit, ok := hitsArray[0].(map[string]interface{})
		if !ok {
			return nil, fmt.Errorf("hit not found in response")
		}

		source, ok := hit["_source"].(map[string]interface{})
		if !ok {
			return nil, fmt.Errorf("_source not found in response")
		}

		/*timestamp, ok := source["@timestamp"].(string)
		if !ok {
			return nil, fmt.Errorf("@timestamp not found in response")
		}*/

		jfbLog, ok := source["jfb_log"].(string)
		if !ok {
			return nil, fmt.Errorf("jfb_log not found in response")
		}

		// Special handler for catLevel nginx_access_per_hour
		if catLevel == "nginx_access_per_hour" {
			// Save jfb_log into string then done
			resp.NginxAccessPerHour = jfbLog
			continue
		}

		var data map[string]interface{}
		if err := json.Unmarshal([]byte(jfbLog), &data); err != nil {
			return nil, fmt.Errorf("error parsing jfb_log: %v", err)
		}

		switch catLevel {
		case "nginx_count":
			resp.NginxCount, err = structpb.NewStruct(data)
		case "dashboard_history":
			resp.DashboardHistory, err = structpb.NewStruct(data)
		case "dashboard_live_history":
			resp.DashboardLiveHistory, err = structpb.NewStruct(data)
		}

		if err != nil {
			return nil, fmt.Errorf("error converting native data into struct: %v", err)
		}
	}

	return resp, nil
}

func (s *WorkerServer) QueryRecentWorkerInfoLog(ctx context.Context, req *pb.RecentWorkerInfoRequest) (*pb.RecentWorkerInfoResponse, error) {
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
	deploymentWorkerId := req.DeploymentWorkerId

	query := fmt.Sprintf(`{
		"size": 0,
		"query": {
			"bool": {
				"filter": [
					{"term": {
						"_cat_minor.keyword": "worker"
					}},
					{"term": {
						"kubernetes.labels.deployment_worker_id": %d
					}},
					{"terms": {
						"_cat_level.keyword": [
							"nginx_count", 
							"dashboard_history", 
							"dashboard_live_history",
							"nginx_access_per_hour"
						]
					}}
				]
			}
		},
		"aggs": {
			"latest_by_cat_level": {
				"terms": {
					"field": "_cat_level.keyword"
				},
				"aggs": {
					"top_doc": {
						"top_hits": {
							"size": 1,
							"sort": [{
								"@timestamp": {
									"order": "desc"
								}
							}],
							"_source": ["@timestamp", "jfb_log"]
						}
					}
				}
			}
		}
	}`, deploymentWorkerId)

	return s.WorkerLogsQuery(ctx, query) // TODO 이미지쪽 로그 처리 후 인덱스 범위 좁히기
}
