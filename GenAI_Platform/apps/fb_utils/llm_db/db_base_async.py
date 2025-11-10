from utils import settings

import aiomysql
import os
import asyncio
try:
    db_host = settings.JF_DB_HOST
except :
    db_host = '192.168.1.20'
try:
    db_port = int(settings.JF_DB_PORT)
except :
    db_port = 30001
try:
    db_unix_socket = settings.JF_DB_UNIX_SOCKET
except :
    db_unix_socket = '/jf-src/master/conf/db/mysqld.sock'
try:
    db_user = settings.JF_DB_USER
except :
    db_user = 'root'
try:
    db_pw = settings.JF_DB_PW
except :
    db_pw = 'acryl4958@'
try:
    db_name = "jonathan_llm"
except :
    db_name = 'jonathan_llm'
try:
    db_charset = settings.JF_DB_CHARSET
except :
    db_charset = 'utf8'
try:
    db_dummy_name = "jonathan_llm_dummy"
except :
    db_dummy_name = db_name + "_dummy"

class FetchType:
    ONE = "one"
    ALL = "all"


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
        'host': db_host,
        'port': db_port,
        'user': db_user,
        'password': db_pw,
        'db': db_name,
    }

# Connection pool 초기화
_db_pool = None
_pool_lock = asyncio.Lock()

async def get_db_pool():
    """Connection pool을 생성하고 반환 (싱글톤 패턴)"""
    global _db_pool
    if _db_pool is None:
        async with _pool_lock:
            if _db_pool is None:
                _db_pool = await aiomysql.create_pool(
                    **db_config,
                    minsize=5,  # 최소 연결 수
                    maxsize=20,  # 최대 연결 수
                    pool_recycle=3600,  # 1시간 후 연결 재사용
                    autocommit=False,
                    cursorclass=aiomysql.DictCursor
                )
    return _db_pool

async def select_query(query, params=None, fetch_type='all'):
    """
    Execute a SELECT query and fetch results asynchronously using connection pool.
    
    :param query: SELECT query to be executed.
    :param params: Parameters to be passed to the SQL query.
    :param fetch_type: Type of fetch ('all' for fetchall, 'one' for fetchone).
    :return: Query result.
    """
    pool = await get_db_pool()
    
    async with pool.acquire() as conn:
        try:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(query, params)

                if fetch_type == 'all':
                    result = await cursor.fetchall()
                elif fetch_type == 'one':
                    result = await cursor.fetchone()
                else:
                    raise ValueError("fetch_type must be 'all' or 'one'")
                return result

        except aiomysql.Error as e:
            print(f"aiomysql error: {e}")
            raise e  # 에러 발생 시 호출한 곳에 에러 전달


async def commit_query(query, params=None, execute="one"):
    """
    Execute an INSERT, UPDATE, DELETE query and commit the changes asynchronously using connection pool.
    
    :param query: SQL query to be executed (INSERT, UPDATE, DELETE).
    :param params: Parameters to be passed to the SQL query.
    :param execute: 'one' for single query execution, 'many' for multiple query execution.
    :return: The last inserted ID (if applicable).
    """
    pool = await get_db_pool()
    
    async with pool.acquire() as conn:
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
            await conn.rollback()  # 에러 발생 시 롤백
            raise e  # 에러 발생 시 호출한 곳에 에러 전달


async def execute_query(query, params=None, fetch_type='all', execute="one"):
    """
    위 두함수 함쳐둔 함수
    Execute a query and fetch results asynchronously using connection pool.
    
    :param query: SQL query to be executed.
    :param params: Parameters to be passed to the SQL query.
    :param fetch_type: Type of fetch ('all' for fetchall, 'one' for fetchone, 'id' for insert id).
    :param execute: 'one' for executing a single query, 'many' for executing multiple queries.
    :return: Query result or inserted id.
    """
    pool = await get_db_pool()
    
    async with pool.acquire() as conn:
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
                    await conn.rollback()  # 에러 발생 시 롤백
                    raise e  # 에러 발생 시 호출한 곳에 에러 전달
                except Exception as e:
                    print(f"An error occurred: {e}")
                    await conn.rollback()  # 에러 발생 시 롤백
                    raise e  # 기타 예외 발생 시 에러 전달
        except Exception as e:
            print(f"Connection pool error: {e}")
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