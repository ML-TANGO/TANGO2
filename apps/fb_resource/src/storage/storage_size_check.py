import psutil
import os
import sys
import traceback
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
from utils.msa_db.db_storage import update_storage,get_storage


STORAGEPATH="/storage"
def get_disk_usage():
    try:
        usage=psutil.disk_usage(STORAGEPATH)
        total_size=usage.total
        name=os.getenv("NAME")
        storage_info=get_storage(name=name)
        # for storage in storage_info:

    #     print(type(storage))
    #     print(storage['id'])            
        result= update_storage(
            id=int(storage_info['id']),
            size=total_size,
        )
        print(result)
        return 0
    except:
        traceback.print_exc()
        return 1

get_disk_usage()
