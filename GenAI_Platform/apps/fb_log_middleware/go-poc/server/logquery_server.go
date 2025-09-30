package handler

import (
	"context"

	pb "acryl.ai/go-poc/proto/logquery"
	"acryl.ai/go-poc/server/handler"
	"github.com/elastic/go-elasticsearch/v8"
)

type LogQueryServer struct {
	pb.UnimplementedLogQueryServiceServer
	dashboardServer  *handler.DashboardServer
	trainingServer   *handler.TrainingServer
	deploymentServer *handler.DeploymentServer
	imageServer      *handler.ImageServer
}

func NewLogQueryServer(esClient *elasticsearch.Client) *LogQueryServer {
	return &LogQueryServer{
		dashboardServer:  handler.NewDashboardServer(esClient),
		trainingServer:   handler.NewTrainingServer(esClient),
		deploymentServer: handler.NewDeploymentServer(esClient),
		imageServer:      handler.NewImageServer(esClient),
	}
}

func (s *LogQueryServer) QueryDeploymentAllLogs(ctx context.Context, req *pb.DeploymentAllRequest) (*pb.SummaryLogsResponse, error) {
	return s.deploymentServer.QueryDeploymentAllLogs(ctx, req)
}

func (s *LogQueryServer) QueryImageAllLogs(ctx context.Context, req *pb.ImageAllRequest) (*pb.SummaryLogsResponse, error) {
	return s.imageServer.QueryImageAllLogs(ctx, req)
}

func (s *LogQueryServer) QueryTrainingFigureLogs(ctx context.Context, req *pb.TrainingFigureRequest) (*pb.SummaryLogsResponse, error) {
	return s.trainingServer.QueryTrainingFigureLogs(ctx, req)
}

func (s *LogQueryServer) QueryTrainingAllLogs(ctx context.Context, req *pb.TrainingAllRequest) (*pb.SummaryLogsResponse, error) {
	return s.trainingServer.QueryTrainingAllLogs(ctx, req)
}

func (s *LogQueryServer) QueryWorkspaceDashboardLogs(ctx context.Context, req *pb.WorkspaceDashboardRequest) (*pb.SummaryLogsResponse, error) {
	return s.dashboardServer.QueryWorkspaceDashboardLogs(ctx, req)
}

func (s *LogQueryServer) QueryAdminDashboardLogs(ctx context.Context, req *pb.AdminDashboardRequest) (*pb.SummaryLogsResponse, error) {
	return s.dashboardServer.QueryAdminDashboardLogs(ctx, req)
}

func (s *LogQueryServer) QueryAdminDetailLogs(ctx context.Context, req *pb.AdminDetailRequest) (*pb.SummaryLogsResponse, error) {
	return s.dashboardServer.QueryAdminDetailLogs(ctx, req)
}
