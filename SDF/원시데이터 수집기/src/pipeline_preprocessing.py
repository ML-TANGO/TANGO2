from typing import Any, Dict, Optional, Tuple
from datetime import datetime
import json
from pathlib import Path

import pandas as pd

from src.processing.time_sync import align_time_series


def _find_metadata_file(saved_files: Dict[str, str]) -> Optional[str]:
    for file_key, file_path in saved_files.items():
        if file_key == 'metadata':
            return file_path
    return None


def _load_metadata(metadata_file: Optional[str]) -> Tuple[Dict[str, Any], str]:
    if not metadata_file or not Path(metadata_file).exists():
        raise ValueError("메타데이터 파일을 찾을 수 없습니다.", metadata_file)

    if metadata_file.endswith('.json'):
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        timestamp = metadata.get('timestamp', datetime.now().strftime("%Y%m%d_%H%M%S"))
    elif metadata_file.endswith('.csv'):
        metadata_df = pd.read_csv(metadata_file, encoding='utf-8')
        metadata = {}
        for _, row in metadata_df.iterrows():
            key = row['key']
            value = row['value']
            if key.startswith('config_'):
                config_key = key.replace('config_', '')
                if 'config' not in metadata:
                    metadata['config'] = {}
                metadata['config'][config_key] = value
            elif key.startswith('output_file_'):
                output_key = key.replace('output_file_', '')
                if 'output_files' not in metadata:
                    metadata['output_files'] = {}
                metadata['output_files'][output_key] = value
            elif key == 'sensor_file_mapping':
                metadata['sensor_file_mapping'] = json.loads(value)
            elif key == 'sensor_categories':
                metadata['sensor_categories'] = json.loads(value)
            elif key == 'table_queries':
                metadata['table_queries'] = json.loads(value)
            else:
                metadata[key] = value

        timestamp = metadata.get('timestamp', datetime.now().strftime("%Y%m%d_%H%M%S"))
    else:
        raise ValueError(f"지원하지 않는 메타데이터 파일 형식: {metadata_file}")

    if 'T' in timestamp:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        timestamp = dt.strftime("%Y%m%d_%H%M%S")

    return metadata, timestamp


def _load_data_file(file_path: str) -> Optional[pd.DataFrame]:
    p = Path(file_path)
    if not p.exists():
        return None

    if str(p).endswith('.json'):
        with open(p, 'r', encoding='utf-8') as f:
            rows = json.load(f)
        return pd.DataFrame(rows)
    if str(p).endswith('.csv'):
        return pd.read_csv(p, encoding='utf-8')
    return None


