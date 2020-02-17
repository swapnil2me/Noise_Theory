import os
from datetime import datetime as dt
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float, Boolean, PickleType

import instruments as inst


class MixdownFreqSweep():

    def generateName(self):
        fileName = ''
        fileNameDict = {}
        for i in range(len(self.instrList)):
            voltNow = self.instrList[-1-i].askVolt()
            fileName += str(voltNow) + ''
            fileName += str(self.instrList[-1-i].unit) + '_'
            fileName += str(self.instrList[-1-i].name) + '_'
            fileNameDict[self.instrList[-1-i].name] = [voltNow,self.instrList[-1-i].unit]
        return fileName + str(self.sf) + 'MHz_' + str(self.ef) + 'MHz_'+'FWD.csv', fileName+ str(self.ef) + 'MHz_' + str(self.sf) + 'MHz_'+'BKW.csv', fileNameDict


    def runSweep(self):

        try:
            dataFile_name = self.generateName()

            if not os.path.exists(self.dataLocation):
                os.makedirs(self.dataLocation)

            fwdFile=os.path.join(self.dataLocation,dataFile_name[0])
            bkwFile=os.path.join(self.dataLocation,dataFile_name[1])
            fileNameDict = dataFile_name[2]
            print("---------------XXXXX---------------")
            print(fileNameDict)
            print(fwdFile)
            print("---------------XXXXX---------------")
            freqArray = np.arange(self.sf, self.ef + self.df/2, self.df)

            commonColumns = ['f','A','P','direction']
            columns = [key+'('+val[1]+')' for key,val in fileNameDict.items()] + commonColumns
            voltArray = [val[0] for val in fileNameDict.values()]
            dataF = np.zeros((len(freqArray),len(columns)))
            dataDB = pd.DataFrame(columns=columns+['timeStamp'])
            for i,freq in enumerate(freqArray):
                self.instrList[1].setFreq(freq)
                self.instrList[0].setFreq(freq)
                A,P = self.liaInstr.readLIA()
                dataF[i]= voltArray + [freq,A*1e9,P,1]
                dataDB.loc[0] = voltArray + [freq,A*1e9,P,1,dt.now()]
                dataDB.to_sql(self.paramDict['experintName'], con=self.dbEngine, if_exists='append',index=False)

            pd.DataFrame(dataF,columns=columns).to_csv(fwdFile,index=None)

            if self.bkwSweep:
                freqArray = freqArray[::-1]
                dataB = np.zeros((len(freqArray),len(columns)))
                print("---------------XXXXX---------------")
                print(fileNameDict)
                print(bkwFile)
                print("---------------XXXXX---------------")
                for i,freq in enumerate(freqArray):
                    self.instrList[1].setFreq(freq)
                    self.instrList[0].setFreq(freq)
                    A,P = self.liaInstr.readLIA()
                    dataB[i]= voltArray + [freq,A*1e9,P,-1]
                    dataDB.loc[0] = voltArray + [freq,A*1e9,P,-1,dt.now()]
                    dataDB.to_sql(self.paramDict['experintName'], con=self.dbEngine, if_exists='append',index=False)

                pd.DataFrame(dataB,columns=columns).to_csv(bkwFile,index=None)


        except AttributeError as arrtErr:
            print(arrtErr)
            print('Error Occured')
            for i in range(len(self.instrList)):
                self.instrList[i].rampDown()
                self.instrList[i].close()
            self.liaInstr.close()
            print('instruments closed')


class VoltageSweep(MixdownFreqSweep):

    def __init__(self, dataLocation, instrList, liaInstr, mx, bkwSweep = None):
        self.dataLocation = dataLocation
        self.instrList = instrList
        self.liaInstr = liaInstr
        self.liaInstr.sensitivity = 12
        self.instrList[0].freqOffSet = mx
        self.sf = instrList[0].freqSweepRange[0]
        self.ef = instrList[0].freqSweepRange[-1]
        self.df = instrList[0].freqSweepRange[1]
        self.mx = mx
        self.bkwSweep = bkwSweep


    def sweepSummary(self):
        print('')
        print('The Mixdown Voltage Sweep Summary')
        print('ID     | Name | Unit | Voltage Range  | Freq Range     | Freq Offset')
        for i in range(len(self.instrList)):
            print('Instr ' + str(i) + ': '+str(self.instrList[i].name)
                                    + ' | '+str(self.instrList[i].unit)
                                    + '   | '+str(self.instrList[i].voltageSweepRange)
                                    + '| '+str(self.instrList[i].freqSweepRange)
                                    + '| '+str(self.instrList[i].freqOffSet))
        print('')


    def setExperiment(self):
        voltage_ranges = [i.voltageSweepRange for i in self.instrList]
        assert None not in voltage_ranges, "Please set voltage_ranges for all instrs"
        for i in range(len(self.instrList)):
            if self.instrList[i].askVolt() != voltage_ranges[i][0]:
                self.instrList[i].rampV(voltage_ranges[i][0],10)


    def generateSweepSpace(self):
        voltage_ranges = [i.voltageSweepRange for i in self.instrList]
        assert None not in voltage_ranges, "Please set voltage_ranges for all instrs"
        voltages = [np.arange(i[0],i[-1]+i[1],i[1]) for i in voltage_ranges]
        grids = np.meshgrid(*voltages)
        gridsFlatten = [gr.flatten() for gr in grids]
        sweepSpace = list(zip(*gridsFlatten))
        return sweepSpace


    def runVtgSweep(self):
        sweepSpace = self.generateSweepSpace()
        for i in sweepSpace:
            print('')
            print('Starting frequency sweep:')
            for j in range(len(self.instrList)):
                self.instrList[j].rampV(i[j],10)
            self.runSweep()


    def rampDownAll(self):
        print('')
        print('Ramping down the instruments')
        for i in range(len(self.instrList)):
            self.instrList[i].rampDown()


    def closeAll(self):
        for i in range(len(self.instrList)):
            self.instrList[i].rampV(0,rampN = 10)
            self.instrList[i].close()


