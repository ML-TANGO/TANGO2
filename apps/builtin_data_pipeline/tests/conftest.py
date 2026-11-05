"""Pytest configuration for apps/builtin_data_pipeline tests.

빌트인 노드 스크립트는 잡 pod 의 `/built_in` 에 평평하게 마운트되어 서로를 그냥
`import dp_sds_ais` 로 부른다(dp_sds_ais_scene 이 그렇게 쓴다). 테스트에서도 같은
경로 해석이 되도록 앱 디렉터리를 sys.path 에 넣는다. 이 스크립트들은 표준 라이브러리만
쓰므로 환경변수나 스텁은 필요 없다.
"""
from __future__ import annotations

import os
import sys

APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if APP_ROOT not in sys.path:
    sys.path.insert(0, APP_ROOT)