def _build_frames(
    saved_files: Dict[str, str],
    metadata: Dict[str, Any],
    timestamp_tables: Dict[str, str],
) -> Tuple[Dict[str, pd.DataFrame], Dict[str, str], Dict[str, Any]]:
    frames: Dict[str, pd.DataFrame] = {}
    time_cols: Dict[str, str] = {}

    context = {
        'site_id_list': [],
        'facility_id_dict': {},
    }

    for table_name, file_path in saved_files.items():
        if table_name == 'metadata':
            continue

        parts = table_name.split('_')
        base_key = None
        sensor_type = None

        if len(parts) >= 3 and parts[0] in ['In', 'Out']:
            facility_status = parts[0]

            sensor_id = None
            channel = None

            if len(parts) >= 3:
                if parts[1] == 'agsmotor' and len(parts) >= 4 and parts[2] == 'green':
                    sensor_type = 'agsmotor_green'
                    for i, part in enumerate(parts[3:], 3):
                        if '-' in part and len(part) > 10:
                            sensor_id = part
                            if i + 1 < len(parts) and parts[i + 1].startswith('ch'):
                                channel = parts[i + 1][2:]
                            break
                else:
                    sensor_type = parts[1]
                    sensor_id = parts[2]
                    if sensor_type == 'agsmotor':
                        sensor_type = 'agsmotor_green'
                    if len(parts) >= 4 and parts[3].startswith('ch'):
                        channel = parts[3][2:]

            if sensor_type and sensor_id:
                site_id = None
                facility_id = None

                metadata_key = f"{facility_status}_{sensor_type}_{sensor_id}"
                if channel:
                    metadata_key = f"{facility_status}_{sensor_type}_{sensor_id}_ch{channel}"

                print(f"🔍 디버그: metadata에서 찾을 키: {metadata_key}")

                if 'sensor_file_mapping' in metadata and metadata_key in metadata['sensor_file_mapping']:
                    sensor_info = metadata['sensor_file_mapping'][metadata_key]
                    site_id = sensor_info.get('site_id')
                    facility_id = sensor_info.get('facility_id')
                    print(f"🔍 디버그: 찾은 site_id: {site_id}, facility_id: {facility_id}")
                    context['site_id_list'].append(site_id)
                    if facility_id is not None:
                        context['facility_id_dict'][site_id] = facility_id
                else:
                    print(f"🔍 디버그: metadata에서 키를 찾지 못함: {metadata_key}")

                if channel:
                    base_key = f"{facility_status}_{sensor_type}_{sensor_id}_ch{channel}"
                else:
                    base_key = f"{facility_status}_{sensor_type}_{sensor_id}"

                if site_id and facility_id:
                    base_key = f"{base_key}_site_{site_id}_facility_{facility_id}"

                if base_key not in frames:
                    frames[base_key] = []
                    time_cols[base_key] = timestamp_tables.get(sensor_type, 'ts')
            else:
                base_key = table_name
                if table_name not in frames:
                    frames[table_name] = []
                    time_cols[table_name] = 'ts'

        df = _load_data_file(file_path)
        if df is None:
            continue

        if base_key and (sensor_type or 'agsmotor_green' in table_name):
            frames[base_key].append(df)
        else:
            frames[table_name] = df

        if 'ts' in df.columns:
            time_cols[base_key or table_name] = 'ts'
        else:
            inferred_type = parts[1] if len(parts) >= 2 else table_name
            time_col = timestamp_tables.get(inferred_type)
            if time_col and time_col in df.columns:
                time_cols[base_key or table_name] = time_col

    for key, df_list in frames.items():
        if isinstance(df_list, list):
            frames[key] = pd.concat(df_list, ignore_index=True)

    return frames, time_cols, context


def _is_out_table(key: str, saved_files: Dict[str, str]) -> bool:
    return any(table_name.startswith('Out_') for table_name in saved_files.keys() if key in table_name)


