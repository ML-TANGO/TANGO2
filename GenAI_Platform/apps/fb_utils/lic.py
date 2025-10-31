import json;
import subprocess;
import xml.etree.ElementTree as ET;
import base64;
import traceback;

def fingerprint():
	gpu_list = [];
	try:
		with subprocess.Popen(['nvidia-smi', '-q', '-x'], stdout=subprocess.PIPE) as p:
			out, err = p.communicate();
			out = out.decode('utf-8');
			root = ET.fromstring(out);
		for e in root:
			if e.tag == 'gpu':
				uuid = e.find('uuid').text.replace('\n', '').replace('\r', '').strip();
				if len(uuid) > 0:
					gpu_list.append({
						"uuid":  uuid,
						"brand": e.find('product_brand').text.replace('\n', '').replace('\r', '').strip(),
						"name":  e.find('product_name').text.replace('\n', '').replace('\r', '').strip(),
						"mem":   e.find('fb_memory_usage').find('total').text.replace('\n', '').replace('\r', '').strip()
					});
	except:
		traceback.print_exc();
		gpu_list = [];
	if gpu_list is not None:
		gpu_list.sort(key=lambda a: a["uuid"], reverse=False);
	if len(gpu_list) > 0:
		return json.dumps(gpu_list, ensure_ascii = False, sort_keys=True, indent = 2);
	return None;

BITS = 2048;
BLK_LEN = BITS//8;
NNN = 0xd9ed0a48d3669d5de0d505be6c72d9bb79633c9b37ee296d81c634f41e4a12ad90228eb9b91d5f909f3faa89b4931088b1d2d9edd6770bd0bb4e6b3212e9aa480b1c6f06ef8afb416ad57fb2045f1261b08b27ead24a2b861ea43e1512658ce0cf810104bd421eed9b28d6ebf1ceaa1ad0eb15dee4136aa1cc5763d7594de3ff9d7f6f646cc3333fd6b1d488b1cd7d02998fd267a6ab3cda262408e58402dfd9fa8de3d1d94177d4fa4376db38f8304dbf08f789b3cc13f467f6fc8f8d8486552de4a9c5e2fe077c4a2c6b366037792c77e610a187258ed5087c071fb457a826eada9d458c698b224ebeebc6280a28b2b569a1eaf168f4119b216d800b6f6cbb;
EEE = 0x10001;

def acryl_enc(data):
	try:
		l = len(data);
		if l >= 2**32:
			return None;
		ret = b'';#(len(data)).to_bytes(4, "little", signed = False);
		i = 0;
		while i < l:
			if i <= 0:
				blk = l.to_bytes(4, "little", signed = False);
				blk += data[i:i+(BLK_LEN-6)];
				i += (BLK_LEN-6);
			else:
				blk = data[i:i+(BLK_LEN-2)];
				i += (BLK_LEN-2);
			r = len(blk) % (BLK_LEN-2);
			if r > 0:
				blk += (b'\x00')*((BLK_LEN-2)-r);
			w = int.from_bytes(blk, "little", signed = False);
			ew = pow(w, EEE, NNN);
			x = ew.to_bytes(BLK_LEN, "little", signed = False);
			ret += x;
		return ret;
	except:
		traceback.print_exc();
	return None;

def acryl_dec(data):
	try:
		l = len(data);
		if (l % BLK_LEN) != 0:
			return None;
		ret = b'';
		i = 0;
		dlen = 0;
		while i < l:
			blk = data[i:i+BLK_LEN];
			w = int.from_bytes(blk, "little", signed = False);
			ew = pow(w, EEE, NNN);
			x = ew.to_bytes(BLK_LEN-2, "little", signed = False);
			if i <= 0:
				dlen = int.from_bytes(x[:4], "little", signed = False);
				x = x[4:];
			if dlen >= BLK_LEN-2:
				ret += x;
			else:
				ret += x[:dlen];
			i += BLK_LEN;
			dlen -= len(x);
		return ret;
	except:
		traceback.print_exc();
	return None;

def export_fp():
	try:
		return base64.encodebytes(acryl_enc((fingerprint()).encode('utf-8'))).decode('ascii').replace('\n', '').replace('\r', '');
	except:
		traceback.print_exc();
	return None;

def decode_lic(lic_text):
	try:
		return acryl_dec(base64.decodebytes(lic_text.encode('ascii'))).decode('utf-8');
	except:
		traceback.print_exc();

def is_valid_lic(lic_text):
	try:
		obj1 = json.loads(decode_lic(lic_text));
		obj2 = json.loads(fingerprint());
		for g2 in obj2:
			is_in = False;
			for g1 in obj1["fp"]:
				if g2["uuid"] == g1["uuid"]:
					is_in = True;
					break;
			if not is_in:
				return False;
	except:
		traceback.print_exc();
		return False;
	return True;

