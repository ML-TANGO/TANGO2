import time

# import records
# # import utils.db as db
# import benchmark_storage as bs

class LoopFunctionController:
    def __init__(self, loop_func_list):
        self._loop_func_list = loop_func_list # [ LoopFunction(), ... ]

    def do(self):
        for func in self._loop_func_list:
            func.do()

    # TODO - 자체 thread or subprocess 로 동작할 수 있게

class LoopFunction:
    def __init__(self, func, interval, last_do=None, args=None, kwargs=None):
        """
            Args:
                last_do (int) - timestamp - 0 = 실행과 동시에 시작, None = 생성 시간 기준으로 다음 interval에 실행
        """

        self._func = func
        self._interval = interval
        self._last_do = last_do if last_do is not None else time.time() # 0 or None
        self._args = args if args is not None else ()
        self._kwargs = kwargs if kwargs is not None else {}

    def do(self):
        if self._is_time_to_do():
            self._func(*self._args, **self._kwargs)
            self._update_last_do()
            print("DO", self._func)

    def _is_time_to_do(self):
        return (time.time() - self._last_do) > self._interval

    def _update_last_do(self):
        self._last_do = time.time()

# record_unified 에서 end_datetime 이 없는 아이템 (비정상 적인 종료) end_datetime 지정해주는 함수
# MSA 전환 주석처리
# func_update_record_end_datime = LoopFunction(func=records.update_record_unified_end_datetime_is_null, interval=60 * 60)

# DB Backup
func_backup_db = LoopFunction(func=db.backup_db, interval=60 * 60 * 24)

# Benchmark storage thread lock 문제 대응
# MSA 전환 주석처리
# func_restart_benchmark_storage_thread = LoopFunction(func=bs.restart_thread_for_unprocessed_item, interval=60)

# loop_function_controller = LoopFunctionController(loop_func_list=[func_update_record_end_datime, func_backup_db, func_restart_benchmark_storage_thread])
loop_function_controller = LoopFunctionController(loop_func_list=[func_backup_db])