def _split_in_out_frames(
    frames: Dict[str, pd.DataFrame],
    saved_files: Dict[str, str],
) -> Tuple[Dict[str, pd.DataFrame], Dict[str, pd.DataFrame], Dict[str, list[str]]]:
    out_frames: Dict[str, pd.DataFrame] = {}
    in_frames: Dict[str, pd.DataFrame] = {}
    channel_group: Dict[str, list[str]] = {}

    print(f"🔍 디버그: 처리할 frames 키 목록: {list(frames.keys())}")

    for key, df in frames.items():
        print(f"🔍 디버그: 처리 중인 키: {key}")
        print(f"🔍 디버그: 데이터프레임 컬럼: {list(df.columns)}")
        print(f"🔍 디버그: 데이터프레임 크기: {len(df)}")

        site_id_cols = [col for col in df.columns if col == 'site_id']
        print(f"🔍 디버그: site_id 컬럼: {site_id_cols}")
        print(f"🔍 디버그: 키: {key}, 데이터프레임 컬럼: {list(df.columns)}")
        print(f"🔍 디버그: site_id 컬럼 존재 여부: {'site_id' in df.columns}")

        key_parts = key.split('_')
        parsed_site_id = None
        parsed_facility_id = None
        for i, part in enumerate(key_parts):
            if part == 'site' and i + 1 < len(key_parts):
                parsed_site_id = key_parts[i + 1 : i + 3]
            elif part == 'facility' and i + 1 < len(key_parts):
                parsed_facility_id = key_parts[i + 1]

        print(f"🔍 디버그: 파싱된 site_id: {parsed_site_id}, facility_id: {parsed_facility_id}")

        if site_id_cols:
            site_id_col = site_id_cols[0]
            unique_sites = df[site_id_col].dropna().unique()
            print(f"🔍 디버그: 고유 site_id: {unique_sites}")

            for site_id in unique_sites:
                site_data = df[df[site_id_col] == site_id].copy()
                print(f"🔍 디버그: site_id {site_id} 데이터 크기: {len(site_data)}")

                if 'agsmotor' in key:
                    sensor_type = 'agsmotor_green'
                else:
                    sensor_type = key.split('_')[1] if '_' in key else key
                print(f"🔍 디버그: 추출된 sensor_type: {sensor_type}")

                if sensor_type == 'agsmotor_green' and 'probe' in site_data.columns:
                    print('🔍 디버그: agsmotor_green 데이터, probe 컬럼 있음')
                    unique_probes = site_data['probe'].dropna().unique()
                    print(f"🔍 디버그: 고유 probe 값: {unique_probes}")

                    for probe_value in unique_probes:
                        channel_data = site_data[site_data['probe'] == probe_value].copy()
                        print(f"🔍 디버그: probe {probe_value} 채널 데이터 크기: {len(channel_data)}")
                        print(f"🔍 디버그: 채널 데이터 컬럼: {list(channel_data.columns)}")

                        if _is_out_table(key, saved_files):
                            print('🔍 디버그: Out_ 테이블 처리 - 컬럼명 변경')
                            data_cols = [
                                col
                                for col in channel_data.columns
                                if col not in ['ts', site_id_col, 'sensor_id', 'probe']
                                and not col.startswith('site_')
                                and not col.startswith('facility_')
                            ]
                            print(f"🔍 디버그: 데이터 컬럼: {data_cols}")

                            rename_dict = {}
                            for col in data_cols:
                                if col == 'open_rate':
                                    new_col = f"out_open_rate_ch{int(probe_value)}"
                                else:
                                    new_col = col
                                rename_dict[col] = new_col
                                print(f"🔍 디버그: 컬럼명 변경 {col} -> {new_col}")

                            channel_data = channel_data.rename(columns=rename_dict)
                            print(f"🔍 디버그: 컬럼명 변경 후: {list(channel_data.columns)}")

                            site_facility_key = f"out_{site_id}_{parsed_facility_id}_ch{int(probe_value)}"
                            if site_facility_key not in out_frames:
                                out_frames[site_facility_key] = []
                            out_frames[site_facility_key].append(channel_data)
                            print(f"🔍 디버그: Out_ 프레임에 추가: {site_facility_key}")
                        else:
                            data_cols = [
                                col
                                for col in channel_data.columns
                                if col not in ['ts', site_id_col, 'sensor_id', 'probe']
                                and not col.startswith('site_')
                                and not col.startswith('facility_')
                            ]
                            rename_dict = {}
                            for col in data_cols:
                                if col == 'open_rate':
                                    new_col = f"open_rate_ch{int(probe_value)}"
                                else:
                                    new_col = f"{col}"
                                rename_dict[col] = new_col
                                print(f"🔍 디버그: 컬럼명 변경 {col} -> {new_col}")

                            channel_data = channel_data.rename(columns=rename_dict)
                            print(f"🔍 디버그: 컬럼명 변경 후: {list(channel_data.columns)}")

                            site_facility_key = f"in_{site_id}_{parsed_facility_id}_ch{int(probe_value)}"
                            sf_gkey = f"in_{site_id}_{parsed_facility_id}"
                            if sf_gkey not in channel_group:
                                channel_group[sf_gkey] = [site_facility_key]
                            else:
                                channel_group[sf_gkey].append(site_facility_key)

                            if site_facility_key not in in_frames:
                                in_frames[site_facility_key] = []
                            in_frames[site_facility_key].append(channel_data)
                            print(f"🔍 디버그: In_ 프레임에 추가: {site_facility_key}")
                else:
                    print('🔍 디버그: agsmotor_green이 아닌 다른 센서 처리')
                    if _is_out_table(key, saved_files):
                        print('🔍 디버그: Out_ 테이블 처리 - 컬럼명 변경')
                        data_cols = [
                            col
                            for col in site_data.columns
                            if col not in ['ts', site_id_col, 'sensor_id', 'probe']
                            and not col.startswith('site_')
                            and not col.startswith('facility_')
                        ]
                        print(f"🔍 디버그: 데이터 컬럼: {data_cols}")

                        rename_dict = {col: f"out_{col}" for col in data_cols}
                        site_data = site_data.rename(columns=rename_dict)
                        print(f"🔍 디버그: 컬럼명 변경 후: {list(site_data.columns)}")

                        if 'probe' in site_data.columns:
                            unique_probes = site_data['probe'].dropna().unique()
                            if len(unique_probes) > 0:
                                probe_value = unique_probes[0]
                                site_facility_key = f"out_{site_id}_{parsed_facility_id}_ch{int(probe_value)}"
                            else:
                                site_facility_key = f"out_{site_id}_{parsed_facility_id}"
                        else:
                            site_facility_key = f"out_{site_id}_{parsed_facility_id}"

                        if site_facility_key not in out_frames:
                            out_frames[site_facility_key] = []
                        out_frames[site_facility_key].append(site_data)
                        print(f"🔍 디버그: Out_ 프레임에 추가: {site_facility_key}")
                    else:
                        print('🔍 디버그: In_ 테이블 처리')
                        if 'probe' in site_data.columns:
                            unique_probes = site_data['probe'].dropna().unique()
                            if len(unique_probes) > 0:
                                probe_value = unique_probes[0]
                                site_facility_key = f"in_{site_id}_{parsed_facility_id}_ch{int(probe_value)}"
                                sf_gkey = f"in_{site_id}_{parsed_facility_id}"
                                if sf_gkey not in channel_group:
                                    channel_group[sf_gkey] = [site_facility_key]
                                else:
                                    channel_group[sf_gkey].append(site_facility_key)
                            else:
                                site_facility_key = f"in_{site_id}_{parsed_facility_id}"
                        else:
                            site_facility_key = f"in_{site_id}_{parsed_facility_id}"

                        if site_facility_key not in in_frames:
                            in_frames[site_facility_key] = []
                        in_frames[site_facility_key].append(site_data)
                        print(f"🔍 디버그: In_ 프레임에 추가: {site_facility_key}")
        else:
            sensor_type = key.split('_')[0] if '_' in key else key

            if sensor_type == 'agsmotor_green' and 'probe' in df.columns:
                unique_probes = df['probe'].dropna().unique()
                for probe_value in unique_probes:
                    channel_data = df[df['probe'] == probe_value].copy()
                    if _is_out_table(key, saved_files):
                        data_cols = [
                            col
                            for col in channel_data.columns
                            if col not in ['ts', 'sensor_id', 'probe']
                            and not col.startswith('site_')
                            and not col.startswith('facility_')
                        ]
                        rename_dict = {}
                        for col in data_cols:
                            if col == 'open_rate':
                                rename_dict[col] = f"out_open_rate_ch{int(probe_value)}"
                            else:
                                rename_dict[col] = f"out_{col}"
                        channel_data = channel_data.rename(columns=rename_dict)
                        out_frames[f"no_site_ch{int(probe_value)}"] = channel_data
                    else:
                        in_frames[f"no_site_ch{int(probe_value)}"] = channel_data
            else:
                if _is_out_table(key, saved_files):
                    data_cols = [
                        col
                        for col in df.columns
                        if col not in ['ts', 'sensor_id']
                        and not col.startswith('site_')
                        and not col.startswith('facility_')
                    ]
                    rename_dict = {col: f"out_{col}" for col in data_cols}
                    out_frames['no_site'] = df.rename(columns=rename_dict)
                else:
                    in_frames['no_site'] = df

    return out_frames, in_frames, channel_group


