import grpc
import storage_pb2
import storage_pb2_grpc

def get_disk_usage(server_address, path):
    with grpc.insecure_channel(server_address) as channel:
        stub = storage_pb2_grpc.StorageServiceStub(channel)
        response = stub.GetDiskUsage(storage_pb2.DiskUsageRequest(path=path))
        return response.usage

if __name__ == '__main__':
    servers = ['192.168.1.14:50051']
    path = '/jf-storage-class/main/'

    for server in servers:
        usage = get_disk_usage(server, path)
        print(f'Disk usage on server {server}: {usage}')
        print(type(usage))

