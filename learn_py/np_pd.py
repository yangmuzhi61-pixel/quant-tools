import numpy as np

pairs = [(8, 'one'), (3, 'three'), (2, 'two')]
pairs.sort(key=lambda x: -x[0])   # 按英文单词排序
print(pairs)
# [(1, 'one'), (3, 'three'), (2, 'two')]