def _concat_frame_lists(frame_map: Dict[str, Any]) -> None:
    for key in list(frame_map.keys()):
        if isinstance(frame_map[key], list):
            frame_map[key] = pd.concat(frame_map[key], ignore_index=True)


def _merge_channel_group_frames(in_frames: Dict[str, pd.DataFrame], channel_group: Dict[str, list[str]]) -> None:
    for g_key in channel_group:
        ins_key = channel_group[g_key][0]
        print(len(channel_group[g_key]))
        print(g_key, ins_key)
        if g_key in in_frames:
            channel_group[g_key].append(g_key)
            print('****')
        if ins_key in in_frames:
            for key in channel_group[g_key]:
                print(type(in_frames[key]))
            in_frames[g_key] = pd.concat(
                [in_frames[key] for key in channel_group[g_key]],
                ignore_index=True,
                join='outer',
            )
            for key in channel_group[g_key]:
                if key in in_frames and key != g_key:
                    del in_frames[key]


def _parse_merge_key(key: str) -> str:
    parts = key.split('_')
    if len(parts) >= 5 and parts[4].startswith('ch'):
        return f"{parts[1]}_{parts[2]}_{parts[3]}_{parts[4]}"
    if len(parts) >= 4:
        return f"{parts[1]}_{parts[2]}_{parts[3]}_no_channel"
    return key


