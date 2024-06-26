# #%%
# """Main script for training the model."""
# import debugpy
# debugpy.listen(5678)
# print('Waiting for debugger')
# debugpy.wait_for_client()
# print('Debugger attached')
#%%
# imports
import sys
import os
import re
from absl import flags
#%%
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import pickle
import jax
import numpyro
numpyro.set_platform('cpu')
print(jax.lib.xla_bridge.get_backend().platform)
#%%
# paths
_ROOT_DIR = "/home/paperspace/"
os.chdir(_ROOT_DIR + 'graphical-models-external-networks/')
sys.path.append(_ROOT_DIR + "graphical-models-external-networks/Network_Spike_and_Slab/numpyro/functions")

data_path = './Data/COVID/Pre-processed Data/'
data_save_path = _ROOT_DIR + 'NetworkSS_results_loglikrepr_1000w/'
if not os.path.exists(data_save_path):
    os.makedirs(data_save_path, mode=0o777)

# define flags
# FLAGS = flags.FLAGS
# flags.DEFINE_integer('p', None, 'dimension of each observation')
# flags.mark_flags_as_required(['p'])
# FLAGS(sys.argv)
# %%
# p = FLAGS.p

CP_files = {}
for f in os.listdir(data_save_path):
    if re.search(r'(_CP)\d+', f):
        CP = int(re.search(r'(_CP)\d+', f)[0][3:])
        CP_files[CP] = f

for cp_ix, (k,v) in enumerate(sorted(CP_files.items())):
    print(v)
    if cp_ix==0:
        with open(data_save_path + v, 'rb') as fr:
            res = pickle.load(fr)
        samples = {k:[] for k in res.keys()}
    with open(data_save_path + v, 'rb') as fr:
        res = pickle.load(fr)
    for k in res.keys():
        samples[k].append(res[k])

# %%
# with open(data_save_path + f'NetworkSS_1mcmc_p{p}_s4100_aggregate0.sav' , 'wb') as f:
#     pickle.dump((samples), f)
# # %%

# with open(data_save_path + f'NetworkSS_1mcmc_p{p}_s4100_aggregate0.sav', 'rb') as fr:
#     samples = pickle.load(fr)
# # %%
sampless = {}
for k,v in samples.items():
    # print(k)
    # try:
    #     sampless[k] = np.vstack(np.array(v, dtype=object))
    # except:
    sampless[k] = np.vstack(np.array([s[:,None] for s in v], dtype=object))
del samples
# sampless = {k:np.vstack(np.array(v, dtype=object)) for k,v in samples.items()}
# %%
tot_samples = sampless[k].shape[0]
print(tot_samples)
with open(data_save_path + f'NetworkSS_1mcmc_p{p}_s{tot_samples}_aggregate.sav' , 'wb') as f:
    pickle.dump((sampless), f)
# %%
