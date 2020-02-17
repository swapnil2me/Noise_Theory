import vxi11
import pyvisa
import time
from math import isclose

class Instrument:

    def __init__(self,address,name = None,unit = None, freqOffSet = 0.0):
        self.address = address
        self.name = name
        self.unit = unit
        self.freqOffSet = freqOffSet #Hertz
        self._instR = vxi11.Instrument(address,'inst0')
        self._voltageSweepRange = None
        self._freqSweepRange = None
        self.maxVoltage = 1000 # miliVolts


    @property
    def voltageSweepRange(self):
        return self._voltageSweepRange


    @voltageSweepRange.setter
    def voltageSweepRange(self, voltList):
        if isinstance(voltList, list) and len(voltList) == 3:
            self._voltageSweepRange = voltList
        else:
            print('The sweep range must be a list of length 3')


    @property
    def freqSweepRange(self):
        return self._freqSweepRange


    @freqSweepRange.setter
    def freqSweepRange(self, freqList):
        if isinstance(freqList, list) and len(freqList) == 3:
            self._freqSweepRange = freqList
        else:
            print('The sweep range must be a list of length 3')


    def askVolt(self):
        return float(self._instR.ask(':sour:pow:lev?\n')) * 1000 #in miliVolts


    def incrementSweepVolt(self):
        currentVolt = self.askVolt()
        if currentVolt < self.maxVoltage - self.voltageSweepRange[1]:
            self.rampV(currentVolt + self.voltageSweepRange[1], rampN = 5,ps = 0.001)
        else:
            print('Can not increase voltage, output will surpass maximum limit')


    def decrementSweepVolt(self):
        currentVolt = self.askVolt()
        if currentVolt - self.voltageSweepRange[1] >= 0.0 :
            self.rampV(currentVolt - self.voltageSweepRange[1], rampN = 5,ps = 0.001)
        else:
            print('Can not decrease voltage, current voltage is less than step size')


    def rampV(self, setV, rampN = 200,ps = 0.05):
        if setV == 0.0:
            setV = 1.0
        outV     = float(self._instR.ask(':sour:pow:lev?')) * 1000 #in miliVolts
        rampStep = (outV - setV)/rampN
        if rampStep == 0.0:
            print('{0} at {1} {2}'.format(self.name, setV, self.unit))
            return
        print('Ramping {0} to {1} {2} in {3} steps'.format(self.name, setV, self.unit, rampN))
        for i in range(rampN+1):
            increment = (outV - i*rampStep) / 1000 # in Volts
            self._instR.write(":pow {0:.8f}".format(increment))
            time.sleep(ps)


    def rampDown(self,rampN = 200,ps = 0.05):
        self.rampV(1,10,ps)


    def setFreq(self, freq, phs = 0):
        self._instR.write('FREQ {0:.8f} MHz; PHAS {0:.8f};'.format(
                                                    freq - self.freqOffSet * 1e-6,
                                                    phs))


    def close(self):
        self._instR.close()


class Sma100A(Instrument):

    def __init__(self,address):
        #Instrument.__init__(self,address)
        super(Sma100A, self).__init__(address)
        self._instR.write('UNIT:POW V')


class  Anapico(Instrument):

    def __init__(self, address):
        super(Anapico, self).__init__(address)
        self._instR.write("UNIT:POW V\n")
        if not int(self._instR.ask("OUTP:STAT?\n")):
            self._instR.write(':sour:pow:lev:imm:ampl 0.001\n')
            self._instR.write(':OUTP:STAT ON\n')


    def rampV(self, setV, rampN = 200,ps = 0.05):
        if setV == 0:
            setV = 1
        outV = float(self._instR.ask(':sour:pow:lev?\n')) * 1000 #in miliVolts
        rampStep = (outV - setV)/rampN
        if rampStep == 0.0:
            print('{0} at {1} {2}'.format(self.name, setV, self.unit))
            return
        print('Ramping {0} to {1} {2} in {3} steps'.format(self.name, setV, self.unit, rampN))
        for i in range(rampN+1):
            increment = (outV - i*rampStep) / 1000 # in Volts
            self._instR.write(":sour:pow:lev:imm:ampl {0:.8f}\n".format(increment))
            time.sleep(ps)


    def setFreq(self, freq, phs = 0):
        self._instR.write('FREQ {0:.8f}e6\n'.format(freq - self.freqOffSet * 1e-6))
        self._instR.write('SOUR:PHAS {0:.8f}\n'.format(phs))


