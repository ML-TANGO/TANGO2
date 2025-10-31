import pandas as pd
from typing import List

def load_examples(input_csv_paths: List[str], output_csv_paths: List[str]) -> List[dict]:
    """
    여러 쌍의 CSV 파일에서 Few-Shot 예시를 불러옵니다.
    'file_name'을 기준으로 input.csv의 여러 라인을 합치고 output.csv의 단일 라인과 매칭합니다.
    컬럼명을 포함하여 프롬프트를 구성합니다.
    """
    all_examples = []
    for input_path, output_path in zip(input_csv_paths, output_csv_paths):
        try:
            input_df = pd.read_csv(input_path)
            output_df = pd.read_csv(output_path)

            # 1. 입력 데이터 그룹화: 'file_name'이 같은 행들을 합칩니다.
            if 'file_name' not in input_df.columns:
                print(f"⚠️ 경고: {input_path}에 'file_name' 컬럼이 없습니다. 이 파일을 건너뜁니다.")
                continue

            def aggregate_rows(group):
                other_cols_df = group.drop(columns='file_name')
                # 컬럼명과 데이터를 포함
                col_names = ' '.join(other_cols_df.columns)
                rows_as_str = '\n'.join(other_cols_df.apply(lambda row: ' '.join(row.astype(str)), axis=1))
                return f"{col_names}\n{rows_as_str}"

            aggregated_inputs = input_df.groupby('file_name', sort=False).apply(aggregate_rows).reset_index(name='query')

            # 2. 출력 데이터 준비
            if 'file_name' not in output_df.columns:
                print(f"⚠️ 경고: {output_path}에 'file_name' 컬럼이 없습니다. 이 파일을 건너뜁니다.")
                continue

            output_cols = [col for col in output_df.columns if col != 'file_name']
            output_df['response'] = output_df[output_cols].apply(lambda row: ' '.join(row.astype(str)), axis=1)

            # 3. 입력과 출력을 'file_name' 기준으로 병합
            merged_df = pd.merge(aggregated_inputs, output_df[['file_name', 'response']], on='file_name')

            # 4. 최종 예시 리스트 생성
            pair_examples = merged_df[['query', 'response']].to_dict('records')
            all_examples.extend(pair_examples)

        except FileNotFoundError:
            print(f"⚠️ 경고: 파일을 찾을 수 없습니다: {input_path} 또는 {output_path}")
        except Exception as e:
            print(f"⚠️ 경고: {input_path}, {output_path} 처리 중 오류 발생: {e}")

    return all_examples
