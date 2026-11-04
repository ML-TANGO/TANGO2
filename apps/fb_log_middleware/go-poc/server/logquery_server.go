package handler

import (
	"context"

	pb "acryl.ai/go-poc/proto/logquery"
	"acryl.ai/go-poc/server/handler"
	"github.com/elastic/go-elasticsearch/v8"

	"google.golang.org/protobuf/types/known/structpb"
)

type LogQueryServer struct {
	pb.UnimplementedLogQueryServiceServer
	dashboardServer  *handler.DashboardServer
	trainingServer   *handler.TrainingServer
	deploymentServer *handler.DeploymentServer
	imageServer      *handler.ImageServer
	fineTuningServer *handler.FineTuningServer
	esNativeServer   *handler.ESNativeServer
	resourceServer   *handler.ResourceServer
	workerServer     *handler.WorkerServer
	billingServer    *handler.BillingServer
	workspaceServer  *handler.WorkspaceServer
	allocationServer *handler.AllocationServer
}

func NewLogQueryServer(esClient *elasticsearch.Client) *LogQueryServer {
	return &LogQueryServer{
		dashboardServer:  handler.NewDashboardServer(esClient),
		trainingServer:   handler.NewTrainingServer(esClient),
		deploymentServer: handler.NewDeploymentServer(esClient),
		imageServer:      handler.NewImageServer(esClient),
		fineTuningServer: handler.NewFineTuningServer(esClient),
		esNativeServer:   handler.NewESNativeServer(esClient),
		resourceServer:   handler.NewResourceServer(esClient),
		workerServer:     handler.NewWorkerServer(esClient),
		billingServer:    handler.NewBillingServer(esClient),
		workspaceServer:  handler.NewWorkspaceServer(esClient),
		allocationServer: handler.NewAllocationServer(esClient),
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

func (s *LogQueryServer) QueryFineTuningAllLogs(ctx context.Context, req *pb.FineTuningAllRequest) (*pb.SummaryLogsResponse, error) {
	return s.fineTuningServer.QueryFineTuningAllLogs(ctx, req)
}

func (s *LogQueryServer) ElasticNativeQuery(ctx context.Context, req *pb.ElasticNativeQueryRequest) (*pb.ElasticNativeQueryResponse, error) {
	return s.esNativeServer.ElasticNativeQuery(ctx, req)
}

func (s *LogQueryServer) QueryWorkspaceResourceLogs(ctx context.Context, req *pb.WorkspaceResourceRequest) (*structpb.Struct, error) {
	return s.resourceServer.QueryWorkspaceResourceLogs(ctx, req)
}

func (s *LogQueryServer) QueryClusterResourceLogs(ctx context.Context, req *pb.ClusterResourceRequest) (*structpb.Struct, error) {
	return s.resourceServer.QueryClusterResourceLogs(ctx, req)
}

func (s *LogQueryServer) QueryRecentWorkerInfoLog(ctx context.Context, req *pb.RecentWorkerInfoRequest) (*pb.RecentWorkerInfoResponse, error) {
	return s.workerServer.QueryRecentWorkerInfoLog(ctx, req)
}

func (s *LogQueryServer) QueryBillingNetwork(ctx context.Context, req *pb.BillingNetworkRequest) (*pb.BillingNetworkResponse, error) {
	return s.billingServer.QueryBillingNetwork(ctx, req)
}

func (s *LogQueryServer) QueryBillingInstance(ctx context.Context, req *pb.BillingInstanceRequest) (*pb.BillingInstanceResponse, error) {
	return s.billingServer.QueryBillingInstance(ctx, req)
}

func (s *LogQueryServer) QueryWorkspaceAllocationTime(ctx context.Context, req *pb.WorkspaceAllocationTimeRequest) (*pb.WorkspaceAllocationTimeResponse, error) {
	return s.workspaceServer.QueryWorkspaceAllocationTime(ctx, req)
}

func (s *LogQueryServer) QueryWorkspaceRecentModifyTime(ctx context.Context, req *pb.WorkspaceRecentModifyTimeRequest) (*pb.WorkspaceRecentModifyTimeResponse, error) {
	return s.workspaceServer.QueryWorkspaceRecentModifyTime(ctx, req)
}

func (s *LogQueryServer) QueryAllocationHistory(ctx context.Context, req *pb.AllocationHistoryRequest) (*pb.AllocationHistoryResponse, error) {
	return s.allocationServer.QueryAllocationHistory(ctx, req)
}

func (s *LogQueryServer) QuerySummaryAllocationUptime(ctx context.Context, req *pb.SummaryAllocationUptimeRequest) (*pb.SummaryAllocationUptimeResponse, error) {
	return s.allocationServer.QuerySummaryAllocationUptime(ctx, req)
}
