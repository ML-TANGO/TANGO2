#!/usr/bin/env python3
"""
SSE Graph 엔드포인트 지속 테스트 스크립트
pod 내부에서 localhost로 요청하여 SSE 스트림의 안정성을 확인합니다.
"""

import requests
import time
import json
from datetime import datetime
from typing import List, Dict

class SSEContinuousTest:
    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self.session = requests.Session()
        
    def test_stream_stability(self, duration: int = 60) -> Dict:
        """지속적인 SSE 스트림을 테스트하고 안정성을 확인합니다."""
        print(f"\n{'='*80}")
        print(f"SSE 스트림 안정성 테스트 시작")
        print(f"Endpoint: {self.endpoint}")
        print(f"테스트 지속 시간: {duration}초")
        print(f"{'='*80}\n")
        
        events = []
        errors = []
        start_time = time.time()
        last_data = None
        empty_count = 0
        data_count = 0
        toggle_count = 0  # 빈 데이터와 데이터 사이 전환 횟수
        
        try:
            response = self.session.get(
                self.endpoint,
                stream=True,
                timeout=duration + 10,
                headers={
                    'Accept': 'text/event-stream',
                    'Cache-Control': 'no-cache',
                    'Connection': 'keep-alive'
                }
            )
            
            if response.status_code != 200:
                return {
                    'success': False,
                    'error': f"Non-200 status code: {response.status_code}",
                    'events': [],
                    'errors': []
                }
            
            print("SSE 스트림 연결 성공. 이벤트 수신 중...\n")
            
            for line in response.iter_lines(decode_unicode=True):
                elapsed = time.time() - start_time
                
                if elapsed >= duration:
                    print(f"\n테스트 시간 종료 ({duration}초)")
                    break
                
                if line:
                    if line.startswith('data: '):
                        data_str = line[6:]  # 'data: ' 제거
                        try:
                            data = json.loads(data_str)
                            graph = data.get('graph', {})
                            is_empty = len(graph) == 0
                            
                            events.append({
                                'timestamp': elapsed,
                                'data': data,
                                'is_empty': is_empty
                            })
                            
                            # 상태 전환 감지
                            if last_data is not None:
                                if last_data != is_empty:
                                    toggle_count += 1
                                    print(f"[{elapsed:.1f}초] 상태 전환 감지: "
                                          f"{'빈 데이터' if last_data else '데이터 있음'} -> "
                                          f"{'빈 데이터' if is_empty else '데이터 있음'}")
                            
                            if is_empty:
                                empty_count += 1
                                if empty_count % 10 == 0:
                                    print(f"[{elapsed:.1f}초] 빈 데이터 이벤트 (총 {empty_count}회)")
                            else:
                                data_count += 1
                                graph_keys = list(graph.keys())
                                print(f"[{elapsed:.1f}초] 데이터 이벤트 (총 {data_count}회, "
                                      f"그래프 키: {graph_keys})")
                            
                            last_data = is_empty
                            
                        except json.JSONDecodeError as e:
                            errors.append({
                                'timestamp': elapsed,
                                'error': f"JSON decode error: {str(e)}",
                                'data': data_str[:100]
                            })
                            print(f"[{elapsed:.1f}초] JSON 파싱 오류: {str(e)}")
                            
        except requests.exceptions.ChunkedEncodingError as e:
            errors.append({
                'timestamp': time.time() - start_time,
                'error': f"ChunkedEncodingError: {str(e)}"
            })
            print(f"\nChunkedEncodingError 발생: {str(e)}")
        except Exception as e:
            errors.append({
                'timestamp': time.time() - start_time,
                'error': f"Unexpected error: {str(e)}"
            })
            print(f"\n예기치 않은 오류: {str(e)}")
        
        total_time = time.time() - start_time
        
        # 결과 요약
        print(f"\n{'='*80}")
        print(f"테스트 결과 요약")
        print(f"{'='*80}")
        print(f"총 테스트 시간: {total_time:.1f}초")
        print(f"총 이벤트 수: {len(events)}")
        print(f"데이터 있는 이벤트: {data_count}회")
        print(f"빈 데이터 이벤트: {empty_count}회")
        print(f"상태 전환 횟수: {toggle_count}회")
        print(f"오류 수: {len(errors)}")
        
        if toggle_count > 0:
            print(f"\n⚠️  경고: {toggle_count}회의 상태 전환이 감지되었습니다!")
            print(f"   이는 서버에서 빈 데이터와 데이터 사이를 왔다갔다 하고 있음을 의미합니다.")
        
        if errors:
            print(f"\n오류 목록:")
            for error in errors[:10]:  # 최대 10개만 표시
                print(f"  [{error['timestamp']:.1f}초] {error['error']}")
        
        return {
            'success': True,
            'total_time': total_time,
            'total_events': len(events),
            'data_count': data_count,
            'empty_count': empty_count,
            'toggle_count': toggle_count,
            'errors': errors,
            'events': events[:100]  # 최대 100개만 저장
        }


def main():
    endpoint = "http://localhost:8000/api/models/fine-tuning/sse-graph/12"
    
    test = SSEContinuousTest(endpoint)
    result = test.test_stream_stability(duration=60)  # 60초 테스트
    
    # 결과를 파일로 저장
    with open('/tmp/sse_continuous_test_result.json', 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\n상세 결과가 /tmp/sse_continuous_test_result.json에 저장되었습니다.")


if __name__ == "__main__":
    main()

