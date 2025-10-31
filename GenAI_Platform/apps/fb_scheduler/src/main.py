from scheduler.scheduler import pod_start_new, workspace_item_pod_check
import threading



def main():

    workspace_item_thread = threading.Thread(target=workspace_item_pod_check)
    pod_start_thread = threading.Thread(target=pod_start_new)
    # workspace_item_thread.start()
    pod_start_thread.start()


if __name__=="__main__":
    main()
