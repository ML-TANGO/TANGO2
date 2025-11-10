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

type ESNativeServer struct {
	pb.UnimplementedLogQueryServiceServer
	esClient *elasticsearch.Client
}

func NewESNativeServer(esClient *elasticsearch.Client) *ESNativeServer {
	return &ESNativeServer{esClient: esClient}
}

func (s *ESNativeServer) ElasticNativeQuery(ctx context.Context, req *pb.ElasticNativeQueryRequest) (*pb.ElasticNativeQueryResponse, error) {
	/*
		message ElasticNativeQueryRequest {
			string queryIndex = 1;
			string queryBody = 2;
		}

		message ElasticNativeQueryResponse {
			google.protobuf.Struct response = 1;
		}
	*/
	queryIndex := req.QueryIndex
	queryBody := req.QueryBody

	res, err := s.esClient.Search(
		s.esClient.Search.WithContext(ctx),
		s.esClient.Search.WithIndex(queryIndex),
		s.esClient.Search.WithBody(strings.NewReader(queryBody)),
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
	pbStruct, err := structpb.NewStruct(r)
	if err != nil {
		log.Printf("[JFB/ERROR] (MLS) Error converting native data into struct: %v", err)
		log.Printf("%s", err)
		log.Printf("MultilineEnd")
		return nil, err
	}

	return &pb.ElasticNativeQueryResponse{
		Response: pbStruct,
	}, nil
}
