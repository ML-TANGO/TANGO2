from typing import List
import ipaddress as ipa
from ipaddress import IPv4Address
# from restplus import api
import traceback
import sys

from utils.resource import CustomResource, token_checker
from utils.resource import response
from utils.exceptions import *
from utils.TYPE import *

# import utils.db as db


def get_ethernet_cni_config(ipam_range, ipam_range_start, ipam_range_end):
    """
        Description : Eth 설정용 interface setting
                      Eth의 경우 ipam type이 whereabouts 로 연결되어 있는 노드에서 IP가 중복되지 않도록 자동 관리 된다.


                      사용자는 X 영역에 대해 정의 가능하다.
                        subnet: X.X.X.X/16 24
                        rangeStart: X.X.X.X
                        rangeStart: X.X.X.X


        Args:
            range (str): pod 내에서의 host 기본 주소 및 subnetmask ex) 192.168.0.0/16 or 192.168.100.0/24
            range_start (str) : 생성 될 Pod이 가지게 될 IP 시작 대역 - 서브넷마스크에서 결정되는 범위보다 작게 정의할 수 있다. ex) 192.168.1.5 (16)
            range_end (str) : 생성 될 Pod이 가지게 될 IP 시작 대역 - 서브넷마스크에서 결정되는 범위보다 작게 정의할 수 있다. ex) 192.168.100.100 (16)


        Return :
            (dict) : DB에 그대로 저장하며 이 정보로 nad 정보 생성
    """
    config = {
      "cniVersion": "0.3.0",
      "type": "macvlan",
      "master": None, # Network Group에서 하나만 정의하며 nad로 정의될 땐 master 부분만 각자의 interface를 가져가서 사용하도록
      "mode": "bridge",
      "ipam": {
        "type": "whereabouts",
        "range": ipam_range,
        "range_start": ipam_range_start,
        "range_end": ipam_range_end,
        "gateway": ipam_range_start # ethernet의 경우 IP 할당을 별도로 관리하므로 선언하지 않아도 상관 없으나 infiniband와 형태를 맞추기 위함
      }
    }
    return config

def get_infiniband_cni_config(ipam_range, ipam_range_start, ipam_range_end):
    """
        Description : Infiniband 용 cni 정의 config
                      Infiniband의 경우 ipam type이 host-local 이기 때문에 rangeStart, End 가 각각 노드에서 별도로 관리함 -> 노드간에서 중복되는 IP 발생 가능
                      따라서 ipam_range는 X.X.0.0/16 을 기준으로 하며 0.0.X.0 부분을 등록하는 노드별로 1씩 사용하도록 (최대 255개의 노드 등록 가능)
                      Start, End는 사용할 수 있는 최대 범위를 기본 제공 ? 0.0.0.X 부분만 컨트롤 가능

                      사용자는 X 영역만 정의 가능하다.
                        subnet: X.X.0.0/16
                        rangeStart: [Subnet].[Subnet].[자동].X
                        rangeStart: [Subnet].[Subnet].[자동].X
                     ---> 2022-12-20 변경 진행 중
                      입력한 범위 내에서 JFB API가 자체적으로 할당된 IP를 계산해서 다음 IP를 직접 할당하는 구조로 진행 중
                      테스트가 문제없이 완료되면 ethernet이 가지는 자유도만큼 사용 가능
    """
    config = {
        "type": "ib-sriov",
        "cniVersion": "0.3.1",
        "name": "sriov-network",
        "link_state": "enable",
        "ipam": {
            "type": "host-local",
            "subnet": ipam_range,
            "rangeStart": ipam_range_start,
            "rangeEnd": ipam_range_end,
            "gateway": ipam_range_start # 선언하지 않아도 default로 정의되는 값이 있으나 사용중인 IP 확인 시 gateway는 제외하고 할당하도록 하기 위함
        }
    }
    return config

def create_network_cni(network_group_id, ipam_range, ipam_range_start, ipam_range_end):
    network_group_info = db.get_network_group(network_group_id=network_group_id)

    category = network_group_info["category"]


    if category == NETWORK_GROUP_CATEGORY_INFINIBAND:
        cni_config = get_infiniband_cni_config(ipam_range=ipam_range, ipam_range_start=ipam_range_start, ipam_range_end=ipam_range_end)
    elif category == NETWORK_GROUP_CATEGORY_ETHERNET:
        cni_config = get_ethernet_cni_config(ipam_range=ipam_range, ipam_range_start=ipam_range_start, ipam_range_end=ipam_range_end)
    else:
        raise NetworkGroupCategoryInvalidError

    db.insert_network_group_cni(network_group_id=network_group_id, cni_config=cni_config)