class DispersionSweep(VoltageSweep):

    def __init__(self, paramDict):
        vsAC = getattr(inst, paramDict['VsAC']['instClass'])(paramDict['VsAC']['address'])
        vgAC = getattr(inst, paramDict['VgAC']['instClass'])(paramDict['VgAC']['address'])
        vgDC = getattr(inst, paramDict['VgDC']['instClass'])(paramDict['VgDC']['address'])
        liA  = getattr(inst, paramDict['LIA']['instClass'])(paramDict['LIA']['address'],
                                                            paramDict['LIA']['timeConstant'])
        if 'SRS' in paramDict['VgDC']['instClass']:
            print('')
            print('Using AUX OUT #{0} of {1} for vgDC'.format(paramDict['VgDC']['auxOutPort'],
                                                               paramDict['VgDC']['instClass']))
            vgDC.waitFor = paramDict['LIA']['timeConstant']
            vgDC.auxOutPort = paramDict['VgDC']['auxOutPort']

        vsAC.name = paramDict['VsAC']['name']
        vgAC.name = paramDict['VgAC']['name']
        vgDC.name = paramDict['VgDC']['name']
        vsAC.unit = paramDict['VsAC']['unit']
        vgAC.unit = paramDict['VgAC']['unit']
        vgDC.unit = paramDict['VgDC']['unit']

        vsAC.voltageSweepRange = [paramDict['VsAC']['volt'],1.,paramDict['VsAC']['volt']]
        vgAC.voltageSweepRange = [paramDict['VgAC']['volt'],1.,paramDict['VgAC']['volt']]
        vgDC.voltageSweepRange = paramDict['VgDC']['sweepVolt']
        vsAC.freqSweepRange = paramDict['VsAC']['freqRange']
        vgAC.freqSweepRange = paramDict['VsAC']['freqRange']

        dataLocation = paramDict['dataDir']
        bkwSweep = paramDict.get('backSweep')
        mx = paramDict['VsAC']['mixDownFreq']
        VoltageSweep.__init__(self,dataLocation, [vsAC,vgAC,vgDC], liA, mx,bkwSweep)
        self.sweepSummary()
        self.paramDict = paramDict
        self.dbEngine = create_engine('sqlite:///'+os.path.join(self.dataLocation, 'experiments.db'), echo=False)


    def runDispersion(self):
        self.setExperiment()
        print('')
        print('Running Sweep')
        self.runVtgSweep()
        print('')
        print('Dispersion Finished')
        self.rampDownAll()


    def createImage(self):
        sweep = self.paramDict['sweep']['type']
        unit = self.paramDict['sweep']['unit']
        freqSpan = self.paramDict['VsAC']['freqRange']
        voltSpan = self.paramDict['VgDC']['sweepVolt']
        x = []
        x_ = list(np.arange(voltSpan[0],voltSpan[-1] + 2*voltSpan[1],voltSpan[1]))
        y = list(np.arange(freqSpan[0],freqSpan[-1] + 2*freqSpan[1],freqSpan[1]))
        Z_A = np.zeros((len(y)-1, len(x_)-1))
        Z_P = np.zeros((len(y)-1, len(x_)-1))
        index = 0

        for file in os.listdir(self.dataLocation):
            if file.endswith("FWD.csv"):
                x.append(float(file.split(sweep)[0].split(unit)[0]))
                Z_A[:,index] = list(pd.read_csv(os.path.join(self.dataLocation,file))['A'])
                Z_P[:,index] = list(pd.read_csv(os.path.join(self.dataLocation,file))['P'])
                index += 1

        x.append(x_[-1])
        X,Y = np.meshgrid(x,y)
        fig, (ax0, ax1) = plt.subplots(2    , 1)
        c = ax0.pcolor(X, Y, Z_A, cmap='RdBu')
        fig.colorbar(c, ax=ax0)
        c = ax1.pcolor(X, Y, Z_P, cmap='RdBu')
        fig.colorbar(c, ax=ax1)
        plt.show()

        return None


class Rvg():
    """This implementation of RVG is for KT2461"""

    def __init__(self, paramDict):

        self.smuInst = inst.KT2461(paramDict['address'])
        self.sourceChannel = paramDict['source_channel']
        self.sourceVolt = paramDict['sourceVolt']
        self.gateChannel = paramDict['gate_channel']
        self.gateSweep = paramDict['gateSweep']
        self.dataLocation = paramDict['dataLocation']


    def setExperiment(self):
        self.smuInst.rampV(self.sourceChannel, self.sourceVolt)
        self.smuInst.rampV(self.gateChannel, self.gateSweep[0])


    def startExperiment(self):
        Vg = np.arange(self.gateSweep[0], self.gateSweep[-1]+self.gateSweep[1], self.gateSweep[1])
        R = np.zeros(Vg.shape)
        for i,v in enumerate(Vg):
            self.smuInst.rampV(self.gateChannel, v, 10, 0.1)
            R[i] = self.smuInst.readKT(self.sourceChannel, 'r')
        return Vg, R


    def closeExperiment(self):
        self.smuInst.rampDown(self.sourceChannel,10)
        self.smuInst.rampDown(self.gateChannel,10)
        self.smuInst.close()
