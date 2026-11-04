package handler

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"strings"

	pb "acryl.ai/go-poc/proto/logquery"
	"github.com/elastic/go-elasticsearch/v8"
)

type BillingServer struct {
	pb.UnimplementedLogQueryServiceServer
	esClient *elasticsearch.Client
}

func NewBillingServer(esClient *elasticsearch.Client) *BillingServer {
	return &BillingServer{esClient: esClient}
}

func (s *BillingServer) ResourceLogsQuery(ctx context.Context, query string) (*map[string]interface{}, error) {
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

	aggregations, ok := r["aggregations"].(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("aggregations not found in response")
	}

	return &aggregations, nil
}

func (s *BillingServer) QueryBillingInstance(ctx context.Context, req *pb.BillingInstanceRequest) (*pb.BillingInstanceResponse, error) {
	workspace:= req.Workspace
	startTime:= req.StartTime
	if(startTime == ""){
		startTime = "now-12h"
	}
	endTime:= req.EndTime
	if(endTime == ""){
		endTime = "now"
	}
	interval:= req.Interval
	if(interval == ""){
		interval = "1h"
	}

	query := map[string]interface{}{
		"size": 0,
		"query": map[string]interface{}{
			"bool": map[string]interface{}{
				"filter": []map[string]interface{}{
					{
						"range": map[string]interface{}{
							"@timestamp": map[string]interface{}{
								"gte": startTime,
								"lte": endTime,
							},
						},
					},
					{
						"term": map[string]interface{}{
							"_cat_level.keyword": "workspace_instance_cost",
						},
					},
					{
						"term": map[string]interface{}{
							"workspace_id": workspace,
						},
					},
				},
			},
		},
		"aggs": map[string]interface{}{
			"by_time": map[string]interface{}{
				"date_histogram": map[string]interface{}{
					"field":         "@timestamp",
					"fixed_interval": interval,
					"time_zone":     "Asia/Seoul",
					"format":        "yyyy-MM-dd HH:mm:ss",
				},
				"aggs": map[string]interface{}{
					"total_cost": map[string]interface{}{
						"scripted_metric": map[string]interface{}{
							"init_script": "state.metrics = new HashMap();",
							"map_script": `
								for (key in params._source.instance.keySet()) {
									def instance = params._source.instance[key];
									if (!state.metrics.containsKey(key)) {
										state.metrics[key] = new HashMap();
										state.metrics[key].max_count = 0;
										state.metrics[key].total_cost = 0;
									}
									state.metrics[key].max_count = Math.max(state.metrics[key].max_count, instance.count);
									state.metrics[key].total_cost = instance.cost.time_unit_cost * state.metrics[key].max_count;
								}
							`,
							"combine_script": "return state.metrics;",
							"reduce_script": `
								Map finalMetrics = new HashMap();
								for (partialState in states) {
									if (partialState != null) {
										for (key in partialState.keySet()) {
											if (!finalMetrics.containsKey(key)) {
												finalMetrics[key] = new HashMap();
												finalMetrics[key].max_count = 0;
												finalMetrics[key].total_cost = 0;
											}
											def metric = partialState[key];
											if (metric != null) {
												finalMetrics[key].max_count = Math.max(finalMetrics[key].max_count, metric.max_count);
												finalMetrics[key].total_cost += metric.total_cost;
											}
										}
									}
								}
								return finalMetrics;
							`,
						},
					},
				},
			},
		},
	}

	var buf bytes.Buffer
	if err := json.NewEncoder(&buf).Encode(query); err != nil {
		log.Fatalf("Error encoding query: %s", err)
	}

	result, err:= s.ResourceLogsQuery(ctx, buf.String())
	if err != nil {
		log.Printf("Error querying ElasticSearch: %v", err)
		return nil, err
	}

	resultByTime, ok := (*result)["by_time"].(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("by_time not found in response")
	}

	buckets, ok := resultByTime["buckets"].([]interface{})
	if !ok {
		return nil, fmt.Errorf("buckets not found in response")
	}

	var billingBuckets []*pb.BillingInstanceBucket
	queryTotalCost := int64(0)
	for _, bucket := range buckets {
		bucketMap, ok := bucket.(map[string]interface{})
		if !ok {
			return nil, fmt.Errorf("bucket not found in response")
		}
		// Parse item first, make array and append
		instanceItems := make([]*pb.BillingInstanceItem, 0)
		bucketTotalCost := int64(0)
		for key, value := range bucketMap["total_cost"].(map[string]interface{})["value"].(map[string]interface{}) {
			instanceItem := &pb.BillingInstanceItem{
				InstanceId: key,
				MaxCount:   int32(value.(map[string]interface{})["max_count"].(float64)),
				TotalCost:  int64(value.(map[string]interface{})["total_cost"].(float64)),
			}
			instanceItems = append(instanceItems, instanceItem)
			bucketTotalCost += instanceItem.TotalCost
		}
		queryTotalCost += bucketTotalCost
		billingBuckets = append(billingBuckets, &pb.BillingInstanceBucket{
			TimeStamp: fmt.Sprintf("%v", bucketMap["key_as_string"]),
			TotalCost: bucketTotalCost,
			Instances: instanceItems,
		})
	}

	return &pb.BillingInstanceResponse{
		TotalCost: queryTotalCost,
		Buckets:   billingBuckets,
	}, nil
}

