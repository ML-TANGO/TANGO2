from collections import Counter

new_dict = Counter({
    'h7023b55eeb6467fdba4ebcb68baa96d3-0-0': 117823372,
    'h2894557698b138cba9a3cce042b230a4-513-0': 253396,
    'h53f37b828df9c9be46f0cd2f4d5e444e-514-0': 261456,
    'hd979386dc58a484325f7f4d1abc2d79f-517-0': 258958,
    'hf9b427126684729acd949f2565df6db6-519-0': 259364,
    'he605db4c5d1257ba09f57ce335a68b64-576-0': 393516,
    'hda1a05e6556cddc06ef9740d959f6ebe-652-0': 62810,
    'h6a3678cfb6387e2d1e4f51705240920f-666-0-deployment-llm': 62993,
    'h32b5425f293e3f96830a60c1d886d9fb-687-0-deployment-llm': 56871
})

original_dict = Counter({})

def calculate_difference(original, new):
    return Counter(new) - Counter(original)

difference = calculate_difference(original_dict, new_dict)
print(difference)
network_outbound_usage = sum(value for _,value in  difference.items())
print(network_outbound_usage)
