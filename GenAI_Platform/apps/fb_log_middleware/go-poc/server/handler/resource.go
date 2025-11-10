package handler

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"math"
	"strings"
	"time"

	pb "acryl.ai/go-poc/proto/logquery"
	"github.com/elastic/go-elasticsearch/v8"

	"google.golang.org/protobuf/types/known/structpb"
)

type ResourceServer struct {
	pb.UnimplementedLogQueryServiceServer
	esClient *elasticsearch.Client
}

func NewResourceServer(esClient *elasticsearch.Client) *ResourceServer {
	return &ResourceServer{esClient: esClient}
}

func (s *ResourceServer) ResourceLogsQuery(ctx context.Context, query string) (*structpb.Struct, error) {
	//log.Printf("%s", query)
	res, err := s.esClient.Search(
		s.esClient.Search.WithContext(ctx),
		s.esClient.Search.WithIndex("*jonathan-resource*"),
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

	logs := make(map[string]interface{})
	/*
		Convert the response aggregations to proper format.
		Native result is - memory: { buckets: [ {"key_as_string": ..., "used_ram": {"value": ...}, "total_ram": {"value": ...}}, ...]}
		We need to convert this to - ram: [{"used_ram": ..., "total_ram": ..., "date": ...}, ...]
		Do for gpu, cpu, storage_data, storage_main also.
		Map memory->ram, gpu->gpu, cpu->cpu, storage_data->storage_data, storage_main->storage_main and do all with a loop.
		Not changes for the name of the fields inside the buckets.

		Keep in mind that native data is in r["aggregations"]
	*/
	keyMap := map[string]string{
		"memory":        "ram",
		"gpu":           "gpu",
		"cpu":           "cpu",
		"storage_data":  "storage_data",
		"storage_main":  "storage_main",
		"network":	   	 "network",	
	}
	divisionMap := map[string]float64{
		"memory": 1000 * 1000 * 1000,
		"gpu":    1,
		"cpu":    1,
		"storage_data": 1000 * 1000 * 1000,
		"storage_main": 1000 * 1000 * 1000,
	}

	elasticTime := r["took"].(float64)
	// to check parsing time, record current time
	parseStartTime := time.Now()
	
	// iterate through aggregations
	aggs := r["aggregations"].(map[string]any)
	for key, value := range aggs {
		// check for the proper key
		isTarget := false
		for k, _ := range keyMap {
			if key == k {
				isTarget = true
				break
			}
		}
		if !isTarget {
			continue
		}
		
		currentItems := make([]any, 0)
		// iterate through buckets
		buckets := value.(map[string]any)["buckets"].([]any)
		for _, bucket := range buckets {
			bucketMap := bucket.(map[string]any)
			currentItem := make(map[string]any)
			// iterate through the fields of the bucket
			for k, v := range bucketMap {
				// check if the field is a key_as_string, if it is, assign it to date
				// else if the field is not key or doc_count (_ prefix also), extract value and assign it directly to the log entry
				if k == "key_as_string" {
					currentItem["date"] = fmt.Sprintf("%v", v)
				} else if !strings.HasPrefix(k, "_") && k != "doc_count" && k != "key" {
					currentItem[k] = v.(map[string]any)["value"]
				}
			}
			usedName := fmt.Sprintf("used_%v", keyMap[key])
			totalName := fmt.Sprintf("total_%v", keyMap[key])
			// If usedName and totalName both exists, calculate its percentage and add it.
			if _, ok := currentItem[usedName]; ok {
				if _, ok := currentItem[totalName]; ok {
					// Check both value is number and total is not zero
					if _, ok := currentItem[usedName].(float64); ok {
						if _, ok := currentItem[totalName].(float64); ok {
							if currentItem[totalName].(float64) != 0.0 {
								usageName := fmt.Sprintf("ratio_%v", keyMap[key])			
								currentItem[usageName] = math.Round((currentItem[usedName].(float64) / currentItem[totalName].(float64)) * 10000) / 100
							}
							// truncate the value with divisionMap, until 2 decimal points
							if _, ok := divisionMap[key]; ok {
								currentItem[usedName] = math.Round(currentItem[usedName].(float64) / divisionMap[key] * 100) / 100
								currentItem[totalName] = math.Round(currentItem[totalName].(float64) / divisionMap[key] * 100) / 100
							}
						}
					}
				}
			}

			currentItems = append(currentItems, currentItem)
		}
		// logs.append({keyMap[key]: currentItems})
		logs[keyMap[key]] = currentItems
	}

	log.Printf("[JFB/DEBUG] (resource query) ElasticSearch took %f ms, Parsing took %f ms", elasticTime, time.Since(parseStartTime).Seconds() * 1000)

	response, err := structpb.NewStruct(logs)
	if err != nil {
		log.Printf("[JFB/ERROR] (MLS) Error converting native data into struct: %v", err)
		log.Printf("%s", err)
		log.Printf("MultilineEnd")
		return nil, err
	}

	return response, nil
}

func generateResourceQueryBody(elasticLevel string, workspaceId int64, timeSpan string, interval string, startTime string, endTime string) (string, error){
	if elasticLevel == "" {
		// error
		return "", fmt.Errorf("Elastic level is not provided")
	}
	if timeSpan == "" {
		timeSpan = "now-12h"
	}
	if interval == "" {
		interval = "1m"
	}

	termWorkspaceId := ""	
	aggs := ""
	if workspaceId > 0 {
		termWorkspaceId = fmt.Sprintf(`, {"term": {"workspace_id": %d}}`, workspaceId)
		aggs = fmt.Sprintf(`"aggs": {
			"cpu": {
					"date_histogram": {
						"field": "@timestamp",
						"fixed_interval": "%s",
						"time_zone": "Asia/Seoul",
						"format": "yyyy-MM-dd HH:mm"
					},
					"aggs": {
						"used_cpu": {
							"max": {
								"field": "cpu.used"
							}
						},
						"total_cpu": {
							"max": {
								"field": "cpu.hard"
							}
						}
					}
				},
				"gpu": {
					"date_histogram": {
						"field": "@timestamp", 
						"fixed_interval": "%s",
						"time_zone": "Asia/Seoul",
						"format": "yyyy-MM-dd HH:mm"
					},
					"aggs": {
						"used_gpu": {
							"max": {
								"field": "gpu.used"
							}
						},
						"total_gpu": {
							"max": {
								"field": "gpu.hard"
							}
						}
					}
				},
				"memory": {
					"date_histogram": {
						"field": "@timestamp",
						"fixed_interval": "%s",
						"time_zone": "Asia/Seoul",
						"format": "yyyy-MM-dd HH:mm"
					},
					"aggs": {
						"used_ram": {
							"max": {
								"field": "ram.used"
							}
						},
						"total_ram": {
							"max": {
								"field": "ram.hard"
							}
						}
					}
				},
				"storage_data": {
					"date_histogram": {
						"field": "@timestamp",
						"fixed_interval": "%s",
						"time_zone": "Asia/Seoul",
						"format": "yyyy-MM-dd HH:mm"
					},
					"aggs": {
						"used_storage_data": {
							"max": {
								"field": "storage_data.used"
							}
						},
						"total_storage_data": {
							"max": {
								"field": "storage_data.total"
							}
						}
					}
				},
				"storage_main": {
					"date_histogram": {
						"field": "@timestamp",
						"fixed_interval": "%s",
						"time_zone": "Asia/Seoul",
						"format": "yyyy-MM-dd HH:mm"
					},
					"aggs": {
						"used_storage_main": {
							"max": {
								"field": "storage_main.used"
							}
						},
						"total_storage_main": {
							"max": {
								"field": "storage_main.total"
							}
						}
					}
				},
				"network":{
					"date_histogram": {
						"field": "@timestamp",
						"fixed_interval": "%s",
						"time_zone": "Asia/Seoul",
						"format": "yyyy-MM-dd HH:mm"
					},
					"aggs":{
						"outbound": {
							"sum": {
								"field": "network_inbound"
							}
						},
						"inbound":{
							"sum": {
								"field": "network_outbound"
							}
						}
					}
				}
			}
		`, interval, interval, interval, interval, interval, interval)
	} else {
		aggs = fmt.Sprintf(`"aggs": {
			"cpu": {
					"date_histogram": {
						"field": "@timestamp",
						"fixed_interval": "%s",
						"time_zone": "Asia/Seoul",
						"format": "yyyy-MM-dd HH:mm"
					},
					"aggs": {
						"used_cpu": {
							"max": {
								"field": "cpu.used_cpu"
							}
						},
						"total_cpu": {
							"max": {
								"field": "cpu.total_cpu"
							}
						}
					}
				},
				"gpu": {
					"date_histogram": {
						"field": "@timestamp", 
						"fixed_interval": "%s",
						"time_zone": "Asia/Seoul",
						"format": "yyyy-MM-dd HH:mm"
					},
					"aggs": {
						"used_gpu": {
							"max": {
								"field": "gpu.used_gpu"
							}
						},
						"total_gpu": {
							"max": {
								"field": "gpu.total_gpu"
							}
						}
					}
				},
				"memory": {
					"date_histogram": {
						"field": "@timestamp",
						"fixed_interval": "%s",
						"time_zone": "Asia/Seoul",
						"format": "yyyy-MM-dd HH:mm"
					},
					"aggs": {
						"used_ram": {
							"max": {
								"field": "ram.used_ram"
							}
						},
						"total_ram": {
							"max": {
								"field": "ram.total_ram"
							}
						}
					}
				},
				"storage_data": {
					"date_histogram": {
						"field": "@timestamp",
						"fixed_interval": "%s",
						"time_zone": "Asia/Seoul",
						"format": "yyyy-MM-dd HH:mm"
					},
					"aggs": {
						"used_storage_data": {
							"max": {
								"field": "storage_data.used_storage_data"
							}
						},
						"total_storage_data": {
							"max": {
								"field": "storage_data.total_storage_data"
							}
						}
					}
				},
				"storage_main": {
					"date_histogram": {
						"field": "@timestamp",
						"fixed_interval": "%s",
						"time_zone": "Asia/Seoul",
						"format": "yyyy-MM-dd HH:mm"
					},
					"aggs": {
						"used_storage_main": {
							"max": {
								"field": "storage_main.used_storage_main"
							}
						},
						"total_storage_main": {
							"max": {
								"field": "storage_main.total_storage_main"
							}
						}
					}
				}
			}
		`, interval, interval, interval, interval, interval)
	}

	timeRange := `{
		"range": {
			"@timestamp": {
	`	
	if startTime != "" || endTime != "" {
		timeSpan = ""
		if startTime != "" {
			startTime, err := time.Parse("2006-01-02 15:04:05", startTime)
			if err != nil {
				log.Printf("Error parsing start time: %s", err)
				return "", err
			}
			timeRange += fmt.Sprintf(`"gte": "%s"`, startTime.Format("2006-01-02T15:04:05.000000Z"))
		}
		if endTime != "" {
			if startTime != "" {
				timeRange += ","
			}
			endTime, err := time.Parse("2006-01-02 15:04:05", endTime)
			if err != nil {
				log.Printf("Error parsing end time: %s", err)
				return "", err
			}
			timeRange += fmt.Sprintf(`"lte": "%s"`, endTime.Format("2006-01-02T15:04:05.000000Z"))
		}
		timeRange += "}"
	} else {
		timeRange += fmt.Sprintf(`"gte": "%s"}`, timeSpan)
	}
	timeRange += "}}"


	return fmt.Sprintf(`{
		"size": 0,
		"query": { 
			"bool": { 
				"filter": [
					%s,
					{
						"term": {
							"_cat_level.keyword": "%s"
						}
					} 
					%s
				]
			}
		},
		%s
	}`, timeRange, elasticLevel, termWorkspaceId, aggs), nil

}

func (s *ResourceServer) QueryWorkspaceResourceLogs(ctx context.Context, req *pb.WorkspaceResourceRequest) (*structpb.Struct, error) {
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
	workspaceId := req.WorkspaceId
	timeSpan := req.TimeSpan
	interval := req.Interval
	startTime := req.StartTime
	endTime := req.EndTime
	
	query, _ := generateResourceQueryBody("workspace_usage", workspaceId, timeSpan, interval, startTime, endTime)

	//log.Printf("%v", query)
	//log.Printf("%v", logs)

	return s.ResourceLogsQuery(ctx, query) 
}

func (s *ResourceServer) QueryClusterResourceLogs(ctx context.Context, req *pb.ClusterResourceRequest) (*structpb.Struct, error){
	timeSpan := req.TimeSpan
	interval := req.Interval
	startTime := req.StartTime
	endTime := req.EndTime
	
	query, _ := generateResourceQueryBody("jonathan_usage", -1, timeSpan, interval, startTime, endTime)

	return s.ResourceLogsQuery(ctx, query)
}