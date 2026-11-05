from utils.common import run_func_with_print_line
from utils import settings
from utils.msa_db.db_base import get_db
from utils.msa_db import db_user
import traceback

def set_default_image(db_name, image_name_tag):
    with get_db() as conn:
        try:
            #TODO DB에 넣거나 settings를 kuber에다가 바로 사용하거나 결정
            sql = 'SELECT count(id) as count FROM image WHERE name="{}"'.format(db_name)
            cursor = conn.cursor()
            cursor.execute(sql)
            default_chk = cursor.fetchone()

            user_id = db_user.get_user(user_name='admin').get("id")

            if default_chk['count'] == 0:
                if image_name_tag is None:
                    print("Default Image [{}] Insert Skip".format(db_name))
                else :
                    # user_id = 1
                    name = db_name
                    real_name = image_name_tag
                    status = 2
                    access = 1
                    sql = """
                        INSERT INTO image (user_id, name, real_name, status, access) VALUES ('{}', '{}', '{}', '{}', '{}')
                        """.format(user_id, name, real_name, status, access)
                    conn.cursor().execute(sql)
                    conn.commit()

            elif default_chk['count'] > 0:
                # Update
                if image_name_tag is None:
                    print("Default Image [{}] set access 0".format(db_name))
                    sql = """
                        UPDATE image set real_name = '{}', access = 0 where name = '{}'
                        """.format(real_name, name)
                else :
                    # user_id = 1
                    name = db_name
                    real_name = image_name_tag
                    status = 2
                    access = 1
                    sql = """
                        UPDATE image set real_name = '{}' where name = '{}'
                        """.format(real_name, name)
                conn.cursor().execute(sql)
                conn.commit()
        except:
            traceback.print_exc()

# def set_image_namespace():
#     command = f"helm install image-namespace \
#                 -n {settings.JF_SYSTEM_NAMESPACE}-image --create-namespace\
#                 --set system.namespace='{settings.JF_SYSTEM_NAMESPACE}' \
#                 --set system.registry='{settings.DOCKER_REGISTRY_URL}' \
#                 --set system.imagePullSecrets.enabled='{settings.JONATHAN_IMAGE_PULL_SECRETS_EABLED}' \
#                 ./image-namespace"
#     try:
#         os.chdir("/app/helm_chart/")
#         subprocess.run(
#             command, shell=True, check=True, text=True,
#             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
#         )
#         return True, ""
#     except subprocess.CalledProcessError as e:
#         err_msg = e.stderr.strip()
#         print(e.stdout, file=sys.stderr)
#         print(err_msg, file=sys.stderr)
#         print(command, file=sys.stderr)
#         return False, err_msg
    
def init_default_image():
    # set_default_image(db_name=settings.JF_DEFAULT_IMAGE_NAME, image_name_tag=settings.JF_DEFAULT_IMAGE)
    # set_default_image(db_name=settings.JF_GPU_TF2_IMAGE_NAME, image_name_tag=settings.JF_GPU_TF2_IMAGE)
    # set_default_image(db_name=settings.JF_GPU_TORCH_IMAGE_NAME, image_name_tag=settings.JF_GPU_TORCH_IMAGE)
    # set_default_image(db_name=settings.JF_CPU_DEFAULT_IMAGE_NAME, image_name_tag=settings.JF_CPU_DEFAULT_IMAGE)
    set_default_image(db_name=settings.JF_DEFAULT_UBUNTU_20, image_name_tag=settings.JF_DEFAULT_UBUNTU_20_IMAGE)
    set_default_image(db_name=settings.JF_DEFAULT_UBUNTU_22, image_name_tag=settings.JF_DEFAULT_UBUNTU_22_IMAGE)
    if settings.JONATHAN_INTELLIGENCE_USED:
        set_default_image(db_name="burn", image_name_tag=settings.JF_BUILT_IN_MODEL_BURN)
    pass

# def main():
#     run_func_with_print_line(func=init_default_image, line_message="INIT DEFAULT IMAGE")    

# if __name__ == "__main__":
#     main()