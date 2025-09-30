import subprocess

def run_dmidecode():
    # dmidecode --type memory 명령을 실행하고 결과를 캡처
    output = subprocess.run(['dmidecode', '--type', 'memory'], capture_output=True, text=True).stdout.split('Memory Device')
    memory_list=[]
    for info in output:
        memory_info={}
        for line in info.split('\n'):
            if ":" in line:
                key, value = line.split(":")
                key = key.strip().replace(' ','_')
                value = value.strip()
                memory_info[key] = value
        memory_list.append(memory_info)

    return memory_list

def get_memory_info(memory_list):
    result ={}
    for memory in memory_list:
        if 'Part_Number' not in memory:
            continue
        if result.get(memory['Part_Number']):
            result[memory['Part_Number']]['num'] +=1
        else:
            result[memory['Part_Number']]={
                    'type' : memory['Type'],
                    'size' : memory['Size'],
                    'speed': memory['Speed'],
                    'manufacturer' : memory['Manufacturer'],
                    'num' : 1
                    }

    return result




if __name__ == "__main__":
    memory_info = run_dmidecode()
    print(get_memory_info(memory_info))
