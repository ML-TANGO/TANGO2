import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import logging
from utils.redis import get_redis_health_status, is_redis_connected, get_safe_redis_client

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.handle_health_check()
        elif self.path == '/health/redis':
            self.handle_redis_health()
        elif self.path == '/health/detailed':
            self.handle_detailed_health()
        elif self.path == '/probe/liveness':
            self.handle_liveness_probe()
        elif self.path == '/probe/readiness':
            self.handle_readiness_probe()
        else:
            self.send_error(404, "Not Found")

    def handle_health_check(self):
        """기본 헬스체크 엔드포인트"""
        try:
            redis_status = get_redis_health_status()
            
            if redis_status.get("connected", False):
                status_code = 200
                response_data = {
                    "status": "healthy",
                    "timestamp": time.time(),
                    "services": {
                        "redis": "connected"
                    }
                }
            else:
                status_code = 503
                response_data = {
                    "status": "unhealthy", 
                    "timestamp": time.time(),
                    "services": {
                        "redis": "disconnected"
                    }
                }
            
            self.send_json_response(status_code, response_data)
            
        except Exception as e:
            logging.error(f"Health check 오류: {e}")
            self.send_json_response(500, {
                "status": "error",
                "message": str(e),
                "timestamp": time.time()
            })

    def handle_redis_health(self):
        """Redis 전용 헬스체크"""
        try:
            redis_client = get_safe_redis_client()
            if redis_client and is_redis_connected(redis_client):
                status_code = 200
                response_data = {
                    "redis": {
                        "status": "connected",
                        "last_check": get_redis_health_status().get("last_check", 0)
                    }
                }
            else:
                status_code = 503
                response_data = {
                    "redis": {
                        "status": "disconnected",
                        "last_check": get_redis_health_status().get("last_check", 0)
                    }
                }
            
            self.send_json_response(status_code, response_data)
            
        except Exception as e:
            logging.error(f"Redis health check 오류: {e}")
            self.send_json_response(500, {
                "redis": {
                    "status": "error",
                    "message": str(e)
                }
            })

    def handle_detailed_health(self):
        """상세 헬스체크 정보"""
        try:
            redis_status = get_redis_health_status()
            redis_client = get_safe_redis_client()
            
            response_data = {
                "status": "healthy" if redis_status.get("connected", False) else "unhealthy",
                "timestamp": time.time(),
                "services": {
                    "redis": {
                        "connected": redis_status.get("connected", False),
                        "last_check": redis_status.get("last_check", 0),
                        "last_check_human": time.ctime(redis_status.get("last_check", 0)) if redis_status.get("last_check", 0) > 0 else "N/A"
                    }
                },
                "application": {
                    "uptime": time.time() - getattr(self.server, 'start_time', time.time()),
                    "version": "1.0"
                }
            }
            
            status_code = 200 if redis_status.get("connected", False) else 503
            self.send_json_response(status_code, response_data)
            
        except Exception as e:
            logging.error(f"Detailed health check 오류: {e}")
            self.send_json_response(500, {
                "status": "error",
                "message": str(e),
                "timestamp": time.time()
            })

    def handle_liveness_probe(self):
        """Kubernetes liveness probe 엔드포인트 - 애플리케이션이 살아있는지 확인"""
        try:
            # 기본적인 애플리케이션 상태만 확인 (Redis 연결과 무관하게)
            status_code = 200
            self.send_response(status_code)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
            
        except Exception as e:
            logging.error(f"Liveness probe 오류: {e}")
            self.send_response(503)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'ERROR')

    def handle_readiness_probe(self):
        """Kubernetes readiness probe 엔드포인트 - Redis 연결 상태 확인"""
        try:
            redis_status = get_redis_health_status()
            
            if redis_status.get("connected", False):
                # Redis 연결이 정상이면 ready
                status_code = 200
                response_text = b'READY'
            else:
                # Redis 연결이 끊어지면 not ready (503)
                status_code = 503
                response_text = b'NOT_READY'
            
            self.send_response(status_code)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(response_text)
            
        except Exception as e:
            logging.error(f"Readiness probe 오류: {e}")
            self.send_response(503)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'ERROR')

    def send_json_response(self, status_code, data):
        """JSON 응답을 전송하는 헬퍼 메서드"""
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        response_json = json.dumps(data, indent=2, ensure_ascii=False)
        self.wfile.write(response_json.encode('utf-8'))

    def log_message(self, format, *args):
        """요청 로그를 표준 포맷으로 출력"""
        logging.info(f"Health Check - {self.address_string()} - {format % args}")

class HealthCheckServer:
    def __init__(self, port=8080):
        self.port = port
        self.server = None
        self.thread = None

    def start(self):
        """헬스체크 서버를 백그라운드 스레드에서 시작"""
        try:
            self.server = HTTPServer(('0.0.0.0', self.port), HealthCheckHandler)
            self.server.start_time = time.time()
            
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            
            logging.info(f"Health check 서버가 포트 {self.port}에서 시작되었습니다")
            logging.info(f"Health check endpoints:")
            logging.info(f"  - http://localhost:{self.port}/health")
            logging.info(f"  - http://localhost:{self.port}/health/redis") 
            logging.info(f"  - http://localhost:{self.port}/health/detailed")
            logging.info(f"Kubernetes probe endpoints:")
            logging.info(f"  - http://localhost:{self.port}/probe/liveness")
            logging.info(f"  - http://localhost:{self.port}/probe/readiness")
            
        except Exception as e:
            logging.error(f"Health check 서버 시작 실패: {e}")
            raise

    def stop(self):
        """헬스체크 서버 중지"""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            logging.info("Health check 서버가 중지되었습니다")

# 싱글톤 헬스체크 서버 인스턴스
_health_server = None

def start_health_check_server(port=8080):
    """헬스체크 서버를 시작하는 함수"""
    global _health_server
    if _health_server is None:
        _health_server = HealthCheckServer(port)
        _health_server.start()
    return _health_server

def stop_health_check_server():
    """헬스체크 서버를 중지하는 함수"""
    global _health_server
    if _health_server:
        _health_server.stop()
        _health_server = None 