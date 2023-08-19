import sys
import os

root_path = "addon/primitives/"

files = os.listdir(root_path)

for name in files:
    ending = name[-4:]
    if ending != '.svg':
        continue
    path = root_path + name
    print(path)
    data = ''
    with open(path,"r") as f:
        data = f.read()
        data = data.replace('height="40" ','')
        data = data.replace('width="40" ','')
        data = data.replace('viewBox="4 4 30 30"','viewBox="4 4 32 32"')
    with open(path,"w") as f:
        f.write(data)
    
    


