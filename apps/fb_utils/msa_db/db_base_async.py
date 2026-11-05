from utils import settings
import aiomysql
import traceback
import asyncio
from contextlib import asynccontextmanager

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

db_dumy_config = {
    'host': settings.JF_DB_HOST,
    'port': int(settings.JF_DB_PORT),
    'user': settings.JF_DB_USER,
    'password': settings.JF_DB_PW,
    'db': "msa_jfb_dumy" #settings.JF_DB_NAME,
}

class FetchType:
    ONE = "one"
    ALL = "all"

class ExecuteType:
    ONE = "one"
    MANY = "many"

async def select_query(query, params=None, fetch_type=FetchType.ALL, db_config=db_config):
    """
    Execute a SELECT query and fetch results asynchronously.
    
    :param query: SELECT query to be executed.
    :param params: Parameters to be passed to the SQL query.
    :param fetch_type: Type of fetch ('all' for fetchall, 'one' for fetchone).
    :return: Query result.
    """
    conn = None
    try:
        # 연결 타임아웃 설정을 포함한 데이터베이스 설정
        db_config_with_timeout = db_config.copy()
        #'read_timeout': 30# 읽기 타임아웃 30초, 'write_timeout': 30, # 쓰기 타임아웃 30초
        db_config_with_timeout.update({
            'connect_timeout': 10,  # 연결 타임아웃 10초
            'autocommit': True      # 자동 커밋 활성화
        })
        
        # 비동기 데이터베이스 연결
        conn = await aiomysql.connect(**db_config_with_timeout)
        
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
            traceback.print_exc()
            raise e
        except asyncio.CancelledError:
            print("Database query cancelled due to SSE connection cancellation")
            raise
        finally:
            # 비동기적으로 연결 종료
            if conn:
                await conn.ensure_closed()
            
    except asyncio.CancelledError:
        print("Database connection cancelled")
        if conn:
            try:
                await conn.ensure_closed()
            except:
                pass
        raise
    except Exception as e:
        print(f"Unexpected error in select_query: {e}")
        traceback.print_exc()
        if conn:
            try:
                await conn.ensure_closed()
            except:
                pass
        raise e


async def commit_query(query, params=None, execute=ExecuteType.ONE, db_config=db_config):
    """
    Execute an INSERT, UPDATE, DELETE query and commit the changes asynchronously.
    
    :param query: SQL query to be executed (INSERT, UPDATE, DELETE).
    :param params: Parameters to be passed to the SQL query.
    :param execute: 'one' for single query execution, 'many' for multiple query execution.
    :return: The last inserted ID (if applicable).
    """
    conn = None
    try:
        # 연결 타임아웃 설정을 포함한 데이터베이스 설정
        db_config_with_timeout = db_config.copy()
        db_config_with_timeout.update({
            'connect_timeout': 10,  # 연결 타임아웃 10초
            'autocommit': False     # 수동 커밋 모드
        })
        
        # 비동기 데이터베이스 연결
        conn = await aiomysql.connect(**db_config_with_timeout)
        
        try:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                if execute == ExecuteType.ONE:
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
            traceback.print_exc()
            raise e
        except asyncio.CancelledError:
            print("Database commit query cancelled")
            raise
        finally:
            # 비동기적으로 연결 종료
            if conn:
                await conn.ensure_closed()
            
    except asyncio.CancelledError:
        print("Database connection cancelled for commit")
        if conn:
            try:
                await conn.ensure_closed()
            except:
                pass
        raise
    except Exception as e:
        print(f"Unexpected error in commit_query: {e}")
        traceback.print_exc()
        if conn:
            try:
                await conn.ensure_closed()
            except:
                pass
        raise e


async def execute_query(query, params=None, fetch_type='all', execute="one", db_config=db_config):
    """
    Execute a query and fetch results asynchronously.
    
    :param query: SQL query to be executed.
    :param params: Parameters to be passed to the SQL query.
    :param fetch_type: Type of fetch ('all' for fetchall, 'one' for fetchone, 'id' for insert id).
    :param execute: 'one' for executing a single query, 'many' for executing multiple queries.
    :return: Query result or inserted id.
    """
    conn = None
    try:
        # 연결 타임아웃 설정을 포함한 데이터베이스 설정
        db_config_with_timeout = db_config.copy()
        #'read_timeout': 30,     # 읽기 타임아웃 30초, 'write_timeout': 30,    # 쓰기 타임아웃 30초        
        db_config_with_timeout.update({
            'connect_timeout': 10,  # 연결 타임아웃 10초
            'autocommit': False     # 수동 커밋 모드
        })
        
        # 비동기 데이터베이스 연결
        conn = await aiomysql.connect(**db_config_with_timeout)
        
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
                    raise e
                except asyncio.CancelledError:
                    print("Database execute query cancelled")
                    raise
                except Exception as e:
                    print(f"An error occurred: {e}")
                    raise e

        except asyncio.CancelledError:
            print("Database execute query cancelled")
            raise
        finally:
            # 비동기적으로 연결 종료
            if conn:
                await conn.ensure_closed()
            
    except asyncio.CancelledError:
        print("Database connection cancelled for execute")
        if conn:
            try:
                await conn.ensure_closed()
            except:
                pass
        raise
    except Exception as e:
        print(f"Unexpected error in execute_query: {e}")
        traceback.print_exc()
        if conn:
            try:
                await conn.ensure_closed()
            except:
                pass
        raise e
        
        
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

async def execute_transaction(queries_and_params, db_config=db_config):
    """
    Execute multiple queries in a single transaction.
    If any query fails, all changes are rolled back.
    
    :param queries_and_params: List of tuples (query, params) to execute
    :param db_config: Database configuration
    :return: List of results from each query
    """
    conn = await aiomysql.connect(**db_config)
    
    try:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            results = []
            
            for query, params in queries_and_params:
                await cursor.execute(query, params)
                results.append(cursor.lastrowid)
            
            # 모든 쿼리가 성공하면 커밋
            await conn.commit()
            return results
            
    except Exception as e:
        # 오류 발생 시 롤백
        await conn.rollback()
        print(f"Transaction failed, rolled back: {e}")
        raise e
    finally:
        await conn.ensure_closed()

async def execute_transaction_with_callback(queries_and_params, callback=None, db_config=db_config):
    """
    Execute multiple queries in a transaction with optional callback for additional operations.
    
    :param queries_and_params: List of tuples (query, params) to execute
    :param callback: Optional callback function that receives cursor and results
    :param db_config: Database configuration
    :return: Results from queries and callback
    """
    conn = await aiomysql.connect(**db_config)
    
    try:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            results = []
            
            # 메인 쿼리들 실행
            for query, params in queries_and_params:
                await cursor.execute(query, params)
                results.append(cursor.lastrowid)
            
            # 콜백 함수가 있으면 실행
            if callback:
                callback_result = await callback(cursor, results)
                results.append(callback_result)
            
            # 모든 작업이 성공하면 커밋
            await conn.commit()
            return results
            
    except Exception as e:
        # 오류 발생 시 롤백
        await conn.rollback()
        print(f"Transaction failed, rolled back: {e}")
        raise e
    finally:
        await conn.ensure_closed()