def update_network_cni(network_group_id, ipam_range, ipam_range_start, ipam_range_end):
    network_group_info = db.get_network_group(network_group_id=network_group_id)

    category = network_group_info["category"]


    if category == NETWORK_GROUP_CATEGORY_INFINIBAND:
        cni_config = get_infiniband_cni_config(ipam_range=ipam_range, ipam_range_start=ipam_range_start, ipam_range_end=ipam_range_end)
    elif category == NETWORK_GROUP_CATEGORY_ETHERNET:
        cni_config = get_ethernet_cni_config(ipam_range=ipam_range, ipam_range_start=ipam_range_start, ipam_range_end=ipam_range_end)
    else:
        raise NetworkGroupCategoryInvalidError

    db.update_network_group_cni(network_group_id=network_group_id, cni_config=cni_config)

def get_network_cni_config_ip_info(cni_config):
    """
        Description : 등록된 Network CNI 에서 ip 설정 정보를 가져오는 함수

        Args:
            cni_config (dict) : Network CNI 관련 config - 지원하는 type - "ib-sriov" | "macvlan"

        Return:
            ip_range (str), ip_range_start (str), ip_range_end (str), gateway (str)
    """
    def parsing_macvlan_0_3_0(cni_config):
        """
            Example : {
                "cniVersion": "0.3.0",
                "type": "macvlan",
                "master": "bond1",
                "mode": "bridge",
                "ipam": {
                    "type": "whereabouts",
                    "range": "100.100.0.0/16",
                    "range_start": "100.100.0.1",
                    "range_end": "100.100.255.254",
                    "gateway": "100.100.0.1
                }
            }
        """
        ip_range = cni_config["ipam"]["range"]
        ip_range_start = cni_config["ipam"]["range_start"]
        ip_range_end = cni_config["ipam"]["range_end"]
        gateway = cni_config["ipam"].get("gateway") # Optional

        return ip_range, ip_range_start, ip_range_end, gateway

    def parsing_ib_sriov_0_3_1(cni_config):
        """
            Example : {
                "type": "ib-sriov",
                "cniVersion": "0.3.1",
                "name": "sriov-network",
                "link_state": "enable",
                "ipam": {
                    "type": "host-local",
                    "subnet": "200.200.0.0/16",
                    "rangeStart": "200.200.0.1",
                    "rangeEnd": "200.200.255.254",
                    "gateway": "200.200.0.1"
                }
            }
        """
        ip_range = cni_config["ipam"]["subnet"]
        ip_range_start = cni_config["ipam"]["rangeStart"]
        ip_range_end = cni_config["ipam"]["rangeEnd"]
        gateway = cni_config["ipam"].get("gateway") # Optional

        return ip_range, ip_range_start, ip_range_end, gateway


    parsing_func = {
        "type":{
            "macvlan" : {
                "cniVersion" : {
                    "0.3.0" : parsing_macvlan_0_3_0
                }
            },
            "ib-sriov": {
                "cniVersion" : {
                    "0.3.1" : parsing_ib_sriov_0_3_1
                }
            }
        }
    }

    return parsing_func["type"][cni_config["type"]]["cniVersion"][cni_config["cniVersion"]](cni_config=cni_config)

def create_network_group_container_interface(network_group_id, port_index, interface):
    """
        Description : Node에 있는 Interface가 Container에서 사용될 때 Interface명 지정
                      2개 이상의 포트를 등록 하는 경우 n개의 포트명을 지정해서 n번째 포트는 각각의 이름을 가질 수 있도록 함

        Args:
            network_group_id (int)
            port_index (int) : 몇번째 포트인지 (1부터 시작함 - 숫자는 관리자 마음)
    """
    db.insert_network_group_container_interface(network_group_id=network_group_id, port_index=port_index, interface=interface)

# def update_network_group_container_interface(network_group_container_interface_id, port_index, interface):
#     # TODO port index를 변경할까....?
#     pass

def update_network_group_container_interface_new(network_group_container_interface_id, interface, port_index=None):
    # TODO port index를 변경할까....?
    db.update_network_group_container_interface(network_group_container_interface_id=network_group_container_interface_id, interface=interface, port_index=port_index)
    pass

def delete_network_group_container_interface(network_group_container_interface_id):
    # TODO container interface 삭제 시 port index 초기화는 필요 없어 보임.. 관리자가 port index 지정하고 등록
    db.delete_network_group_container_interface(network_group_container_interface_id=network_group_container_interface_id)
    pass

# TODO 특정 NETWORK GROUP에 CNI 생성을 위한 ENDPOINT가 있어야함


def is_valid_ip_address(ip_address: str) -> bool:
    """
	[Description] ip address 유효성 검사

	[Args]
		ip address (str):  (ex. "192.168.1.1")
	[Returns]
		(bool)
	[Examples]
        is_valid_ip_address("192.168.1.1")  # True
    """
    ip_address = list(map(int, ip_address.split('.')))

    if len(ip_address) != 4:
        return False

    for i in ip_address:
        if not 0 <= i <= 255:
            return False
    return True

