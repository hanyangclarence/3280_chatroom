import struct
import numpy
import os

class Audio:
    def __init__(self):
        self.initialized = False
        self.data = b''
        self.sampleRate = None
        self.channels = None
        self.bytesPerSample = None
        
    def loadConfig(self, sampleRate, channels, bytesPerSample):
        self.sampleRate = sampleRate
        self.channels = channels
        self.bytesPerSample = bytesPerSample
        self.initialized = True
        
    def loadData(self, data, sampleRate, channels, bytesPerSample):
        assert bytesPerSample==2, "bytesPerSample should be 2"
        assert channels==1 or channels==2, "channels must be 1 or 2"
        self.data = data
        self.sampleRate = sampleRate
        self.channels = channels
        self.bytesPerSample = bytesPerSample
        self.initialized = True
        return 0
        
    def appendData(self, data:bytes, sampleRate, channels, bytesPerSample):
        assert bytesPerSample==2, "bytesPerSample should be 2"
        assert channels==self.channels, "channels mismatch"
        assert sampleRate==self.sampleRate, "sampleRate mismatch"
        self.data = self.data + data
        
    def loadWaveForm(self, waveform, sampleRate, channels, bytesPerSample):
        assert bytesPerSample==2, "bytesPerSample should be 2"
        assert channels==1 or channels==2, "channels must be 1 or 2"
        data = b''
        
        if channels == 2:
            for float in waveform:
                b = struct.pack('h', round(float*32768))
                data += b  # connect bytes
                data += b  # 2 channels
        elif channels == 1:
            for float in waveform:
                b = struct.pack('h', round(float*32768))
                data += b  # connect bytes
                    
        self.data = data
        self.sampleRate = sampleRate
        self.channels = channels
        self.bytesPerSample = bytesPerSample
        self.initialized = True
        return 0
    
    def loadFrames(self, frames, sampleRate, channels, bytesPerSample):
        print("loadFrames with sr="+str(sampleRate)+" channels="+str(channels)+" frameSize="+str(len(frames[0])))
        assert bytesPerSample==2, "bytesPerSample should be 2"
        assert channels==1 or channels==2, "channels must be 1 or 2"
        data = b''
        for frame in frames:
            data+= frame
        self.data = data
        self.sampleRate = sampleRate
        self.channels = channels
        self.bytesPerSample = bytesPerSample
        self.initialized = True
        return 0
        
    def getData(self, sampleRate, channels, bytesPerSample):
        try:
            assert self.initialized==True, "Audio not initialized"
            assert self.sampleRate==sampleRate, "sampleRate mismatch, resample first"
            assert channels==1 or channels==2, "Channels must be 1 or 2"
            assert self.bytesPerSample==2 and bytesPerSample==2, "bytesPerSample should be 2"
            data = b''
            if self.channels==channels:
                return self.data
            elif self.channels==1 and channels==2:
                for i in range(0, len(self.data), self.channels*bytesPerSample):
                    num = struct.unpack('<h', self.data[i:i+bytesPerSample])[0]
                    num = num // 2
                    data += struct.pack('h', num)
                    data += struct.pack('h', num)
            elif self.channels==2 and channels==1:
                for i in range(0, len(self.data), self.channels*bytesPerSample):
                    num1 = struct.unpack('<h', self.data[i:i+bytesPerSample])[0]
                    num2 = struct.unpack('<h', self.data[i+bytesPerSample:i+2*bytesPerSample])[0]
                    num = (num1+num2)/2
                    data += struct.pack('h', num)
                
            return data
        except Exception as e:
            print("Error during getData")
            print(e)
            return 1
        
    def getInfo(self):
        return self.sampleRate, self.channels, self.bytesPerSample
        
        #sampleRate, channels, bytesPerSample are what format you want
    def getWaveForm(self, sampleRate, channels, bytesPerSample):
        try:
            assert self.initialized==True, "Audio not initialized"
            assert self.sampleRate==sampleRate, "sampleRate mismatch, resample first"
            assert channels==1, "Channels of waveform must be 1"
            assert self.bytesPerSample==2 and bytesPerSample==2, "bytesPerSample should be 2"
            waveform = []
            if self.channels==1:
                for i in range(0, len(self.data), self.channels*bytesPerSample):
                    num1 = struct.unpack('<h', self.data[i:i+bytesPerSample])[0]
                    waveform.append(num1/32768.0)
                
            elif self.channels==2:
                for i in range(0, len(self.data), self.channels*bytesPerSample):
                    num1 = struct.unpack('<h', self.data[i:i+bytesPerSample])[0]
                    num2 = struct.unpack('<h', self.data[i+bytesPerSample:i+2*bytesPerSample])[0]
                    waveform.append((num1+num2)/32768.0/2.0)    # resize to [-1, 1], average 2 channels
            
            waveform = numpy.array(waveform)
            return waveform
        except Exception as e:
            print("Error during getWaveForm")
            print(e)
            return 1
    
        #framesize, sampleRate, channels, bytesPerSample are what format you want
    def getFrames(self, sampleRate, channels, frameSize, bytesPerSample):
        try:
            assert self.initialized==True, "Audio not initialized"
            assert self.sampleRate==sampleRate, "sampleRate mismatch, resample first"
            assert channels==1 or channels==2, "Channels must be 1 or 2"
            assert self.bytesPerSample==2 and bytesPerSample==2, "bytesPerSample should be 2"
            frames = []
            if self.channels==channels:
                length = len(self.data)
                i=0
                while True:
                    if i+frameSize>=length:
                        frames.append(self.data[i:])
                        break
                    frames.append(self.data[i:i+frameSize])
                    i += frameSize
            elif self.channels==2 and channels==1:
                #raise Exception("self.channels==2 and channels==1")
                frameIndex = 0
                frame=b''
                for i in range(0, len(self.data), 2*bytesPerSample):
                    num1 = struct.unpack('<h', self.data[i:i+bytesPerSample])[0]
                    num2 = struct.unpack('<h', self.data[i+bytesPerSample:i+2*bytesPerSample])[0]
                    num = (num1+num2)/2
                    frame += struct.pack('h', num)
                    frameIndex += bytesPerSample
                    if frameIndex == frameSize:
                        frames.append(frame)
                        frame = b''
                        frameIndex = 0
                if len(frame)>0:
                    frames.append(frame)
            elif self.channels==1 and channels==2:
                #raise Exception("self.channels==1 and channels==2")
                assert frameSize%2==0, "frameSize is odd number"
                frameIndex = 0
                frame=b''
                for i in range(0, len(self.data), bytesPerSample):
                    num = struct.unpack('<h', self.data[i:i+bytesPerSample])[0]
                    frame += struct.pack('h', num)
                    frame += struct.pack('h', num)
                    frameIndex += 2*bytesPerSample
                    if frameIndex == frameSize:
                        frames.append(frame)
                        frame = b''
                        frameIndex = 0
                if len(frame)>0:
                    frames.append(frame)
                    
            return frames
        except Exception as e:
            print("Error during getFrames")
            print(e)
            return 1
    
    def write(self, filepath):
        assert self.initialized==True, "Audio not initialized"
        print("writing with sr="+str(self.sampleRate)+" channels="+str(self.channels))
        if len(self.data)==0:
            print("No data to write")
            return
        try:
            file = open(filepath, "wb")
            
            datasize = len(self.data)
            
            file.write("RIFF".encode())                     # 0-3    RIFF
            file.write(struct.pack('i', 36+datasize))       # 4-7    chunksize = datasize + 36
            file.write("WAVEfmt ".encode())                 # 8-15   WAVEfmt(SPACE)
            file.write(struct.pack('i', 16))                # 16-19  SubchunkSize = 16
            file.write(struct.pack('h', 1))                 # 20-21  AudioFormat = 1
            file.write(struct.pack('h', self.channels))     # 22-23  NumOfChannels always 2
            file.write(struct.pack('i', self.sampleRate))   # 24-27  SampleRate
            byte_rate = self.sampleRate * self.channels * self.bytesPerSample
            file.write(struct.pack('i', byte_rate))         # 28-31  ByteRate
            block_align = 2 * self.bytesPerSample
            file.write(struct.pack('h', block_align))       # 32-33  BlockAlign
            bits_per_sample = self.bytesPerSample * 8
            file.write(struct.pack('h', bits_per_sample))   # 34-35  BitsPerSample
            file.write("data".encode())                     # 36-39  data
            file.write(struct.pack('i', datasize))          # 40-43  datasize
            
            file.write(self.data)
            
            file.close()
            print("Write success")
            return 0
        except Exception as e:
            try:
                file.close()
                os.remove(filepath)
            except:
                pass
            print("Error during write")
            print(e)
            return 1


    def read(self, filepath):
        try:
            file = open(filepath, "rb")
            
            assert str(file.read(4), encoding='utf-8')=="RIFF", "File does not start with RIFF"         # 0-3    RIFF
            chunkSize = int.from_bytes(file.read(4), "little")                                          # 4-7    chunksize = datasize + 36
            assert str(file.read(8), encoding='utf-8')=="WAVEfmt ", "File has incorrect WAVEfmt part"   # 8-15   WAVEfmt(SPACE)
            assert int.from_bytes(file.read(4), "little")==16, "SubchunkSize is not 16"                 # 16-19  SubchunkSize = 16
            assert int.from_bytes(file.read(2), "little")==1, "AudioFormat is not 1"                    # 20-21  AudioFormat = 1
            channels = int.from_bytes(file.read(2), "little")                                           # 22-23  NumOfChannels
            assert channels==2 or channels==1, "channels must be 1 or 2"
            sampleRate = int.from_bytes(file.read(4), "little")                                        # 24-27  SampleRate
            ByteRate = int.from_bytes(file.read(4), "little")                                           # 28-31  ByteRate
            BlockAlign = int.from_bytes(file.read(2), "little")                                         # 32-33  BlockAlign
            BitsPerSample = int.from_bytes(file.read(2), "little")                                      # 34-35  BitsPerSample
            assert BitsPerSample==16, "Can't handle BitsPerSample != 16"
            assert str(file.read(4), encoding='utf-8')=="data", "\"data\" header incorrect"             # 36-39  data
            datasize = int.from_bytes(file.read(4), "little")                                           # 40-43  datasize

            bytesPerSample = BitsPerSample//8
            assert ByteRate == channels*sampleRate*bytesPerSample, "Incorrect ByteRate"
            assert BlockAlign == channels*bytesPerSample, "Incorrect BlockAlign"
            assert chunkSize == datasize + 36, "Incorrect chunksize or datasize"
            
            data = file.read(datasize)
            
            file.close()
            print("Read success")
            self.initialized = True
            self.data = data
            self.sampleRate = sampleRate
            self.channels = channels
            self.bytesPerSample = bytesPerSample
            
            return
        except Exception as e:
            print("Error during read")
            print(e)
            return 1
        