func (s *BillingServer) QueryBillingNetwork(ctx context.Context, req *pb.BillingNetworkRequest) (*pb.BillingNetworkResponse, error) {
	/*
		message BillingNetworkRequest{
			string workspace = 1;
			string startTime = 2;
			string endTime = 3;
			string interval = 4;
		}

		message BillingNetworkResponse{
			string timeStamp = 1;
			int64 outbound = 2;
			int64 paidCost = 3;
		}


	*/
	workspace:= req.Workspace
	startTime:= req.StartTime
	if(startTime == ""){
		startTime = "now-12h"
	}
	endTime:= req.EndTime
	if(endTime == ""){
		endTime = "now"
	}
	interval:= req.Interval
	if(interval == ""){
		interval = "1m"
	}


	query := map[string]interface{}{
		"size": 0,
		"query": map[string]interface{}{
			"bool": map[string]interface{}{
				"filter": []map[string]interface{}{
					{
						"range": map[string]interface{}{
							"@timestamp": map[string]interface{}{
								"gte": startTime,
								"lte": endTime,
							},
						},
					},
					{
						"term": map[string]interface{}{
							"_cat_level.keyword": "workspace_cost",
						},
					},
					{
						"term": map[string]interface{}{
							"workspace_id": workspace,
						},
					},
				},
			},
		},
		"aggs": map[string]interface{}{
			"network": map[string]interface{}{
				"date_histogram": map[string]interface{}{
					"field":         "@timestamp",
					"fixed_interval": interval,
					"time_zone":     "Asia/Seoul",
					"format":        "yyyy-MM-dd HH:mm:ss",
				},
				"aggs": map[string]interface{}{
					"paid_cost": map[string]interface{}{
						"scripted_metric": map[string]interface{}{
							"init_script": "state.paidCost = 0;",
							"map_script": `
								if (params['_source'].containsKey('network') && params['_source']['network'].containsKey('outbound')) {
									def outbound = params['_source']['network']['outbound'];
									def costs = params['_source']['network']['cost'];
									for (def cost : costs) {
										if (cost.start <= outbound) {
											state.paidCost = Math.max(state.paidCost, cost.cost);
										}
									}
								}
								else{
									state.paidCost=-1;
								}
							`,
							"combine_script": "return state.paidCost;",
							"reduce_script":  "return states[0];",
						},
					},
					"outbound": map[string]interface{}{
						"sum": map[string]interface{}{
							"field": "network.outbound",
						},
					},
				},
			},
		},
	}

	// 쿼리 JSON으로 변환
	var buf bytes.Buffer
	if err := json.NewEncoder(&buf).Encode(query); err != nil {
		log.Fatalf("Error encoding query: %s", err)
	}

	result, err:= s.ResourceLogsQuery(ctx, buf.String())
	if err != nil {
		log.Printf("Error querying ElasticSearch: %v", err)
		return nil, err
	}

	resultNetwork, ok := (*result)["network"].(map[string]interface{})
	if !ok {
		return nil, fmt.Errorf("network not found in response")
	}

	buckets, ok := resultNetwork["buckets"].([]interface{})
	if !ok {
		return nil, fmt.Errorf("buckets not found in response")
	}

	var billingBuckets []*pb.BillingNetworkBucket
	totalCost := int64(0)
	for _, bucket := range buckets {
		bucketMap, ok := bucket.(map[string]interface{})
		if !ok {
			return nil, fmt.Errorf("bucket not found in response")
		}
		// TimeStamp: key_as_string, Outbound: outbound.value, PaidCost: paid_cost.value
		billingNetworkBucket := &pb.BillingNetworkBucket{
			TimeStamp: fmt.Sprintf("%v", bucketMap["key_as_string"]),
			Outbound:  int64(bucketMap["outbound"].(map[string]interface{})["value"].(float64)),
			PaidCost:  int64(bucketMap["paid_cost"].(map[string]interface{})["value"].(float64)),
		}
		totalCost += billingNetworkBucket.PaidCost
		billingBuckets = append(billingBuckets, billingNetworkBucket)
	}

	return &pb.BillingNetworkResponse{
		TotalCost: totalCost,
		Buckets:   billingBuckets,
	}, nil
}
