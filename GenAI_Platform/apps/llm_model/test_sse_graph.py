#!/usr/bin/env python3
"""
SSE Graph 엔드포인트 테스트 스크립트
http://115.71.36.57/api/models/fine-tuning/sse-graph/12 엔드포인트를 지속적으로 요청하여
상태가 canceled와 200 사이를 왔다갔다 하는 문제를 확인합니다.
"""

import requests
import time
import json
from datetime import datetime
from typing import Optional

class SSETestClient:
    def __init__(self, base_url: str, model_id: int):
        self.base_url = base_url.rstrip('/')
        self.model_id = model_id
        self.endpoint = f"{self.base_url}/api/models/fine-tuning/sse-graph/{model_id}"
        self.session = requests.Session()
        
    def test_single_request(self, timeout: int = 10) -> dict:
        """단일 SSE 요청을 테스트하고 결과를 반환합니다."""
        result = {
            'timestamp': datetime.now().isoformat(),
            'status_code': None,
            'response_time': None,
            'event_count': 0,
            'error': None,
            'success': False
        }
        
        start_time = time.time()
        try:
            response = self.session.get(
                self.endpoint,
                stream=True,
                timeout=timeout,
                headers={
                    'Accept': 'text/event-stream',
                    'Cache-Control': 'no-cache',
                    'Connection': 'keep-alive'
                }
            )
            
            result['status_code'] = response.status_code
            result['response_time'] = time.time() - start_time
            
            if response.status_code == 200:
                result['success'] = True
                # SSE 이벤트 읽기
                try:
                    for line in response.iter_lines(decode_unicode=True):
                        if line:
                            if line.startswith('data: '):
                                result['event_count'] += 1
                                data = line[6:]  # 'data: ' 제거
                                try:
                                    parsed_data = json.loads(data)
                                    print(f"[{result['event_count']}] Event received: {json.dumps(parsed_data, indent=2)[:200]}...")
                                except json.JSONDecodeError:
                                    print(f"[{result['event_count']}] Non-JSON data: {data[:100]}")
                            elif line.startswith(':'):
                                # SSE comment, 무시
                                pass
                        if time.time() - start_time >= timeout:
                            break
                except requests.exceptions.ChunkedEncodingError as e:
                    result['error'] = f"ChunkedEncodingError: {str(e)}"
                    result['success'] = False
                except Exception as e:
                    result['error'] = f"Error reading stream: {str(e)}"
                    result['success'] = False
            else:
                result['error'] = f"Non-200 status code: {response.status_code}"
                result['success'] = False
                
        except requests.exceptions.Timeout:
            result['error'] = f"Request timeout after {timeout} seconds"
            result['success'] = False
        except requests.exceptions.ConnectionError as e:
            result['error'] = f"Connection error: {str(e)}"
            result['success'] = False
        except Exception as e:
            result['error'] = f"Unexpected error: {str(e)}"
            result['success'] = False
        finally:
            result['response_time'] = time.time() - start_time
            
        return result
    
    def test_continuous_requests(self, count: int = 10, interval: float = 2.0, request_timeout: int = 5):
        """연속적인 요청을 보내서 상태 변화를 확인합니다."""
        print(f"\n{'='*80}")
        print(f"SSE Graph 엔드포인트 연속 테스트 시작")
        print(f"Endpoint: {self.endpoint}")
        print(f"요청 횟수: {count}, 요청 간격: {interval}초, 요청 타임아웃: {request_timeout}초")
        print(f"{'='*80}\n")
        
        results = []
        success_count = 0
        error_count = 0
        
        for i in range(1, count + 1):
            print(f"\n[요청 {i}/{count}]")
            result = self.test_single_request(timeout=request_timeout)
            results.append(result)
            
            if result['success']:
                success_count += 1
                print(f"✓ 성공 - Status: {result['status_code']}, "
                      f"이벤트 수: {result['event_count']}, "
                      f"응답 시간: {result['response_time']:.2f}초")
            else:
                error_count += 1
                print(f"✗ 실패 - Status: {result['status_code']}, "
                      f"에러: {result['error']}, "
                      f"응답 시간: {result['response_time']:.2f}초")
            
            if i < count:
                time.sleep(interval)
        
        # 결과 요약
        print(f"\n{'='*80}")
        print(f"테스트 결과 요약")
        print(f"{'='*80}")
        print(f"총 요청 수: {count}")
        print(f"성공: {success_count} ({success_count/count*100:.1f}%)")
        print(f"실패: {error_count} ({error_count/count*100:.1f}%)")
        
        # 상태 코드별 통계
        status_codes = {}
        for r in results:
            code = r['status_code']
            if code:
                status_codes[code] = status_codes.get(code, 0) + 1
        
        print(f"\n상태 코드별 통계:")
        for code, count in sorted(status_codes.items()):
            print(f"  {code}: {count}회")
        
        # 에러 유형별 통계
        error_types = {}
        for r in results:
            if r['error']:
                error_type = r['error'].split(':')[0]
                error_types[error_type] = error_types.get(error_type, 0) + 1
        
        if error_types:
            print(f"\n에러 유형별 통계:")
            for error_type, count in sorted(error_types.items()):
                print(f"  {error_type}: {count}회")
        
        return results


def main():
    base_url = "http://115.71.36.57"
    model_id = 12
    
    client = SSETestClient(base_url, model_id)
    
    # 연속 요청 테스트
    results = client.test_continuous_requests(
        count=20,  # 20번 요청
        interval=1.0,  # 1초 간격
        request_timeout=5  # 각 요청 5초 타임아웃
    )
    
    # 결과를 파일로 저장
    with open('/tmp/sse_test_results.json', 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n상세 결과가 /tmp/sse_test_results.json에 저장되었습니다.")


if __name__ == "__main__":
    main()

