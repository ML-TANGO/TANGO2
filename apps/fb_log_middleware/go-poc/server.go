package main

import (
	"context"
	"crypto/tls"
	"log"
	"net"
	"net/http"
	"os"

	//"crypto/tls"

	pb "acryl.ai/go-poc/proto/logquery"
	lqs "acryl.ai/go-poc/server"
	"github.com/elastic/go-elasticsearch/v8"
	"github.com/grpc-ecosystem/grpc-gateway/v2/runtime"
	"google.golang.org/grpc"
)

func main() {
	// Create ElasticSearch client
	// Fingerprint can be retreived with below command:
	// openssl s_client -connect localhost:30552 -servername localhost -showcerts </dev/null 2>/dev/null \
	//  | openssl x509 -fingerprint -sha256 -noout -in /dev/stdin
	// And then you must remove all :s or redundant starting "SHA256 Fingerprint="
	// Or, cert, _ := os.ReadFile("./ca.crt") then CACert: xxx
	//cert, _ := os.ReadFile("./ca.crt")

	esAddress := os.Getenv("ELASTICSEARCH_ADDRESS")
	if esAddress == "" {
		esAddress = "https://elasticsearch-master-hl:9200"
	}
	
	cfg := elasticsearch.Config{
		Addresses: []string{ // https://192.168.0.20:32495 // https://elasticsearch-master-hl:9200
			esAddress, // must be sent to inner 9200 port, not 9300!
		},
		Username: "elastic",
		Password: "tango1234!",
		Transport: &http.Transport{
			TLSClientConfig: &tls.Config{InsecureSkipVerify: true}, // Ignore CA verification
		},
	}
	esClient, err := elasticsearch.NewClient(cfg)
	if err != nil {
		log.Fatalf("Error creating the ElasticSearch client: %v", err)
	}
	res, err := esClient.Info()
	if err != nil {
		log.Fatalf("Error getting ElasticSearch information: %v", err)
	}
	defer res.Body.Close()

	// gRPC server
	grpcServer := grpc.NewServer()
	pb.RegisterLogQueryServiceServer(grpcServer, lqs.NewLogQueryServer(esClient))

	lis, err := net.Listen("tcp", ":50051")
	if err != nil {
		log.Fatalf("Failed to listen: %v", err)
	}

	log.Printf("Server listening on :50051")
	go grpcServer.Serve(lis)

	// Start HTTP server (gRPC Gateway)
	ctx := context.Background()
	ctx, cancel := context.WithCancel(ctx)
	defer cancel()

	mux := runtime.NewServeMux()
	err = pb.RegisterLogQueryServiceHandlerServer(ctx, mux, lqs.NewLogQueryServer(esClient))
	if err != nil {
		log.Fatalf("Failed to register gateway: %v", err)
	}

	log.Printf("REST gateway server listening on :8080")
	http.ListenAndServe(":8080", mux)
}
