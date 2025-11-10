from utils import settings
import aiomysql
# import asyncio

class ListCursor(aiomysql.cursors.Cursor):
    async def fetchone(self):
        row = await super(ListCursor, self).fetchone()
        if row is not None:
            return list(row)
        return row

    async def fetchall(self):
        rows = await super(ListCursor, self).fetchall()
        return [list(row) for row in rows]

db_config = {
        'host': settings.JF_DB_HOST,
        'port': int(settings.JF_DB_PORT),
        'user': settings.JF_DB_USER,
        'password': settings.JF_DB_PW,
        'db': settings.JF_DB_NAME,
    }


class FetchType:
    ONE = "one"
    ALL = "all"

async def select_query(query, params=None, fetch_type=FetchType.ALL):
    """
    Execute a SELECT query and fetch results asynchronously.
    
    :param query: SELECT query to be executed.
    :param params: Parameters to be passed to the SQL query.
    :param fetch_type: Type of fetch ('all' for fetchall, 'one' for fetchone).
    :return: Query result.
    """

    # 비동기 데이터베이스 연결
    conn = await aiomysql.connect(**db_config)
    
    try:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(query, params)
            
            if fetch_type == FetchType.ALL:
                result = await cursor.fetchall()
            elif fetch_type == FetchType.ONE:
                result = await cursor.fetchone()
            else:
                raise ValueError("fetch_type must be 'all' or 'one'")
            
            return result

    except aiomysql.Error as e:
        print(f"aiomysql error: {e}")
        raise e  # 에러 발생 시 호출한 곳에 에러 전달
    finally:
        # 비동기적으로 연결 종료
        await conn.ensure_closed()


async def commit_query(query, params=None, execute="one"):
    """
    Execute an INSERT, UPDATE, DELETE query and commit the changes asynchronously.
    
    :param query: SQL query to be executed (INSERT, UPDATE, DELETE).
    :param params: Parameters to be passed to the SQL query.
    :param execute: 'one' for single query execution, 'many' for multiple query execution.
    :return: The last inserted ID (if applicable).
    """

    # 비동기 데이터베이스 연결
    conn = await aiomysql.connect(**db_config)
    
    try:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            if execute == "one":
                await cursor.execute(query, params)
            else:
                await cursor.executemany(query, params)
            
            # 마지막 삽입된 ID 가져오기 (필요한 경우에만)
            last_insert_id = cursor.lastrowid
            
            # 변경 사항 커밋
            await conn.commit()
            
            return last_insert_id

    except aiomysql.Error as e:
        print(f"aiomysql error: {e}")
        raise e  # 에러 발생 시 호출한 곳에 에러 전달
    finally:
        # 비동기적으로 연결 종료
        await conn.ensure_closed()


async def execute_query(query, params=None, fetch_type='all', execute="one"):
    """
    Execute a query and fetch results asynchronously.
    
    :param query: SQL query to be executed.
    :param params: Parameters to be passed to the SQL query.
    :param fetch_type: Type of fetch ('all' for fetchall, 'one' for fetchone, 'id' for insert id).
    :param execute: 'one' for executing a single query, 'many' for executing multiple queries.
    :return: Query result or inserted id.
    """
    # 데이터베이스 연결 정보 설정
    db_config = {
        'host': settings.JF_DB_HOST,
        'port': int(settings.JF_DB_PORT),
        'user': settings.JF_DB_USER,
        'password': settings.JF_DB_PW,
        'db': 'msa_jfb',
    }

    # 비동기 데이터베이스 연결
    conn = await aiomysql.connect(**db_config)
    
    try:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            try:
                # 쿼리 실행
                if execute == "one":
                    await cursor.execute(query, params)
                else:
                    await cursor.executemany(query, params)
                
                # 결과 가져오기
                if fetch_type == 'all':
                    result = await cursor.fetchall()
                elif fetch_type == 'one':
                    result = await cursor.fetchone()
                elif fetch_type == 'id':
                    # 마지막 삽입된 ID 가져오기
                    result = cursor.lastrowid
                else:
                    raise ValueError("fetch_type must be 'all', 'one', or 'id'")
                
                # 데이터 수정 쿼리인 경우 명시적으로 커밋
                if execute == "one" or execute == "many":
                    await conn.commit()
                
                return result

            except aiomysql.Error as e:
                print(f"aiomysql error: {e}")
                raise e  # 에러 발생 시 호출한 곳에 에러 전달
            except Exception as e:
                print(f"An error occurred: {e}")
                raise e  # 기타 예외 발생 시 에러 전달

    finally:
        # 비동기적으로 연결 종료
        await conn.ensure_closed()
        
        
"""
# 비동기 실행을 위한 함수
async def main():
    query = "SELECT * FROM your_table WHERE id = %s"
    params = (1,)
    
    # fetchall 사용 예시
    result_all = await execute_query(query, params, fetch_type='all')
    print("Fetch all result:", result_all)
    
    # fetchone 사용 예시
    result_one = await execute_query(query, params, fetch_type='one')
    print("Fetch one result:", result_one)

"""