def _load_weather_df(weather_file: Optional[str]) -> Optional[pd.DataFrame]:
    if weather_file is None:
        return None

    weather_df = pd.read_csv(weather_file)
    print('디버그: weather_df', weather_df.head())

    required_weather_cols = ['YYMMDDHHMI', 'SS', 'SI']
    available_cols = [col for col in required_weather_cols if col in weather_df.columns]

    if not available_cols:
        print(f"⚠️ 기상 데이터에 필요한 컬럼이 없습니다. 필요한 컬럼: {required_weather_cols}")
        return None

    weather_df = weather_df[available_cols]
    print(f"🔍 디버그: 기상 데이터 컬럼 선택: {available_cols}")

    if 'YYMMDDHHMI' in weather_df.columns:
        weather_df['ts'] = pd.to_datetime(weather_df['YYMMDDHHMI'], format='%Y%m%d%H%M', utc=True)
        weather_df = weather_df.drop(columns=['YYMMDDHHMI'])
        print('🔍 디버그: 기상 시간 컬럼 YYMMDDHHMI -> ts로 변환 완료 (UTC 타임존 적용)')
    else:
        print('⚠️ 기상 데이터에 YYMMDDHHMI 컬럼이 없습니다')

    return weather_df


def _merge_out_in_frames(
    out_frames: Dict[str, pd.DataFrame],
    in_frames: Dict[str, pd.DataFrame],
    weather_df: Optional[pd.DataFrame],
) -> Dict[str, pd.DataFrame]:
    combined_frames: Dict[str, pd.DataFrame] = {}

    all_keys = set(out_frames.keys()) | set(in_frames.keys())
    print('디버그: all_keys', all_keys)

    out_parsed_keys = {key: _parse_merge_key(key) for key in out_frames}
    in_parsed_keys = {key: _parse_merge_key(key) for key in in_frames}

    print('디버그: out_parsed_keys', out_parsed_keys)
    print('디버그: in_parsed_keys', in_parsed_keys)

    for out_key in out_frames:
        out_parsed = out_parsed_keys[out_key]

        matching_in_keys = [
            in_key
            for in_key, in_parsed in in_parsed_keys.items()
            if in_parsed.split('_')[0:2] == out_parsed.split('_')[0:2]
        ]

        print(f"디버그: matching_in_keys for {out_key}: {matching_in_keys}")

        for in_key in matching_in_keys:
            print(f"🔍 디버그: 병합 가능한 키 발견: {out_key} <-> {in_key} (파싱된: {out_parsed})")

            out_df = out_frames[out_key]
            in_df = in_frames[in_key]

            site_id_cols = [col for col in out_df.columns if 'site_id' in col.lower()]
            site_id_col = site_id_cols[0] if site_id_cols else None

            print('디버그: out_df.columns', out_df.columns)
            print('디버그: in_df.columns', in_df.columns)

            if 'ts' in out_df.columns:
                try:
                    out_df['ts'] = pd.to_datetime(out_df['ts'], format='ISO8601', utc=True)
                except Exception:
                    try:
                        out_df['ts'] = pd.to_datetime(out_df['ts'], utc=True)
                    except Exception:
                        print(f"⚠️ out_df ts 컬럼 변환 실패: {out_df['ts'].iloc[0] if len(out_df) > 0 else 'N/A'}")
                        continue

            if 'ts' in in_df.columns:
                try:
                    in_df['ts'] = pd.to_datetime(in_df['ts'], format='ISO8601', utc=True)
                except Exception:
                    try:
                        in_df['ts'] = pd.to_datetime(in_df['ts'], utc=True)
                    except Exception:
                        print(f"⚠️ in_df ts 컬럼 변환 실패: {in_df['ts'].iloc[0] if len(in_df) > 0 else 'N/A'}")
                        continue

            if site_id_col and 'ts' in out_df.columns and 'ts' in in_df.columns:
                if not pd.api.types.is_datetime64_any_dtype(out_df['ts']) or not pd.api.types.is_datetime64_any_dtype(in_df['ts']):
                    print(f"⚠️ ts 컬럼 타입 불일치: out_df[{out_df['ts'].dtype}] vs in_df[{in_df['ts'].dtype}]")
                    continue

                combined = pd.merge(out_df, in_df, on='ts', how='outer', suffixes=('', '_dup'))

                if weather_df is not None:
                    combined = pd.merge_asof(
                        combined,
                        weather_df,
                        on='ts',
                        direction='nearest',
                        tolerance=pd.Timedelta('90min'),
                        suffixes=('', '_weather'),
                    )
                    print(f"🔍 디버그: 기상 데이터 병합 완료 (90분 이내 근접 조인, 컬럼: {list(weather_df.columns)})")

                dup_cols = [col for col in combined.columns if col.endswith('_dup') and not col.startswith('open_rate')]
                if dup_cols:
                    combined = combined.drop(columns=dup_cols)
                    print(f"🔍 디버그: 중복 컬럼 제거됨 (open_rate 관련 제외): {dup_cols}")

                combined[site_id_col] = out_df[site_id_col].iloc[0] if len(out_df) > 0 else None

                facility_id_cols = [col for col in in_df.columns if 'facility_id' in col.lower()]
                if facility_id_cols:
                    facility_id_col = facility_id_cols[0]
                    combined[facility_id_col] = in_df[facility_id_col].iloc[0] if len(in_df) > 0 else None

                combined_key = in_key[len('in_'):]
                combined_frames[combined_key] = combined
            else:
                combined_key = in_key[len('in_'):]
                combined_frames[combined_key] = pd.concat([out_df, in_df], ignore_index=True)

        if len(matching_in_keys) == 0:
            combined_frames[out_key[len('out_'):]] = out_frames[out_key]

    for in_key in in_frames:
        is_merged = False
        if in_key[len('in_'):] in combined_frames:
            is_merged = True
            break

        if not is_merged:
            combined_frames[in_key] = in_frames[in_key]

    return combined_frames


