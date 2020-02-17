# -*- coding: utf-8 -*-
"""
Created on Mon Feb 17 14:57:10 2020

@author: nemslab4
"""

import instruments as ins
import numpy as np
import pandas as pd

tc = 10.0 #mS
lia = ins.SRS830(8,tc)
datapoints = 1000
data = np.zeros((datapoints,2))

for i in range(datapoints):
    data[i] = lia.readLIA()
    
pd.DataFrame(data, columns = ['A','P']).to_csv('{}_datapoints_{}_mS_TC.csv'.format(datapoints,tc))