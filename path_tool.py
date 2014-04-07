import os

fname = "eoieggs.txt"
with open(fname) as f:
    content = f.readlines()

for i in range(0,len(content)):
    content[i] = content[i].replace("\n","")

data  = "export PYTHONPATH="    

data += ""+os.getcwd()+"/extern/coverage-model"
data += ":"+os.getcwd()+"/extern/coverage-model/interface"
data += ":"+os.getcwd()+"/extern/pyon"
data += ":"+os.getcwd()+"/extern/coverage-model/coverage_model:"

data += ":".join(content)   

data += ":$PYTHONPATH"  
new_f = "python_path.txt"
with open(new_f,'w') as new_f:
    new_f.write(data)