def _cleanup_aligned_frame(aligned_single: pd.DataFrame) -> pd.DataFrame:
    sensor_id_cols = [col for col in aligned_single.columns if col == 'sensor_id']
    if sensor_id_cols:
        aligned_single = aligned_single.drop(columns=sensor_id_cols)
        print('🔍 디버그: sensor_id 컬럼 제거됨')

    date_time_cols = [col for col in aligned_single.columns if col in ['date', 'time']]
    if date_time_cols:
        aligned_single = aligned_single.drop(columns=date_time_cols)
        print(f"🔍 디버그: date/time 컬럼 제거됨: {date_time_cols}")

    site_id_prefix_cols = [col for col in aligned_single.columns if col.startswith('site_id_')]
    if site_id_prefix_cols:
        aligned_single = aligned_single.drop(columns=site_id_prefix_cols)
        print(f"🔍 디버그: site_id_ 접두사 컬럼 제거됨: {site_id_prefix_cols}")

    if 'probe' in aligned_single.columns:
        aligned_single = aligned_single.drop(columns=['probe'])

    wind_cols = [col for col in aligned_single.columns if col.startswith('wind_')]
    if wind_cols:
        aligned_single = aligned_single.drop(columns=wind_cols)
        print(f"🔍 디버그: wind_ 접두사 컬럼 제거됨: {wind_cols}")

    return aligned_single


