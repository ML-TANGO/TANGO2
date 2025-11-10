package handler

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"strings"
	"time"
	_ "time/tzdata"

	pb "acryl.ai/go-poc/proto/logquery"
	"github.com/elastic/go-elasticsearch/v8"
)

type WorkspaceServer struct {
	pb.UnimplementedLogQueryServiceServer
	esClient *elasticsearch.Client
}

func NewWorkspaceServer(esClient *elasticsearch.Client) *WorkspaceServer {
	return &WorkspaceServer{esClient: esClient}
}

func (s *WorkspaceServer) WorkspaceLogsQuery(ctx context.Context, query string) (*map[string]interface{}, error) {
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

func (s *WorkspaceServer) QueryWorkspaceAllocationTime(ctx context.Context, req *pb.WorkspaceAllocationTimeRequest) (*pb.WorkspaceAllocationTimeResponse, error){
	workspaceName := req.WorkspaceName
	// count := req.Count
	// if count == 0 {
	// 	count = 10000
	// }

	query := map[string]interface{}{
        "size": 0,
        "aggs": map[string]interface{}{
            "instances_composite": map[string]interface{}{
                "composite": map[string]interface{}{
                    "size": 10000,
                    "sources": []map[string]interface{}{
                        {
                            "name": map[string]interface{}{
                                "terms": map[string]interface{}{
                                    "field": "info.instances.instance_name.keyword",
                                },
                            },
                        },
                        {
                            "count": map[string]interface{}{
                                "terms": map[string]interface{}{
                                    "field": "info.instances.instance_count",
                                },
                            },
                        },
                    },
                },
                "aggs": map[string]interface{}{
                    "total_duration": map[string]interface{}{
                        "sum": map[string]interface{}{
                            "field": "info.duration_minutes",
                        },
                    },
                },
            },
            "storages_composite": map[string]interface{}{
                "composite": map[string]interface{}{
                    "size": 10000,
                    "sources": []map[string]interface{}{
                        {
                            "storage_name": map[string]interface{}{
                                "terms": map[string]interface{}{
                                    "field": "info.storages.storage_name.keyword",
                                },
                            },
                        },
                        {
                            "storage_type": map[string]interface{}{
                                "terms": map[string]interface{}{
                                    "field": "info.storages.storage_type.keyword",
                                },
                            },
                        },
                        {
                            "storage_size": map[string]interface{}{
                                "terms": map[string]interface{}{
                                    "field": "info.storages.storage_size",
                                },
                            },
                        },
                    },
                },
                "aggs": map[string]interface{}{
                    "total_duration": map[string]interface{}{
                        "sum": map[string]interface{}{
                            "field": "info.duration_minutes",
                        },
                    },
                },
            },
			"total_duration_minutes": map[string]interface{}{
                "sum": map[string]interface{}{
                    "field": "info.duration_minutes",
                },
            },
        },
    }
	if workspaceName != "" {
		query["query"] = map[string]interface{}{
			"bool": map[string]interface{}{
				"filter": []map[string]interface{}{
					{
						"term": map[string]interface{}{
							"workspace.keyword": workspaceName,
						},
					},
				},
			},
		}							
	}

	// 쿼리 JSON으로 변환
	var buf bytes.Buffer
	if err := json.NewEncoder(&buf).Encode(query); err != nil {
		log.Fatalf("Error encoding query: %s", err)
	}

	queryString, err := json.Marshal(query)
	if err != nil {
		log.Fatalf("Error marshaling query to string: %s", err)
	}

	//log.Printf("Query: %s", queryString)

	resultMap, err := s.WorkspaceLogsQuery(ctx, string(queryString))
	if err != nil {
		log.Fatalf("Error querying workspace logs: %s", err)
	}

	//log.Printf("Result: %v", resultMap)

	// 결과 파싱
	// instancesComposite := (*resultMap)["aggregations"].(map[string]interface{})["instances_composite"].(map[string]interface{})["buckets"].([]interface{})
	// storagesComposite := (*resultMap)["aggregations"].(map[string]interface{})["storages_composite"].(map[string]interface{})["buckets"].([]interface{})

	// instances := make([]*pb.Instance, 0)
	// for _, instanceBucket := range instancesComposite {
	// 	instanceBucketMap := instanceBucket.(map[string]interface{})
	// 	instanceName := instanceBucketMap["key"].(map[string]interface{})["name"].(string)
	// 	instanceCount := int32(instanceBucketMap["key"].(map[string]interface{})["count"].(float64))
	// 	totalDuration := int32(instanceBucketMap["total_duration"].(map[string]interface{})["value"].(float64))

	// 	instances = append(instances, &pb.InstanceAllocation{
	// 		Name: instanceName,
	// 		Count: instanceCount,
	// 		TotalDuration: totalDuration,
	// 	})
	// }

	// storages := make([]*pb.StorageAllocation, 0)
	// for _, storageBucket := range storagesComposite {
	// 	storageBucketMap := storageBucket.(map[string]interface{})
	// 	storageName := storageBucketMap["key"].(map[string]interface{})["storage_name"].(string)
	// 	storageType := storageBucketMap["key"].(map[string]interface{})["storage_type"].(string)
	// 	storageSize := int32(storageBucketMap["key"].(map[string]interface{})["storage_size"].(float64))
	// 	totalDuration := int32(storageBucketMap["total_duration"].(map[string]interface{})["value"].(float64))

	// 	storages = append(storages, &pb.StorageAllocation{
	// 		Name: storageName,
	// 		Type: storageType,
	// 		Size: storageSize,
	// 		TotalDuration: totalDuration,
	// 	})
	// }

	totalDurationMinutes := int32((*resultMap)["aggregations"].(map[string]interface{})["total_duration_minutes"].(map[string]interface{})["value"].(float64))

	return &pb.WorkspaceAllocationTimeResponse{
		// Instances: instances,
		// Storages: storages,
		ActivationMinutes: totalDurationMinutes,
	}, nil
}

func (s *WorkspaceServer) QueryWorkspaceRecentModifyTime(ctx context.Context, req *pb.WorkspaceRecentModifyTimeRequest) (*pb.WorkspaceRecentModifyTimeResponse, error) {
	workspaceName := req.WorkspaceName

	query := map[string]interface{}{
		"size": 1,
		"query": map[string]interface{}{
			"bool": map[string]interface{}{
				"filter": []map[string]interface{}{
					{
						"term": map[string]interface{}{
							"workspace.keyword": workspaceName,
						},
					},
					{
						"terms": map[string]interface{}{
							"action.keyword": []string{"create", "update"},
						},
					},
				},
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
				"workspace", "@timestamp",
			},
		},		
	}

	// 쿼리 JSON으로 변환
	var buf bytes.Buffer
	if err := json.NewEncoder(&buf).Encode(query); err != nil {
		log.Fatalf("Error encoding query: %s", err)
	}

	queryString, err := json.Marshal(query)
	if err != nil {
		log.Fatalf("Error marshaling query to string: %s", err)
	}

	//log.Printf("Query: %s", queryString)

	resultMap, err := s.WorkspaceLogsQuery(ctx, string(queryString))
	if err != nil {
		log.Fatalf("Error querying workspace logs: %s", err)
	}

	//log.Printf("Result: %v", resultMap)

	// 결과 파싱
	hits := (*resultMap)["hits"].(map[string]interface{})["hits"].([]interface{})
	if len(hits) == 0 {
		return &pb.WorkspaceRecentModifyTimeResponse{
			ModifyTime: "",
		}, nil
	}

	hit := hits[0].(map[string]interface{})
	source := hit["_source"].(map[string]interface{})
	modifyTime := source["@timestamp"].(string)

	// Parse the modifyTime string to time.Time
	t, err := time.Parse(time.RFC3339Nano, modifyTime)
	if err != nil {
		log.Fatalf("Error parsing time: %s", err)
	}

	// Convert time to KST (UTC+9)
	kst, err := time.LoadLocation("Asia/Seoul")
	if err != nil {
		log.Fatalf("Error loading location: %s", err)
	}
	t = t.In(kst)

	// Format time to "YYYY-MM-DD hh:mm"
	formattedTime := t.Format("2006-01-02 15:04")

	return &pb.WorkspaceRecentModifyTimeResponse{
		ModifyTime: formattedTime,
	}, nil
	
}
