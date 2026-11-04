import grpc
from concurrent import futures
import os
import subprocess
import storage_pb2
import storage_pb2_grpc
from pathlib import Path

class StorageService(storage_pb2_grpc.StorageServiceServicer):
    def GetDiskUsage(self, request, context):
        if Path(request.path).exists():
            print(request.path)
            result = subprocess.run(['du', '-sb', request.path], capture_output=True, text=True)
            usage = result.stdout.split()[0] if result.returncode == 0 else 0
            print(usage)
            return storage_pb2.DiskUsageReply(usage=usage)
        return storage_pb2.DiskUsageReply(usage=0)

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=20))
    storage_pb2_grpc.add_StorageServiceServicer_to_server(StorageService(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    server.wait_for_termination()

if __name__ == '__main__':
    serve()