class SRS830(Instrument):
    """docstring for SRS830."""

    def __init__(self, address, waitFor=300, auxOutPort=None):
        rm = pyvisa.ResourceManager()
        self.address = int(address)
        self.waitFor = waitFor
        self._instR = rm.open_resource('GPIB0::'+str(address)+'::INSTR')
        self.auxOutPort = auxOutPort
        self.name = 'LIA'
        self.unit = 'Volts'
        self._voltageSweepRange = 'NA'
        self._freqSweepRange = 'NA'
        self.freqOffSet = 'NA'


    def checkStatus(self):
        ovldI = self._instR.query('lias?0\n')
        ovldTC = self._instR.query('lias?1\n')
        return any(list(map(int,(ovldI, ovldTC))))


    def unlocked(self):
        return int(self._instR.query('lias?3\n')) == 1


    @property
    def sensitivity(self):
        self._sensitivity = int(self._instR.query('SENS ?'))
        return self._sensitivity


    @sensitivity.setter
    def sensitivity(self, numB):
        self._instR.write('SENS' + str(int(numB)))
        self._sensitivity = int(numB)
        print('LIA sensitivity changed to: {}'.format(numB))
        return self._sensitivity


    def outputOverload(self):
        return int(self._instR.query('lias?2\n')) == 1


    def matchSensitivity(self):
        self.sensitivity = self.sensitivity - 1
        while not self.outputOverload():
            self.sensitivity = self.sensitivity - 1


    def readLIA(self):
        start_time = time.time()
        while self.checkStatus():
            time.sleep(self.waitFor/1000)
            elapsed_time1 = time.time() - start_time
            if elapsed_time1 > 5:
                print('Check Instrument for overload')
                print('')
        #print('Overload Resolved')
        while self.unlocked():
            time.sleep(self.waitFor/1000)
            elapsed_time2 = time.time() - start_time
            if elapsed_time2 > 20:
                print('Reference is unlocked, please check reference input')
                print('')
        #print('Locked to the reference')
        while self.outputOverload():
            self.sensitivity = self.sensitivity + 1
            time.sleep(self.waitFor/1000)
        time.sleep(self.waitFor/1000)
        return list(map(float,(self._instR.query('SNAP?3, 4').split(','))))


    def askVolt(self):
        assert self.auxOutPort != None, 'Output aux port not defined'
        auxOutPort = self.auxOutPort
        return float(self._instR.query('AUXV?{}\n'.format(auxOutPort))) #in Volts


    def rampV(self, setV, rampN = 200,ps = 0.05):
        """
        setV is in Volts
        """
        assert self.auxOutPort != None, 'Output aux port not defined'
        auxOutPort = self.auxOutPort
        #print('Using Aux Port {}'.format(auxOutPort))
        outV = float(self._instR.query('AUXV?{}\n'.format(auxOutPort))) #in Volts
        rampStep = (outV - setV)/float(rampN)
        if rampStep == 0.0:
            print('{0} at {1} {2}'.format(self.name, setV, self.unit))
            return
        print('Ramping {0} to {1} {2} in {3} steps'.format(self.name, setV, self.unit, rampN))
        for i in range(1,rampN+1):
            increment = (outV - i*rampStep) # in Volts
            self._instR.write("AUXV{0:d},{1:.8f}\n".format(auxOutPort,increment))
            time.sleep(ps)
        outV = float(self._instR.query('AUXV?{}\n'.format(auxOutPort))) #in Volts
        if isclose(outV, setV, rel_tol = 1e-3):
            print('Correcting Output')
            self._instR.write("AUXV{0:d},{1:.8f}\n".format(auxOutPort,setV))
        else:
            print(outV, setV)
            print('Actual output is off by 1e-3 V')


    def rampDown(self,rampN = 200,ps = 0.05):
        assert self.auxOutPort != None, 'Output aux port not defined'
        auxOutPort = self.auxOutPort
        self.rampV(0,10,ps)


class SRS844(SRS830):
    """docstring for SRS844."""

    def __init__(self, address, waitFor=300, auxOutPort=None):
        SRS830.__init__(self, address, waitFor, auxOutPort)


    def readLIA(self):
        time.sleep(self.waitFor/1000)
        return list(map(float,(self._instR.query('SNAP?3, 5').split(','))))


    def askVolt(self):
        assert self.auxOutPort != None, 'Output aux port not defined'
        auxOutPort = self.auxOutPort
        return float(self._instR.query('AUXO?{}\n'.format(auxOutPort))) #in Volts


    def rampV(self, setV, rampN = 200,ps = 0.05):
        """
        setV is in Volts
        """
        assert self.auxOutPort != None, 'Output aux port not defined'
        auxOutPort = self.auxOutPort
        #print('Using Aux Port {}'.format(auxOutPort))
        outV = float(self._instR.query('AUXO?{}\n'.format(auxOutPort))) #in Volts
        rampStep = (outV - setV)/float(rampN)
        if rampStep == 0.0:
            print('{0} at {1} {2}'.format(self.name, setV, self.unit))
            return
        print('Ramping {0} to {1} {2} in {3} steps'.format(self.name, setV, self.unit, rampN))
        for i in range(1,rampN+1):
            increment = (outV - i*rampStep) # in Volts
            self._instR.write("AUXO{0:d},{1:.8f}\n".format(auxOutPort,increment))
            time.sleep(ps)
        outV = float(self._instR.query('AUXO?{}\n'.format(auxOutPort))) #in Volts
        if isclose(outV, setV, rel_tol = 1e-3):
            print('Correcting Output')
            self._instR.write("AUXO{0:d},{1:.8f}\n".format(auxOutPort,setV))
        else:
            print(outV, setV)
            print('Actual output is off by 1e-3 V')


class KT2461(Instrument):


    def __init__(self, address):
        Instrument.__init__(self, address)


    def rampV(self, channel, setV, rampN = 200, ps = 0.05):
        outV = self.readKT(channel,'v')
        rampStep = (outV - setV)/float(rampN)
        if rampStep == 0.0:
            print('{0} at {1} {2}'.format(self.name, setV, self.unit))
            return
        print('Ramping {0} to {1} {2} in {3} steps'.format(self.name, setV, self.unit, rampN))
        for i in range(1,rampN+1):
            increment = (outV - i*rampStep) # in Volts
            self._instR.write('smu{}.source.levelv={}'.format(channel,increment))
            time.sleep(ps)


    def readKT(self, channel, read):
        """
        read Voltage ('v') has unit of Volts
        read Current ('i') has unit of Amps
        read Resistance ('r') has unit of Ohms
        """
        self._instR.write('funC=smu{}.measure.{}()'.format(channel,read))
        self._instR.write('print(funC)')
        value = float(self._instR.read())
        return value


    def rampDown(self, channel, rampN = 200, ps = 0.05):
        self.rampV(channel, 0.0, rampN, ps)
