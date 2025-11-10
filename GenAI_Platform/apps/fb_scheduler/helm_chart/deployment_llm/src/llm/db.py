import os, traceback, aiomysql, settings
datetime_format = settings.TIME_DATE_FORMAT_SQL 

# DB settings ========================================================================
db_host = settings.JF_LLM_DB_HOST
db_port = settings.JF_LLM_DB_PORT
db_user = settings.JF_LLM_DB_USER
db_pw = settings.JF_LLM_DB_PW
db_name = settings.JF_LLM_DB_NAME

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

# DB query ========================================================================



async def insert_playground_test(playground_id: int, type: str):
    try:
        sql = """INSERT into playground_test (playground_id, type) VALUES (%s,%s)"""
        last_commit_id = await commit_query(query=sql, params=(playground_id, type))
        return True, last_commit_id
    except:
        traceback.print_exc()
        return False, None


async def update_playground_test(db_id, **kwargs):
    try:
        columns = []
        values = []
        for column, value in kwargs.items():
            columns.append(f"{column}=%s")
            values.append(value)
        columns_str = ", ".join(columns)
        values.append(db_id)

        sql = f"""UPDATE playground_test pt SET {columns_str} WHERE pt.id = %s"""
        await commit_query(query=sql, params=values)
        return True  
    except:
        traceback.print_exc()
        return False


async def get_rag_doc_list(rag_id: int):
    res = []
    try:
        sql = """                
            SELECT r.id as rag_id, r.name, r.description, rd.*,
            rd.id doc_id, rd.name doc_name, rd.size doc_size
            FROM jonathan_llm.rag_docs rd
            LEFT JOIN jonathan_llm.rag r ON rd.rag_id = r.id
            """
        if rag_id is not None:
            sql += "WHERE r.id='{}' ".format(rag_id)
        res = await select_query(sql, params=())
    except Exception as e:
        traceback.print_exc()
    return res


async def update_rag_result(rag_id, **kwargs):
    try:
        columns = []
        values = []
        for column, value in kwargs.items():
            columns.append(f"{column}=%s")
            values.append(value)
        columns_str = ", ".join(columns)
        values.append(rag_id)

        sql = f"""UPDATE rag SET {columns_str} WHERE id = %s"""
        await commit_query(query=sql, params=values)
        return True  
    except:
        traceback.print_exc()
        return False

async def get_dataset(dataset_id):
    res = None
    try:
        sql = """
        SELECT * FROM msa_jfb.datasets WHERE id=%s
        """
        res = await select_query(sql, params=(dataset_id,), fetch_type="one")
    except:
        traceback.print_exc()
    return res



# DB BASE ========================================================================
async def select_query(query, params=None, fetch_type='all'):
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
    위 두함수 함쳐둔 함수
    Execute a query and fetch results asynchronously.
    
    :param query: SQL query to be executed.
    :param params: Parameters to be passed to the SQL query.
    :param fetch_type: Type of fetch ('all' for fetchall, 'one' for fetchone, 'id' for insert id).
    :param execute: 'one' for executing a single query, 'many' for executing multiple queries.
    :return: Query result or inserted id.
    """
    # 데이터베이스 연결 정보 설정

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