def is_valid_prefix(prefix: int) -> bool:
    """
	[Description] prefix 유효성 검사

	[Args]
		prefix (int):  (ex. 16)
	[Returns]
		(bool)
	[Examples]
        is_valid_prefix(16)  # True
    """
    return 1 <= prefix <= 32

def get_ip_address_range(ip_address: str, prefix: int) -> tuple:
    """
        [Description] IP 주소와 prefix (서브넷 마스크의 bit 수)를 받아 가능한 Host IP 범위를 리턴

        [Args]
            ip address (str):  (ex. "192.168.1.1")
            prefix (int):  (ex. 16)
        [Returns]
            range of Host IP (tuple):  (ex. ('192.168.0.1', '192.168.255.254'))
        [Examples]
            > get_address_range(ip_address="192.168.1.1", prefix=16)
            > ('192.168.0.1', '192.168.255.254')
        [References]
            https://gist.github.com/vndmtrx/dc412e4d8481053ddef85c678f3323a6
            https://damaha-labo.site/converter/ko/IT/CalcSubnetMask
    """

    # check address format (0 <= ip_address <= 255)
    if not is_valid_ip_address(ip_address):
        raise Exception("Invalid IP address format")

    # check prefix (1 <= prefix <= 32)
    if not is_valid_prefix(prefix):
        raise Exception("prefix is not valid")

    ip_address = [int(i) for i in ip_address.split('.')]

    # get subnet mask, network, broadcast
    mask = [(((1 << 32) - 1) << (32 - prefix) >> i) & 255 for i in reversed(range(0, 32, 8))]  # 16 -> [255, 255, 0, 0]
    network = [ip_address[i] & mask[i] for i in range(4)]  # AND 한 것 [192, 168, 0, 0]
    broadcast = [(ip_address[i] & mask[i]) | (255 ^ mask[i]) for i in range(4)]  # [192, 168, 255, 255]

    # get host address
    start_address, end_address = network, broadcast
    start_address[-1] += 1
    end_address[-1] -= 1

    return '.'.join(map(str, start_address)), '.'.join(map(str, end_address))


def is_within_ip_address(ip_address: str, prefix: int, start_address: str, end_address: str) -> bool:
    """
        [Description] ip_address를 받아 최대 range를 구하고, 범위 range를 받아 최대 range 내에 속하는지 판단하는 함수

        [Args]
            ip address (str):  (ex. "192.168.1.1")
            prefix (int):  (ex. 16)
            start address (str):  (ex. "192.168.0.1")
            end address (str):  (ex. "192.168.255.254")
        [Returns]
            boolean (bool):  (ex. True | False)
        [Examples]
            is_valid_address(ip_address="192.168.1.1",
                            prefix=16,
                            start_address="192.168.0.1",
                            end_address="192.168.255.254")  # True
    """
    # IP 주소의 전체 range 반환
    ip_start_address, ip_end_address = map(ipa.ip_address, get_ip_address_range(ip_address, prefix))
    start_address, end_address = map(ipa.ip_address, (start_address, end_address))

    if start_address >= end_address:
        raise ValueError("정확한 IP 주소를 입력해 주세요")

    # 범위 비교
    if (start_address <= ip_start_address <= end_address) \
        or (start_address <= ip_end_address <= end_address):
            return True
    if (ip_start_address <= start_address <= ip_end_address) \
        or (ip_start_address <= end_address <= ip_end_address):
            return True
    return False

def get_available_address(start_address: str, end_address: str, used_ips: List[str] = None) -> str:
    """
	[Description] ip address 범위를 받아 사용한 ip 목록(used_ips)에 포함되지 않은 ip 반환

	[Args]
		start_address (str):  (ex. "192.168.0.1")
		end_address (str):  (ex. "192.168.0.3")
		used_ips (List[str]):  (ex.  ["192.168.0.1", "192.168.0.2", "192.168.0.3"])
	[Returns]
		available ip address (str):  (ex. "192.168.5.102")
	[Examples]
        get_available_address("192.168.5.100",
                             "192.168.7.5",
                             ["192.168.5.100", "192.168.5.101"]  # "192.168.5.102"
    """
    if used_ips is None:
        used_ips = []
    start_address: IPv4Address = ipa.ip_address(start_address)
    end_address: IPv4Address = ipa.ip_address(end_address)
    available_address: IPv4Address = start_address

    # 범위 체크
    if start_address > end_address:
        raise ValueError()

    while True:
        # 사용된 ips 에 포함되어 있지 않고 end_address 의 범위 내에 있는 경우 리턴
        if available_address > end_address:
            raise Exception("사용 가능한 ip가 없습니다.")
        if str(available_address) not in used_ips:
            return str(available_address)
        available_address += 1