def _align_frames_by_site_facility(
    frames: Dict[str, pd.DataFrame],
    config: Dict[str, Any],
) -> Dict[str, pd.DataFrame]:
    print(f"🔍 디버그: 처리할 frames 키: {list(frames.keys())}")
    final_results: Dict[str, pd.DataFrame] = {}

    for key, df in frames.items():
        print(f"🔍 디버그: 처리할 프레임: {key}, 크기: {len(df)}")

        site_id_cols = [col for col in df.columns if 'site_id' in col.lower() and not col.startswith('site_id_')]
        facility_id_cols = [
            col for col in df.columns if 'facility_id' in col.lower() and not col.startswith('facility_id_')
        ]

        if not site_id_cols:
            print(f"🔍 디버그: site_id 없는 프레임: {key}")
            final_results[key] = df
            continue

        site_id_col = site_id_cols[0]
        unique_sites = df[site_id_col].dropna().unique()

        for site_id in unique_sites:
            site_df = df[df[site_id_col] == site_id].copy()

            if facility_id_cols:
                facility_id_col = facility_id_cols[0]
                unique_facilities = site_df[facility_id_col].dropna().unique()

                for facility_id in unique_facilities:
                    filtered_df = site_df[site_df[facility_id_col] == facility_id].copy()
                    if len(filtered_df) == 0:
                        continue

                    result_key = f"site_{site_id}_facility_{facility_id}"
                    print(f"🔍 디버그: {result_key} 처리 시작, 크기: {len(filtered_df)}")

                    single_frames = {result_key: filtered_df.copy()}
                    single_time_cols = {result_key: 'ts' if 'ts' in filtered_df.columns else None}
                    aligned_single = align_time_series(
                        frames=single_frames,
                        time_cols=single_time_cols,
                        base_key=result_key,
                        tolerance=config.get('processing_tolerance', '120s'),
                        resample_to_min=config.get('resample_to_minute', True),
                        minute_agg=config.get('minute_aggregation', 'first'),
                        fill_method=config.get('fill_method', 'nearest'),
                    )

                    aligned_single = _cleanup_aligned_frame(aligned_single)
                    out = aligned_single

                    if 'ts' in out.columns:
                        out = out.set_index('ts')
                        out.index.name = 'index'
                        out = out.reset_index()

                    final_results[result_key] = out
                    print(f"🔍 디버그: {result_key} 처리 완료, 최종 크기: {len(out)}")
            else:
                result_key = f"site_{site_id}"
                print(f"🔍 디버그: {result_key} 처리 시작 (facility_id 없음), 크기: {len(site_df)}")

                single_frames = {result_key: site_df}
                single_time_cols = {result_key: 'ts' if 'ts' in site_df.columns else None}
                aligned_single = align_time_series(
                    frames=single_frames,
                    time_cols=single_time_cols,
                    base_key=result_key,
                    tolerance=config.get('processing_tolerance', '120s'),
                    resample_to_min=config.get('resample_to_minute', True),
                    minute_agg=config.get('minute_aggregation', 'first'),
                    fill_method=config.get('fill_method', 'nearest'),
                )

                sensor_id_cols = [col for col in aligned_single.columns if 'sensor_id' in col.lower()]
                aligned_single = aligned_single.drop(columns=sensor_id_cols)

                date_time_cols = [col for col in aligned_single.columns if col in ['date', 'time']]
                aligned_single = aligned_single.drop(columns=date_time_cols)

                site_id_prefix_cols = [col for col in aligned_single.columns if col.startswith('site_id_')]
                aligned_single = aligned_single.drop(columns=site_id_prefix_cols)

                out = aligned_single
                if 'ts' in out.columns:
                    out = out.set_index('ts')
                    out.index.name = 'index'
                    out = out.reset_index()

                final_results[result_key] = out
                print(f"🔍 디버그: {result_key} 처리 완료 (facility_id 없음), 최종 크기: {len(out)}")

    return final_results


def _save_final_results(final_results: Dict[str, pd.DataFrame], output_dir: str) -> Dict[str, str]:
    output_paths: Dict[str, str] = {}
    proc_dir = Path(output_dir)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    processed_dir = proc_dir / f"processed_{timestamp}"
    processed_dir.mkdir(exist_ok=True)
    print(f"🔍 디버그: 전처리 결과 저장 폴더: {processed_dir}")

    for result_key, df in final_results.items():
        cols_to_remove = []
        for col in df.columns:
            if col == 'open_rate':
                cols_to_remove.append(col)
            elif col == 'open_rate_dup':
                ch_cols = [c for c in df.columns if c.startswith('open_rate_ch') and c != 'open_rate_dup']
                if ch_cols:
                    first_ch_col = ch_cols[0]
                    df[col] = df[first_ch_col]
                    print(f"🔍 디버그: {col} -> {first_ch_col}로 변환")
                    cols_to_remove.append(col)
            elif col.startswith('site_id_'):
                cols_to_remove.append(col)
            elif col.startswith('facility_id_'):
                cols_to_remove.append(col)

        if cols_to_remove:
            df = df.drop(columns=cols_to_remove)
            print(f"🔍 디버그: {result_key}에서 컬럼 제거: {cols_to_remove}")

        filename = f"{result_key}_{timestamp}.json"
        file_path = processed_dir / filename

        file_path_csv = file_path.with_suffix('.csv')
        df.to_csv(file_path_csv, index=False, encoding='utf-8')

        output_paths[result_key] = str(file_path)
        print(f"🔍 디버그: {result_key} 파일 저장 완료: {file_path}")

    print(f"🔍 디버그: 최종 결과 파일: {list(output_paths.keys())}")
    return output_paths


def run_preprocessing(
    pipeline_instance,
    saved_files: Dict[str, str],
    output_dir: str,
    config: Dict[str, Any],
    timestamp_tables: Dict[str, str],
) -> Dict[str, str]:
    if not config.get('run_processing', True):
        return {}

    metadata_file = _find_metadata_file(saved_files)
    metadata, _ = _load_metadata(metadata_file)

    frames, time_cols, _ = _build_frames(
        saved_files=saved_files,
        metadata=metadata,
        timestamp_tables=timestamp_tables,
    )

    if not frames:
        return {}

    out_frames, in_frames, channel_group = _split_in_out_frames(frames=frames, saved_files=saved_files)
    _concat_frame_lists(out_frames)
    _concat_frame_lists(in_frames)
    _merge_channel_group_frames(in_frames=in_frames, channel_group=channel_group)

    weather_df = _load_weather_df(pipeline_instance.weather_file)
    frames = _merge_out_in_frames(out_frames=out_frames, in_frames=in_frames, weather_df=weather_df)

    for key, df in frames.items():
        time_cols[key] = 'ts' if 'ts' in df.columns else None

    final_results = _align_frames_by_site_facility(frames=frames, config=config)
    return _save_final_results(final_results=final_results, output_dir=output_dir)
