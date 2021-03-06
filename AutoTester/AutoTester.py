'''
AutoTester is the controlling software to automatically run water tests
Further info can be found at: https://robogardens.com/?p=928
This software is free for DIY, Nonprofit, and educational uses.
Copyright (C) 2017 - RoboGardens.com
    
Created on Aug 9, 2017

This module is the main server module which runs the tests and hosts the streaming video of the tester.

@author: Stephen Hayes
'''
import rpyc   # @UnresolvedImport
from TesterCore import Tester,getBasePath
import time
import atexit
import datetime
import threading
import cv2   # @UnresolvedImport
from http.server import BaseHTTPRequestHandler,HTTPServer
from socketserver import ThreadingMixIn
import numpy as np
import math
import traceback
from rpyc.utils.server import ThreadedServer   # @UnresolvedImport
import _pickle
import logging
import schedule    # @UnresolvedImport
import requests   # @UnresolvedImport
import os
import shutil
from FishEyeWrapper import FishEye
from ImageCheck import matchMarkers,evaluateColor,evaluateColorBinary,findLightingEnvironment
from Alarms import sendMeasurementReport,sendReagentAlarm,sendFillAlarm,sendDispenseAlarm,sendEvaluateAlarm,sendUnableToRotateAlarm,sendCannotOpenStoppersAlarm,sendCannotParkAlarm,sendOutOfLimitsAlarm,sendOutOfLimitsWarning
from Learn import testFeature,insertTrainingGraphic,testDlibForVerticalPosition,testDlibForHorizontalPosition
import sys
from skimage.color.rgb_colors import greenyellow
import random
from random import randint
import django
import platform

currentVersion='0.02'
remoteControlThreadRPYC=None
tester=None
letterSequenceCheck={'A':'B','B':'C','C':'D','D':'E','E':'F','F':'G','G':'H','H':'I','I':'J','J':'K','K':'L','L':'A'}

degreesToMove={'AA':0,'AB':30,'AC':60,'AD':90,'AE': 120,'AF':150,'AG':180,'AH': -150,'AI':-120,'AJ':-90,'AK':-60,'AL':-30,
             'BA':-30,'BB':0,'BC':30,'BD':60,'BE':90,'BF':120,'BG':150,'BH':180,'BI':-150,'BJ':-120,'BK':-90,'BL':-60,
             'CA':-60,'CB':-30,'CC':0,'CD':30,'CE':60,'CF':90,'CG':120,'CH':150,'CI':180,'CJ':-150,'CK':-120,'CL':-90,
             'DA':-90,'DB':-60,'DC':-30,'DD':0,'DE':30,'DF':60,'DG':90,'DH':120,'DI':150,'DJ':180,'DK':-150,'DL':-120,
             'EA':-120,'EB':-90,'EC':-60,'ED':-30,'EE':0,'EF':30,'EG':60,'EH':90,'EI':120,'EJ':150,'EK':180,'EL':-150,
             'FA':-150,'FB':-120,'FC':-90,'FD':-60,'FE':-30,'FF':0,'FG':30,'FH':60,'FI':90,'FJ':120,'FK':150,'FL':180,
             'GA':180,'GB':-150,'GC':-120,'GD':-90,'GE':-60,'GF':-30,'GG':0,'GH':30,'GI':60,'GJ':90,'GK':120,'GL':150,
             'HA':150,'HB':180,'HC':-150,'HD':-120,'HE':-90,'HF':-60,'HG':-30,'HH':0,'HI':30,'HJ':60,'HK':90,'HL':120,
             'IA':120,'IB':150,'IC':180,'ID':-150,'IE':-120,'IF':-90,'IG':-60,'IH':-30,'II':0,'IJ':30,'IK':60,'IL':90,
             'JA':90,'JB':120,'JC':150,'JD':180,'JE':-150,'JF':-120,'JG':-90,'JH':-60,'JI':-30,'JJ':0,'JK':30,'JL':60,
             'KA':60,'KB':90,'KC':120,'KD':150,'KE':180,'KF':-150,'KG':-120,'KH':-90,'KI':-60,'KJ':-30,'KK':0,'KL':30,
             'LA':30,'LB':60,'LC':90,'LD':120,'LE':150,'LF':180,'LG':-150,'LH':-120,'LI':-90,'LJ':-60,'LK':-30,'LL':0}
destinationLetters='ABCDEFGHIJKL'



def screenPresent(name):
    from subprocess import check_output
    var = str(check_output(["screen -ls; true"],shell=True))
    index=var.find(name)
    return index>-1

def runWebserverOld(tester,name):
    from subprocess import call
    call(["screen","-d","-m","-S",name,"python3", "/home/pi/AutoTesterv2/manage.py","runserver","0.0.0.0:" + str(tester.webPort),"--insecure"])            

def generateWebLaunchFile(tester):
    launchFile=tester.basePath + "/launchWebServer.sh"
    launchText="#!/bin/bash\nexport WORKON_HOME=$HOME/.virtualenvs\nexport VIRTUALENVWRAPPER_PYTHON=/usr/bin/python3\nsource /usr/local/bin/virtualenvwrapper.sh\nworkon "
    launchText = launchText + tester.virtualEnvironmentName + "\n"
    launchText=launchText + 'python ' + tester.basePath + 'manage.py runserver 0.0.0.0:' + str(tester.webPort) + ' --insecure\n'
    f=open(launchFile,"w+")
    f.write(launchText)
    f.close()
    
def runWebServer(tester,name):
    from subprocess import call
    generateWebLaunchFile(tester)
    call(["screen","-d","-m","-S",name,"bash", "launchWebServer.sh" ])   

def sleepUntilNextInterval(lastTime,intervalInSeconds):
    timeInterval=datetime.timedelta(seconds=intervalInSeconds)
    nextTime=lastTime+timeInterval
    while nextTime<datetime.datetime.now():
        nextTime+=timeInterval
    timeToSleep=(nextTime-datetime.datetime.now()).total_seconds()
    time.sleep(timeToSleep)
    return nextTime

def loadFeatureWindow(tester,featureName):
    if not tester.referenceMarkFound:
        return None
    try:
        feat=tester.featureList[featureName]
        feat.setTesterClipFromFeature(tester)
        return feat
    except:
        tester.debugLog.exception("Continuing...")
        return None
        
class TesterRemoteControl(rpyc.Service):
    def on_connect(self):
        # code that runs when a connection is created
        # (to init the serivce, if needed)
        self.tester=tester

    def on_disconnect(self):
        # code that runs when the connection has already closed
        # (to finalize the service, if needed)
        pass
    
    def exposed_testerOperation(self,operation):
        try:
            processWebCommand(tester,operation)
        except:
            tester.debugLog.exception("Continuing...")
    
def startHandler(threadName,operation): 
    tester.debugMessage('Thread: ' + threadName + ' started')
    operation.start() 
    
def videoGrabber():
    frameIntervalDelta=datetime.timedelta(milliseconds=1000/tester.framesPerSecond)
    frameIntervalSecs=frameIntervalDelta.microseconds/1000000
#    i=1
    tester.webcamInitialize()
    time.sleep(.1)
    nextTime=datetime.datetime.now()
    while True:
        try:
            if tester.suppressProcessing:
                try:
                    imageLo=tester.grabFrame()
                except:
                    tester.debugLog.exception("Continuing...")  
                    imageLo=None                              
                if imageLo is None:
                    time.sleep(.01)
                else:
                    tester.videoLowResCaptureLock.acquire()
                    tester.latestLowResImage=imageLo
                    tester.videoLowResCaptureLock.notifyAll()
                    tester.videoLowResCaptureLock.release()                
            else:
                currTime=datetime.datetime.now()
                if currTime>=nextTime:
                    try:
                        if tester.simulation:
                            imageLo=tester.fakeFrame()
                        else:
                            imageLo=tester.grabFrame()
                    except:
                        tester.debugLog.exception("Continuing...")  
                        imageLo=None                              
                    if imageLo is None:
                        time.sleep(.01)
                    else:
                        tester.videoLowResCaptureLock.acquire()
                        tester.latestLowResImage=imageLo
                        tester.videoLowResCaptureLock.notifyAll()
                        tester.videoLowResCaptureLock.release()
    #                    tester.debugMessage('Grabbed low res frame')
    #                i+=1
                    nextTime=nextTime+frameIntervalDelta
                else:
                    timeRemainingUntilNextFrame=(nextTime-currTime).microseconds/1000000
                    time.sleep(timeRemainingUntilNextFrame)
        except:
            tester.debugLog.exception("Continuing...")
            time.sleep(.1)

class TesterViewer(BaseHTTPRequestHandler):
    
    def do_GET(self):
        font = cv2.FONT_HERSHEY_SIMPLEX        
        if self.path.endswith('.mjpg'):
            self.send_response(200)
            self.send_header('Content-type','multipart/x-mixed-replace; boundary=--jpgboundary')
            self.end_headers()
            while tester.streamVideo:
                try:
                    if tester.suppressProcessing:
                        while tester.suppressProcessing:
                            time.sleep(1)
                            return
                    tester.videoLowResCaptureLock.acquire()
                    tester.videoLowResCaptureLock.wait()
                    if tester.suppressProcessing:
                        tester.videoLowResCaptureLock.release()
                        jpg=tester.dummyBlackScreen
                    else:
                        imageCopy=tester.latestLowResImage.copy()
                        tester.videoLowResCaptureLock.release()
                        cv2.putText(imageCopy,'System Status: ' + tester.systemStatus,(20,25), font, .75,(255,255,255),2,cv2.LINE_AA)                    
                        if not tester.testStatus is None:
                            try:
                                cv2.putText(imageCopy,"Running Test: " + tester.currentTest,(20,55), font, .75,(255,255,255),2,cv2.LINE_AA)
                                cv2.putText(imageCopy,tester.testStatus,(20,85), font, .75,(255,255,255),2,cv2.LINE_AA)                                
                            except:
                                tester.debugLog.exception("Error displaying test Status")

                        if tester.showTraining and not tester.currentFeature is None:
                            insertTrainingGraphic(tester,imageCopy)
                        if tester.seriesRunning:
                                    cv2.putText(imageCopy,'Series Running',(200,115), font, .75,(255,255,255),2,cv2.LINE_AA)                                
                        if tester.referenceMarkFound and tester.displayDot:
                            cv2.line(imageCopy,(int(tester.avgCircleLeftMarkerCol),int(tester.avgCircleLeftMarkerRow)),(int(tester.avgCircleRightMarkerCol),int(tester.avgCircleRightMarkerRow)),(255,0,0),4)
                        if tester.colorTable:
                            try:
                                colorTable=tester.colorTable.generateColorTableDisplay(tester,width=tester.colorTable.tableWidth,height=tester.colorTable.tableRowHeight)
                                if not colorTable is None:
                                    showTableRows,showTableCols,showTableColors=colorTable.shape
                                    imageCopy[tester.colorTable.tableStartPosition:tester.colorTable.tableStartPosition+showTableRows,:showTableCols,:] =  colorTable
                            except:
                                traceback.print_exc()
    #                    r,jpg = cv2.imencode('.jpg',tester.maskGrey)
                        r,jpg = cv2.imencode('.jpg',imageCopy)
                    self.wfile.write(bytearray("--jpgboundary\r\n",'utf-8'))
                    self.send_header('Content-type','image/jpeg')
                    self.send_header('Content-length',str(len(jpg)))
                    self.end_headers()
                    self.wfile.write(bytearray(jpg))
                    self.wfile.write(bytearray('\r\n','utf-8'))
                except:
#                    tester.debugLog.exception("Continuing...")
                    break                    
            tester.debugMessage('Connection aborted')
            while not tester.streamVideo:
                time.sleep(1)
            return
        if self.path.endswith('.html'):
            self.send_response(200)
            self.send_header('Content-type','text/html')
            self.end_headers()
            self.wfile.write('<html><head></head><body>')
            self.wfile.write('<img src="tester.mjpg"/>')
            self.wfile.write('</body></html>')
            return

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""

def videoStreamer():
    while tester.streamVideo:
        tester.debugMessage('Restarting Streaming Server')
        try:
            server = ThreadedHTTPServer(('', tester.videoStreamingPort), TesterViewer)
            tester.debugMessage("MJPG Server Started")
            server.serve_forever()
        except:
            tester.debugLog.exception("Closing Socket")
            server.socket.close()
            
def captureImages():
    while True:
        try:
            tester.captureImageLock.acquire()
            tester.captureImageLock.wait()
            tester.captureImageLock.release()
            tester.videoLowResCaptureLock.acquire()
            tester.videoLowResCaptureLock.wait()
            if tester.useImageForCalibration:
                currentImage=tester.latestLowResImage.copy()
                tester.useImageForCalibration=False
                tester.videoLowResCaptureLock.release()
                sampleDirectory=tester.basePath + 'Calibrate/Samples'
                if not os.path.isdir(sampleDirectory):
                    tester.infoMessage('Creating ' + sampleDirectory)
                    os.mkdir(sampleDirectory)
                fn=sampleDirectory + '/Image-(' + tester.lensType + ',' + str(tester.cameraHeightLowRes) + ' x ' + str(tester.cameraWidthLowRes) + ')-' + datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S") + ').jpg'
                cv2.imwrite(fn,currentImage)
                tester.debugMessage('Calibration Image image saved at: ' + fn)
            else:
                if tester.currentFeature==None:
                    currentClippedWindow=tester.latestLowResImage.copy()
                    tester.videoLowResCaptureLock.release()
                    fn=tester.basePath + 'Images/ClippedImages/Image-' + datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S") + '.jpg'
                    cv2.imwrite(fn,currentClippedWindow)
                    tester.debugMessage('Full image saved at: ' + fn)
                else:                    
                    currentClippedWindow=tester.latestLowResImage[tester.featureWindowULRow:tester.featureWindowLRRow,tester.featureWindowULCol:tester.featureWindowLRCol,:]
                    tester.videoLowResCaptureLock.release()
                    fn=tester.basePath + 'Images/ClippedImages/Image-' + datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S") + '.jpg'
                    cv2.imwrite(fn,currentClippedWindow)
                    tester.debugMessage('Clipped image saved at: ' + fn)
        except:
            tester.debugLog.exception("Continuing...")
        time.sleep(1)
                 
def saveVideo(tester,duration=30):    
    startTime=datetime.datetime.now()
    staticFilepath=tester.basePath+"/Images"
    fileName=staticFilepath + '/Video-' + tester.testerName + '/Image-' + startTime.strftime("%Y-%m-%d %H-%M-%S") + '.avi'
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    rows,cols,colors=tester.latestLowResImage.shape
    tester.videoLowResCaptureLock.release()
    frameCount=0
    tester.infoMessage('Starting to save ' + str(duration) + ' seconds of video')
    out = cv2.VideoWriter(fileName,fourcc,tester.framesPerSecond, (cols,rows),isColor=True)
    font = cv2.FONT_HERSHEY_SIMPLEX        
    while (datetime.datetime.now()-startTime).seconds<duration:
        tester.videoLowResCaptureLock.acquire()
        tester.videoLowResCaptureLock.wait()
        imageCopy=tester.latestLowResImage.copy()
        tester.videoLowResCaptureLock.release()
        timestamp=datetime.datetime.now()
        nowText=timestamp.strftime("%Y-%m-%d %H-%M-%S")
        cv2.putText(imageCopy,'Time: ' + nowText,(25,rows-12), font, .75,(0,0,255),3,cv2.LINE_AA)
        out.write(imageCopy)
        frameCount+=1
    out.release()
    tester.infoMessage(str(frameCount) + ' frames saved to ' + fileName)

def clearCameraCalibrationPhotos(tester):
    pathToCamerasCalibrationFolder=tester.basePath+'Calibrate'
    pathToCalibrationImages=pathToCamerasCalibrationFolder + '/Samples'
    calibrationPhotoList=os.listdir(pathToCalibrationImages)
    count=0
    for file in calibrationPhotoList:
        os.remove(pathToCalibrationImages + '/' + file)
        count+=1
    tester.infoMessage(str(count) + ' files deleted from ' + pathToCalibrationImages)

def checkerboardImageFisheyeCalibration(tester,pathToCamerasCalibrationFolder):
    #This loads the input images from the sample directory of the input
    NX=9
    NY=6
    pathToCalibrationImages=pathToCamerasCalibrationFolder + '/Samples'
    imgList = sorted(os.listdir(pathToCalibrationImages))
    imgs_paths=[]
    for fileName in imgList:
        if useImageAsSample(tester,fileName):
            imgs_paths.append(pathToCalibrationImages+'/'+fileName)
    fe = FishEye(nx=NX, ny=NY, verbose=True)
    tester.infoMessage('Fisheye calibration model created')
    rms, K, D, rvecs, tvecs = fe.calibrate(
        imgs_paths,
        show_imgs=False
    )
    tester.infoMessage('Fisheye calibration model done')
    pathToCalibrationData=pathToCamerasCalibrationFolder + '/FisheyeUndistort-(' + tester.lensType + ',' + str(tester.cameraHeightLowRes) + ' x ' + str(tester.cameraWidthLowRes) + ')-' + sys.version[0] + '.pkl'
    with open(pathToCalibrationData, 'wb') as f:
        _pickle.dump([fe,tester.cameraFisheyeExpansionFactor], f)
    
    pathToOutputData=pathToCamerasCalibrationFolder + '/UndistortedUsingFisheye'
    if not os.path.isdir(pathToOutputData):
        os.mkdir(pathToOutputData)
    
    for fileName in imgList:
        if useImageAsSample(tester,fileName):
            img = cv2.imread(pathToCalibrationImages+'/'+fileName)
            height,width,colors=img.shape
            Rmat=np.array([[1.,0.,0.],[0.,1.,0.],[0.,0.,tester.cameraFisheyeExpansionFactor]])
            undist_img = fe.undistort(img, undistorted_size=(width, height),R=Rmat)
            outputPath=pathToCalibrationImages + '/UndistortedUsingFisheye/' + fileName
            tester.infoMessage('Writing undistorted image to ' + outputPath)
            cv2.imwrite(outputPath,undist_img)
    tester.infoMessage('Camera Calibration Done')

def useImageAsSample(tester,filename):
    index= filename.find('Image-(' + tester.lensType + ',' + str(tester.cameraHeightLowRes) + ' x ' + str(tester.cameraWidthLowRes) + ')')
    if index>-1:
        index=filename.find('.jpg')
        if index>-1:
            return True
        else:
            return False
    else:
        return False
                             
def generateCameraCalibrationModel(tester):
    pathToCamerasCalibrationFolder=tester.basePath+'Calibrate'
    samplePath=pathToCamerasCalibrationFolder + '/Samples'
    try:
        tempDir1=pathToCamerasCalibrationFolder + '/TempSampleStorage1'
        os.mkdir(tempDir1)
    except:
        listOfTempFiles=os.listdir(tempDir1)
        for fileN in listOfTempFiles:
            os.remove(tempDir1 + '/' + fileN)
    try:
        tempDir2=pathToCamerasCalibrationFolder + '/TempSampleStorage2'
        os.mkdir(tempDir2)
    except:
        listOfTempFiles=os.listdir(tempDir2)
        for fileN in listOfTempFiles:
            os.remove(tempDir2 + '/' + fileN)
    try:
        discardPath=pathToCamerasCalibrationFolder + '/DiscardedFisheyeSamples'
        os.mkdir(discardPath)
    except:
        pass
    pass
    pathToCalibrationImages=pathToCamerasCalibrationFolder + '/Samples'
    imgList = sorted(os.listdir(pathToCalibrationImages))
    potentialSampleList=[]
    for fileN in imgList:
        if useImageAsSample(tester,fileN):
            potentialSampleList.append(fileN)
        for fileN in potentialSampleList:
            shutil.move(samplePath + '/' + fileN, tempDir1 + '/' + fileN)
        for fileN in potentialSampleList:
            shutil.move(tempDir1 + '/' + fileN, samplePath + '/' + fileN)
            try:
                tester.infoMessage('Checking sample: ' + fileN)
                checkerboardImageFisheyeCalibration(tester,pathToCamerasCalibrationFolder)
                tester.infoMessage('Sample: ' + fileN + ' kept')
            except:
                traceback.print_exc()  
                tester.infoMessage('Sample: ' + fileN + ' discarded')
                shutil.move(samplePath + '/' + fileN, discardPath + '/' + fileN)
    keptSampleList=sorted(os.listdir(tempDir2))
    for fileN in keptSampleList:
        shutil.move(tempDir2 + '/' + fileN, samplePath + '/' + fileN)
    shutil.rmtree(tempDir1)
    shutil.rmtree(tempDir2)
    tester.infoMessage('Samples checked and bad samples placed in DiscardedFisheyeSamples directory')
        
    
def recordTesterData():
    lastWakeupTime=datetime.datetime.now()
    normalInterval=datetime.timedelta(seconds=tester.normalRecordIntervalInSecs)
    nextNormalWakeupTime=lastWakeupTime+normalInterval
    while True:
        lastWakeupTime=sleepUntilNextInterval(lastWakeupTime,tester.expeditedRecordIntervalInSecs)
        if datetime.datetime.now()>nextNormalWakeupTime:
            nextNormalWakeupTime=nextNormalWakeupTime+normalInterval
            try:
                tester.writeTimesliceToDB()
            except:
                tester.debugLog.exception("Continuing...")
        elif tester.currentRecordingModeIsExpedited:
            try:
                tester.writeTimesliceToDB()
            except:
                tester.debugLog.exception("Continuing...")
                                
def triggertester():
    time.sleep(100)
    
def queuePlungerMove(tester,distanceToMove,speed=None):
    moveQueued=False
    count=0
    while not moveQueued:
        tester.movePlungerLock.acquire()
        if tester.distanceToMovePlunger is None:
            tester.speedToMovePlunger=speed
#            print('Queuer: Inserting ' + str(distanceToMove))
            tester.distanceToMovePlunger=distanceToMove
            tester.movePlungerLock.notify()
            tester.movePlungerLock.release()
            moveQueued=True
        else:
            tester.movePlungerLock.notify()
            tester.movePlungerLock.release()
            time.sleep(.5)
            print(count)
    return True

def markPlungerAsClosed(tester):
    return queuePlungerMove(tester,tester.SET_HOME_POSITION)
    
def tightenPlungerPastClosedPosition(tester):
    return queuePlungerMove(tester,tester.TIGHTEN_PAST_HOME_POSITION)
    
def movePlungerProcess():
    tester.plungerMoving=False
    tester.distanceToMovePlunger=None
    while True:
        tester.movePlungerLock.acquire()
        plungerMoveDistance=tester.distanceToMovePlunger
        plungerMoveSpeed=tester.speedToMovePlunger
        while plungerMoveDistance is None:
            tester.movePlungerLock.wait(1)
            plungerMoveDistance=tester.distanceToMovePlunger
            plungerMoveSpeed=tester.speedToMovePlunger
        tester.plungerMoving=True
        time.sleep(.1)
#            print('Dequeuer - move plunger: ' + str(plungerMoveDistance))
        tester.movePlunger(plungerMoveDistance,speed=plungerMoveSpeed)
        tester.plungerMoving=False
        tester.distanceToMovePlunger=None
        tester.movePlungerLock.release()
        
def waitUntilPlungerStopsMoving(tester):
    while tester.plungerMoving or tester.plungerStepping:
#        print('Waiting: carouselMoveQueued: ' + str(tester.carouselMoveQueued) + ', carouselStepping: ' + str(tester.carouselStepping))
        time.sleep(.5)

def queueCarouselMove(tester,distanceToMove):
    if not distanceToMove==tester.SET_HOME_POSITION:
        if tester.plungerState==tester.PLUNGER_FULLY_CLOSED or tester.plungerState==tester.PLUNGER_MOSTLY_CLOSED:
            return False   #carousel obstructed
    moveQueued=False
    while not moveQueued:
        tester.moveCarouselLock.acquire()
        if tester.distanceToMoveCarousel is None:
            tester.distanceToMoveCarousel=distanceToMove
            tester.moveCarouselLock.notify()
            tester.moveCarouselLock.release()
            moveQueued=True
        else:
            tester.moveCarouselLock.notify()
            tester.moveCarouselLock.release()
            time.sleep(1)
    
def markCarouselAsAtOrigin(tester):
    return queueCarouselMove(tester,tester.SET_HOME_POSITION)

def waitUntilCarouselStopsMoving(tester):
    while tester.carouselMoveQueued or tester.carouselStepping:
#        print('Waiting: carouselMoveQueued: ' + str(tester.carouselMoveQueued) + ', carouselStepping: ' + str(tester.carouselStepping))
        time.sleep(.5)

def moveCarouselProcess():
    tester.carouselMoveQueued=False
    tester.distanceToMoveCarousel=None
    while True:
        tester.moveCarouselLock.acquire()
        tester.moveCarouselLock.wait()
        carouselMoveDistance=tester.distanceToMoveCarousel
        if carouselMoveDistance is None:
            tester.carouselMoveQueued=False
        else:
            tester.carouselMoveQueued=True
            tester.moveCarousel(carouselMoveDistance)
        tester.distanceToMoveCarousel=None
        tester.carouselMoveQueued=False
        tester.moveCarouselLock.release()
        
def findImageShift(tester,carouselFeature,latestFullImage,maxShift):
    shiftValues=[]
    minImageDiff=100000000000
    for shiftIndex in range(maxShift):
        shiftedImage=carouselFeature.clipImage(tester,latestFullImage,rowOffset=-shiftIndex)
        diff=cv2.absdiff(shiftedImage,carouselFeature.referenceClip)
        diffSum=np.sum(diff)
        if diffSum<minImageDiff:
            minShift=shiftIndex
            minImageDiff=diffSum
        shiftValues.append(diffSum)
    return minShift
        
def liftPlungerASmallBit(tester,distance=.2,firstCall=False):
    carouselFeature=tester.featureList["Carousel"]
    if firstCall:
        tester.videoLowResCaptureLock.acquire()
        tester.videoLowResCaptureLock.wait()
        carouselFeature.referenceClip=carouselFeature.clipImage(tester,tester.latestLowResImage)
        tester.videoLowResCaptureLock.release()
    queuePlungerMove(tester,distance)
    waitUntilPlungerStopsMoving(tester)
    tester.videoLowResCaptureLock.acquire()
    tester.videoLowResCaptureLock.wait()
    latestFullImage=tester.latestLowResImage.copy()
    tester.videoLowResCaptureLock.release()
    bestShiftMatch=findImageShift(tester,carouselFeature,latestFullImage,3)
    return bestShiftMatch

def determineStopperClosureValue(tester):
    rightStopperFeature=tester.featureList["RightStopper"]
    tester.videoLowResCaptureLock.acquire()
    tester.videoLowResCaptureLock.wait()
    rightStopperImage=rightStopperFeature.clipImage(tester,tester.latestLowResImage)
    tester.videoLowResCaptureLock.release()
    verticalsFound=testDlibForVerticalPosition(rightStopperFeature,rightStopperImage)
    highestStopper=99999
    for vertical in verticalsFound:
        if vertical<highestStopper:
            highestStopper=vertical
    return highestStopper

def testPlungerPosition(tester,useVisualOnly=False):
    if not useVisualOnly:
        if tester.plungerState==tester.PLUNGER_FULLY_CLOSED:
            return 'Closed'
        elif tester.plungerState==tester.PLUNGER_MIOSTLY_CLOSED:
            return 'Closed'
        if not tester.plungerState==tester.PLUNGER_UNKNOWN:
            return 'Open'
    if tester.valueForStopperWhenClosed is None:
        return 'Unknown'
    currentStopperClosureValue=determineStopperClosureValue(tester)
    if currentStopperClosureValue<=tester.valueForStopperWhenClosed:
        print('Closed')
        return 'Closed'
    else:
        print('Open')
        return 'Open'
    
def setPlungerToClosed(tester,runAsDiagnostic=False,ignorePlungerStatus=False,blockUntilDone=True): 
    if tester.plungerState==tester.PLUNGER_FULLY_CLOSED and not ignorePlungerStatus:
        return True
    if tester.plungerState==tester.PLUNGER_MOSTLY_CLOSED or tester.plungerState==tester.PLUNGER_UNKNOWN or ignorePlungerStatus:    
        queuePlungerMove(tester,-tester.mmToRaiseFromOpenToFullyClosed-1)  #lower 5 mm from raised position
        time.sleep(1)
        waitUntilPlungerStopsMoving(tester)
    ascentStep=0
    increment=.2
    maxAscentSteps=int(tester.maxPlungerDepthNoAgitator/increment)
    currentShift=0
    initialLift=True
    while ascentStep<maxAscentSteps and currentShift<1:
        currentShift=liftPlungerASmallBit(tester,distance=increment,firstCall=initialLift)
        initialLift=False
        ascentStep+=1
    if ascentStep<maxAscentSteps:
        if tester.stopperTighteningInMM>0:
            tightenPlungerPastClosedPosition(tester)
        if runAsDiagnostic:
            tester.debugLog.info('Plunger Position Set to Closed')
        markPlungerAsClosed(tester)
        if blockUntilDone:
            secondsElapsed=0
            while secondsElapsed<tester.MAX_WAIT_FOR_CLOSURE:
                if tester.plungerState==tester.PLUNGER_FULLY_CLOSED:
                    return True
                time.sleep(1)
                secondsElapsed+=1
            tester.debugLog.info('Close timeout expired without reaching Closed State')
            return False
        else:        
            return True
    else:
        tester.debugLog.info('Unable to Detect Plunger Closure.  Plunger May be Stuck')
        return False
        
def setPlungerPosition(tester,desiredPosition=None,runAsDiagnostic=False):
    try:
        if desiredPosition==tester.PLUNGER_FULLY_CLOSED:
            setPlungerToClosed(tester,runAsDiagnostic=runAsDiagnostic)
            tester.debugLog.info('Plunger Position Set to Closed')
            return True
        elif desiredPosition==tester.PLUNGER_OPEN:
            if tester.plungerState==tester.PLUNGER_OPEN or tester.plungerState==tester.PLUNGER_PAST_OPEN:
                tester.debugLog.info('Plunger Already Open')
                return True
            setPlungerToClosed(tester,runAsDiagnostic=runAsDiagnostic)
            queuePlungerMove(tester,-tester.mmToRaiseFromOpenToFullyClosed-1)  #lower 6 mm from raised position
            tester.debugLog.info('Plunger Position Set to Open')
            return True
        else:
            if runAsDiagnostic:
                tester.debugLog.info('Desired position must be either open or closed')
            return False
    except:
        if runAsDiagnostic:
            tester.debugLog.info("Plunger Seating Failure")
        tester.debugLog.exception("Plunger Seating Failure")
        return False

def setPlungerToOpen(tester,runAsDiagnostic=False,blockUntilDone=True):
    result=setPlungerPosition(tester,desiredPosition=tester.PLUNGER_OPEN,runAsDiagnostic=runAsDiagnostic)    
    if result:
        if blockUntilDone:
            secondsElapsed=0
            while secondsElapsed<tester.MAX_WAIT_FOR_OPENING:
                if tester.plungerState==tester.PLUNGER_OPEN or tester.plungerState==tester.PLUNGER_PAST_OPEN:
                    return True
                time.sleep(1)
                secondsElapsed+=1
            tester.debugLog.info('Open timeout expired without reaching Open State. Final State was: ' + str(tester.plungerState))
            return False
        else:        
            return True
        
    else:
        return False
    
def liftPlungerUntilExactlyOpen(tester,blockUntilDone=True):
    if tester.plungerState==tester.PLUNGER_OPEN:
        return True
    if tester.plungerState==tester.PLUNGER_FULLY_CLOSED or tester.plungerState==tester.PLUNGER_MOSTLY_CLOSED or tester.plungerState==tester.PLUNGER_UNKNOWN:
        return setPlungerToOpen(tester,blockUntilDone=blockUntilDone)
    if tester.plungerState==tester.PLUNGER_PAST_OPEN:
        currentPlungerMM=tester.plungerSteps/tester.plungerStepsPerMM
        mmToLift=-tester.mmToRaiseFromOpenToFullyClosed-currentPlungerMM
        queuePlungerMove(tester,mmToLift-.5)   #Subtract a smidge so it doesn't show up as past close
        if blockUntilDone:
            secondsElapsed=0
            while secondsElapsed<tester.MAX_WAIT_FOR_CLOSURE:
                if tester.plungerState==tester.PLUNGER_OPEN:
                    return True
                time.sleep(1)
                secondsElapsed+=1
            tester.debugLog.info('Close timeout expired with lifting to open state')
            return False
        else:        
            return True
                   
        
    else:
        tester.debugLog.info('Unknown Plunger State: ' + str(tester.plungerStat))
        return False
        
    
def testReagentPosition(tester,precise=False):
    waitUntilCarouselStopsMoving(tester)
    if precise:
        featureToUse=tester.featureList["PreciseCenter"]
    else:        
        featureToUse=tester.featureList["ApproxCenter"]
    tester.videoLowResCaptureLock.acquire()
    tester.videoLowResCaptureLock.wait()
    currentFeature=featureToUse.clipImage(tester,tester.latestLowResImage)
    tester.videoLowResCaptureLock.release()
    resultList=testDlibForHorizontalPosition(featureToUse,currentFeature)
    if len(resultList)==0:
        return None
    elif len(resultList)==1:
        return resultList[0]
    else:
        minResult=resultList[0]
        for result in resultList:
            if abs(result)<abs(minResult):
                minResult=result
        return minResult
    
        
def centerReagent(tester,precise=False):
    maxSteps=50
    currStep=0
    minAlignmentRough=1
    minAlignmentPrecise=.5
    bePrecise=False
    previousBePrecise=bePrecise
    while currStep<maxSteps:
        currOffset=testReagentPosition(tester,precise=bePrecise)
        previousBePrecise=bePrecise
        if currOffset is None:  #Didn't find a reagent, so just move a bit and check again
#            print('Step: ' + str(currStep) + ', Precise1: ' + str(bePrecise) + ' - Queue: ' + str(1))
            queueCarouselMove(tester,1/360)
            bePrecise=False
            time.sleep(1) 
        elif abs(currOffset)>minAlignmentRough:
#            print('Step: ' + str(currStep) + ', Precise2: ' + str(bePrecise) + ' - Queue: ' + str(currOffset))
            queueCarouselMove(tester,currOffset/360) 
            bePrecise=False
            time.sleep(1)
        else:
            if not precise:
                return True
            else:
                if abs(currOffset)<=minAlignmentPrecise and previousBePrecise:
                    return True
                else:
                    distToMove=currOffset/(360*4)
                    if abs(distToMove<minAlignmentPrecise):
                        return True
#                    print('Step: ' + str(currStep) + ', Precise3: ' + str(bePrecise) + ' - Queue: ' + str(currOffset/(360*4)))
                    queueCarouselMove(tester,currOffset/(360*4))
                    previousBePrecise= bePrecise
                    time.sleep(1)
                    bePrecise=True
        currStep+=1
    return False        
     
def testLeftLetter(tester):
    tester.videoLowResCaptureLock.acquire()
    tester.videoLowResCaptureLock.wait()
    leftLetterClipping=tester.featureList["LeftLetter"]
    clippedImageToTest=leftLetterClipping.clipImage(tester,tester.latestLowResImage)
    tester.videoLowResCaptureLock.release()
    foundLetter=testFeature(tester,leftLetterClipping,clippedImageToTest)
    print('Found Left Letter: ' + foundLetter)
    return foundLetter
  
def testRightLetter(tester):
    tester.videoLowResCaptureLock.acquire()
    tester.videoLowResCaptureLock.wait()
    rightLetterFeature=tester.featureList["RightLetter"]
    clippedImageToTest=rightLetterFeature.clipImage(tester,tester.latestLowResImage)
    tester.videoLowResCaptureLock.release()
    foundLetter=testFeature(tester,rightLetterFeature,clippedImageToTest)  
    print('Found Right Letter: ' + foundLetter)
    return foundLetter
    
def getReagentPosition(tester,precise=False):
    repositionList=[-.8/360,+1.6/360,-2.4/360]
    maxTries=3
    tries=0
    while tries<maxTries:
        try:
            if centerReagent(tester,precise):
                leftLetter=testLeftLetter(tester)
                rightLetter=testRightLetter(tester)
                if letterSequenceCheck[leftLetter]==rightLetter:
                    tester.carouselCurrentSymbol=leftLetter
                    return True,leftLetter
        except:
            tester.debugLog.exception('Failure in getting reagent position, retrying...')
        queueCarouselMove(tester,repositionList[tries])
        time.sleep(1)
        tries+=1
    tester.carouselCurrentSymbol=None
    return False,None

def rotateToPosition(tester,targetPosition,precise=False,runAsDiagnostic=False):
    unknownPositionRotate=[-30,30,-60,60,-120,120]
    unknownPositionCount=0
    notMovingPositionRotate=[30,-30,60,-60,120,-120]
    notMovingPositionCount=0
    previousPosition=None
    retryMax=6
    retries=0
    while retries<retryMax: 
        msg='Retry: ' + str(retries) + ' to rotate to position ' + targetPosition    
        if runAsDiagnostic:
            tester.debugLog.info(msg)
        result,newPosition=rotateToPositionSingle(tester,targetPosition,precision=precise,runAsDiagnostic=runAsDiagnostic)
        if result:
            msg='Correctly ended up at target position ' + targetPosition
            if runAsDiagnostic:
                tester.debugLog.info(msg)
            return True
        else:
            if newPosition is None:
                queueCarouselMove(tester,unknownPositionRotate[unknownPositionCount]/360)
                msg='Position could not be determined, so rotating ' + str(unknownPositionRotate[unknownPositionCount]) + ' degrees'
                if runAsDiagnostic:
                    tester.debugLog.info(msg)
                unknownPositionCount+=1
            else:
                if newPosition==previousPosition:
                    queueCarouselMove(tester,notMovingPositionRotate[notMovingPositionCount]/360)
                    msg='Ended up at ' + newPosition + ' again, so rotating ' + str(notMovingPositionRotate[notMovingPositionCount]) + ' degrees'
                    if runAsDiagnostic:
                        tester.debugLog.info(msg)
                    notMovingPositionCount+=1
                else:
                    previousPosition=newPosition
        msg='Retrying rotation to target position'
        if runAsDiagnostic:
            tester.debugLog.info(msg)
        retries+=1
    return False
            
def rotateToPositionSingle(tester,targetPosition,precision,overshoot=1.0,runAsDiagnostic=False):
    if tester.plungerState==tester.PLUNGER_FULLY_CLOSED or tester.plungerState==tester.PLUNGER_MOSTLY_CLOSED:
        msg='Aborting rotate because plunger not open'
        if runAsDiagnostic:
            tester.debugLog.info(msg)
        return False,None
    if tester.carouselCurrentSymbol==None:
        result,currPos=getReagentPosition(tester,precision)
        if not result:
            msg='Cannot determine current carousel location'
            if runAsDiagnostic:
                tester.debugLog.info(msg)
            return False,None
    else:
        currPos=tester.carouselCurrentSymbol
    if currPos==targetPosition:
        return True,targetPosition
    else:
        try:
            degreesToRotate=degreesToMove[currPos+targetPosition]
            msg='Degrees to rotate: ' + str(degreesToRotate)
            if runAsDiagnostic:
                tester.debugLog.info(msg)
            queueCarouselMove(tester,degreesToRotate*overshoot/360)
            time.sleep(1)
            result,newCurrPosition=getReagentPosition(tester,precision)
            if result:
                if newCurrPosition==targetPosition:
                    return True,targetPosition
                else:
                    msg='Unexpectedly ended up at: ' + newCurrPosition + ' instead of: ' + targetPosition
                    if runAsDiagnostic:
                        tester.debugLog.info(msg)
                    return False,newCurrPosition
            else:  #Could not determine current position
                msg='Could not determine current position'
                if runAsDiagnostic:
                    tester.debugLog.info(msg)
                return False,None
        except:
            msg="Could not rotate to new position"
            if runAsDiagnostic:
                tester.debugLog.info(msg)
            tester.debugLog.exception(msg)
            return False,None
        

def testDrip(tester):
    motionChangeThresholdTop=10
    featureToUseTop=tester.featureList["DripTop"]
    tester.videoLowResCaptureLock.acquire()
    tester.videoLowResCaptureLock.wait()
    latestImageTop=featureToUseTop.clipImage(tester,tester.latestLowResImage)
    tester.videoLowResCaptureLock.release()
    if tester.previousDripTopImage is None:
        cntTop=0
    else:
        diffImage=cv2.absdiff(latestImageTop,tester.previousDripTopImage)
        topDiff=np.sum(diffImage)
        greyDiff=cv2.cvtColor(diffImage,cv2.COLOR_BGR2GRAY)
        ret,mask=cv2.threshold(greyDiff,motionChangeThresholdTop,1,cv2.THRESH_BINARY)
        cntTop=np.sum(mask)
    tester.previousDripTopImage=latestImageTop
    bwImage=cv2.cvtColor(latestImageTop,cv2.COLOR_BGR2GRAY)
    ret1,th1 = cv2.threshold(bwImage,130,255,cv2.THRESH_BINARY_INV)
    kernel = np.ones((3,3),np.uint8)
    th2=cv2.erode(th1,kernel,iterations=1)
    (xList,yList)=np.nonzero(th2)
    try:
        lowestPoint=max(xList)
    except:
        lowestPoint=0
#    print('Lowest: ' + str(lowestPoint) + ', Size: ' + str(cntTop))
    return lowestPoint,cntTop

def computeDripsFromLowestPoint(tester,newValue,sizeDelta=None):
    dripHeightThreshold=5
    sizeDeltaThreshold=10
    initialSamplesToIgnore=10
    if tester.previousDripHeight is None:
        tester.previousDripHeight=newValue
        tester.samplesSinceLastDrop=0
        tester.dripSampleCount=0
        return False
    else:
        tester.dripSampleCount+=1
        if newValue-tester.previousDripHeight<=-dripHeightThreshold and tester.samplesSinceLastDrop>=tester.dripMinGap and tester.dripSampleCount>initialSamplesToIgnore:
            tester.previousDripHeight=newValue
            tester.samplesSinceLastDrop=0
            if sizeDelta is None:
                return True
            elif sizeDelta>=sizeDeltaThreshold:
                return True
            else:
                return False
        else:
            tester.previousDripHeight=newValue
            tester.samplesSinceLastDrop+=1
            return False

def resetDripHistory(tester):
    tester.previousDripHeight=None
    tester.suppressProcessing=False
    tester.plungerSlow=False
    tester.plungerAbort=False
    tester.dripSamplesSoFar=0
    tester.samplesSinceLastDrop=0
    tester.dripSampleCount=0
    tester.dripTopList=[]
    tester.previousDripTopImage=None
    
def saveTopDripList(tester):
    fn="/home/pi/Images/DripTop/DT-" + datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S") + '-'
#    print('Saving Top Drip images')
    index=0
    for image in tester.dripTopList:
        saveFN=fn+str(index).zfill(4) + '.jpg'
        cv2.imwrite(saveFN,image)
        index+=1
    tester.dripTopList=[]

def getMaxPlungerDepth(reagent):
    try:
        rg=tester.reagentList[reagent]
        if rg.hasAgitator:
            plungerMaxDepth=-tester.plungerStepsPerMM*tester.maxPlungerDepthAgitator
        else:
            plungerMaxDepth=-tester.plungerStepsPerMM*tester.maxPlungerDepthNoAgitator
    except:
        tester.debugLog.exception("Trying to get max depth")        
        plungerMaxDepth=-tester.plungerStepsPerMM*tester.maxPlungerDepthAgitator
    stepsUntilMaxDepth=plungerMaxDepth-tester.plungerSteps
    mmUntilMaxDepth=stepsUntilMaxDepth/tester.plungerStepsPerMM  
    return plungerMaxDepth,mmUntilMaxDepth          
        
def dispenseDrops(tester,numDrops,waitUntilPlungerRaised=True,reagent=None,runAsDiagnostic=False):
    plungerSlowDownThreshold=20
    initialSamplesToDiscard=10
    log=""
    if numDrops<=0:
        return True
    try:
        if tester.plungerSteps==None:
            if runAsDiagnostic:
                tester.debugLog.info('Plunger position must be initialized before dispensing Drops')
            return False
        resetDripHistory(tester)        #This assumes the reagent is in the front position
        originalDistortion=tester.undistortImage
        tester.undistortImage=False
        tester.suppressProcessing=True  #Turn off unecessary processing while in operation
        plungerMaxDepth,mmUntilMaxDepth=getMaxPlungerDepth(reagent)
#        print(mmUntilMaxDepth)
        if runAsDiagnostic:
            tester.debugLog.info('Starting to lower the plunger')
        queuePlungerMove(tester,mmUntilMaxDepth,speed=tester.PLUNGER_HIGH_SPEED)
        currentSpeedIsHigh=True
        dropCount=0
        sampleCount=0
        collectSamples=False
        collectedSampleIndex=0
        while tester.plungerSteps>plungerMaxDepth and dropCount<numDrops:
            dripTopValue,sizeChange=testDrip(tester)
            dropDetected=computeDripsFromLowestPoint(tester,dripTopValue,sizeDelta=sizeChange)
            if dropDetected:
                dropCount+=1
            if sizeChange>plungerSlowDownThreshold and currentSpeedIsHigh and sampleCount>initialSamplesToDiscard:
                tester.plungerSlow=True
                currentSpeedIsHigh=False 
                collectSamples=True
                log=""
            if collectSamples:
                log+=str(collectedSampleIndex) + ',' + str(dripTopValue) + '\n'
            sampleCount+=1
        tester.plungerAbort=True
        time.sleep(1)
        tester.plungerAbort=False
        tester.plungerSlow=False
        tester.suppressProcessing=False
        tester.undistortImage=originalDistortion
        if runAsDiagnostic:
            tester.debugLog.info('Processing reactivated')
        if dropCount>=numDrops:
            tester.debugLog.info(str(dropCount) + ' Dispensed')
            if not reagent is None:
                tester.saveReagentPosition(reagent)
        else:
            tester.debugLog.info('Plunger Hit Max Depth before drops dispensed')
            if not reagent is None:
                tester.saveReagentPosition(reagent)
            tester.debugLog.info('Lifting plunger back up')
            liftPlungerUntilExactlyOpen(tester,blockUntilDone=waitUntilPlungerRaised)
            return False
        if runAsDiagnostic:
            tester.debugLog.info('Lifting plunger back up')
        liftPlungerUntilExactlyOpen(tester,blockUntilDone=waitUntilPlungerRaised)
        if runAsDiagnostic:
            tester.debugLog.info('Drip Dispensing Done')
        tester.infoMessage('Drip Dispensing Done')
        return True
    except:
        tester.plungerAbort=False
        tester.plungerSlow=False
        tester.suppressProcessing=False
        tester.undistortImage=originalDistortion
        if runAsDiagnostic:
            tester.debugLog.info("Failure Counting Drops")
        tester.debugLog.exception("Failure Counting Drops")        
    return False

def dispenseFirstDrop(tester,reagent=None,runAsDiagnostic=False):
    print('Dispensing first drop')
    plungerSlowDownThreshold=20
    initialSamplesToDiscard=10
    log=""
    try:
        if tester.plungerSteps==None:
            if runAsDiagnostic:
                tester.debugLog.info('Plunger position must be initialized before dispensing Drops')
            return False
        resetDripHistory(tester)        #This assumes the reagent is in the front position
        tester.suppressProcessing=True  #Turn off unecessary processing while in operation
        plungerMaxDepth,mmUntilMaxDepth=getMaxPlungerDepth(reagent)
#        print(mmUntilMaxDepth)
        if runAsDiagnostic:
            tester.debugLog.info('Starting to lower the plunger')
        queuePlungerMove(tester,mmUntilMaxDepth,speed=tester.PLUNGER_HIGH_SPEED)
        currentSpeedIsHigh=True
        sampleCount=0
        collectSamples=False
        collectedSampleIndex=0
        firstDropDispensed=False
        while tester.plungerSteps>plungerMaxDepth:
            dripTopValue,sizeChange=testDrip(tester)
            dropDetected=computeDripsFromLowestPoint(tester,dripTopValue,sizeDelta=sizeChange)
            if dropDetected:
                firstDropDispensed=True
                break
            if sizeChange>plungerSlowDownThreshold and currentSpeedIsHigh and sampleCount>initialSamplesToDiscard:
                tester.plungerSlow=True
                currentSpeedIsHigh=False 
                collectSamples=True
                log=""
            if collectSamples:
                log+=str(collectedSampleIndex) + ',' + str(dripTopValue) + '\n'
            sampleCount+=1
        tester.plungerPause=True
        tester.suppressProcessing=False
        if runAsDiagnostic:
            tester.debugLog.info('Processing reactivated')
        if firstDropDispensed:
            tester.debugLog.info('First drop dispensed')
            return True
        else:
            tester.debugLog.info('Plunger Hit Max Depth before first drop dispensed')
            return False
    except:
        if runAsDiagnostic:
            tester.debugLog.info("Failure Dispensing")
        tester.debugLog.exception("Failure Dispensing")        
        return False

def dispenseAnotherDrop(tester,reagent=None,runAsDiagnostic=False):
    print('Dispensing next drop')
    time.sleep(.5)
    initialSamplesToDiscard=10
    log=""
    try:
        if tester.plungerSteps==None:
            if runAsDiagnostic:
                tester.debugLog.info('Plunger position must be initialized before dispensing Drops')
            return False
        resetDripHistory(tester)        #This assumes the reagent is in the front position
        tester.suppressProcessing=True  #Turn off unecessary processing while in operation
#        print(mmUntilMaxDepth)
        tester.plungerSlow=True
        tester.plungerPause=True        
        sampleCount=0
        collectSamples=False
        collectedSampleIndex=0
        dropDispensed=False
        sampleDiscardCount=0
        plungerMaxDepth,mmUntilMaxDepth=getMaxPlungerDepth(reagent)
        while tester.plungerSteps>plungerMaxDepth:
            if sampleDiscardCount>initialSamplesToDiscard:
                tester.plungerPause=False
            sampleDiscardCount+=1
            dripTopValue,sizeChange=testDrip(tester)
            dropDetected=computeDripsFromLowestPoint(tester,dripTopValue,sizeDelta=sizeChange)
            if dropDetected:
                dropDispensed=True
                break
        tester.plungerPause=True
        tester.suppressProcessing=False
        if runAsDiagnostic:
            tester.debugLog.info('Processing reactivated')
        if dropDispensed:
            tester.debugLog.info('Next drop dispensed')
            return True
        else:
            tester.debugLog.info('Plunger Hit Max Depth before next drop dispensed')
            return False
    except:
        if runAsDiagnostic:
            tester.debugLog.info("Failure Dispensing")
        tester.debugLog.exception("Failure Dispensing")        
        return False

def testRotation(tester,numOfDestinations):
    testNum=0
    successCount=0
    failureCount=0
    setPlungerToOpen(tester,runAsDiagnostic=True)
    waitUntilPlungerStopsMoving(tester)
    time.sleep(10)
    while testNum<numOfDestinations:
        randomDest=random.randint(0,11)
        dest=destinationLetters[randomDest]
        tester.debugLog.info('Going to Destination # ' + str(testNum) + ': ' + dest)
        result=rotateToPosition(tester,dest,runAsDiagnostic=True)
        if result:
            tester.debugLog.info('Cycle completion: Success')
            successCount+=1
        else:
            tester.debugLog.info('Cycle completion: Failed')
            failureCount+=1
        testNum+=1
    tester.debugLog.info('All test cycles completed. Success: ' + str(successCount) + ', Failures: ' + str(failureCount))
            
def testPlunger(tester,numCycles):
    testNum=0
    successCount=0
    failureCount=0
    while testNum<numCycles:
        waitUntilPlungerStopsMoving(tester)
        result=setPlungerToOpen(tester,runAsDiagnostic=True)
        if result:
            time.sleep(3)
            waitUntilPlungerStopsMoving(tester)
            result=setPlungerToClosed(tester,runAsDiagnostic=True)
            if result:
                tester.debugLog.info('Cycle completion: Success')
                successCount+=1
            else:
                tester.debugLog.info('Cycle completion: Failed')
                failureCount+=1
        else:
            failureCount+=1
        testNum+=1
    tester.debugLog.info('All test cycles completed. Success: ' + str(successCount) + ', Failures: ' + str(failureCount))            
        
def testSlotADrops(tester):
    result=setPlungerToClosed(tester,runAsDiagnostic=True)
    if result:
        result=setPlungerToOpen(tester,runAsDiagnostic=True)
        if result:
            result=rotateToPosition(tester,'A',precise=False,runAsDiagnostic=True)
            if result:
                randomDrops=random.randint(1,6)
                result=dispenseDrops(tester,randomDrops,waitUntilPlungerRaised=True,reagent='A',runAsDiagnostic=True)    
                if result:
                    return True
                else:
                    return False
            else:
                return False
        else:
            return False
    else:
        return False            

def testDispensing(tester,numCycles):
    testNum=0
    successCount=0
    failureCount=0
    while testNum<numCycles:
        result=testSlotADrops(tester)
        if result:
            tester.debugLog.info('Cycle completion: Success')
            successCount+=1
        else:
            tester.debugLog.info('Cycle completion: Failed')
            failureCount+=1
        testNum+=1
    tester.debugLog.info('All test cycles completed. Success: ' + str(successCount) + ', Failures: ' + str(failureCount))            
        
def testFillingMixer(tester):
    randomLevel=random.randint(4,10)
    tester.debugLog.info('Test filling mixer to level: ' + str(randomLevel))
    result=fillMixingCylinder(tester,vol=randomLevel,runAsDiagnostic=True)
    return result

def testMixerFill(tester,numCycles):
    testNum=0
    successCount=0
    failureCount=0
    while testNum<numCycles:
        result=testFillingMixer(tester)
        if result:
            tester.debugLog.info('Cycle completion: Success')
            successCount+=1
        else:
            tester.debugLog.info('Cycle completion: Failed')
            failureCount+=1
        testNum+=1
    tester.openMixerValve()
    tester.debugLog.info('All test cycles completed. Success: ' + str(successCount) + ', Failures: ' + str(failureCount))            
        
def seriesCapture():
    while True:
        angle=0
        tester.seriesRunning=False
        tester.carouselSeriesLock.acquire()
        tester.carouselSeriesLock.wait()
        tester.seriesRunning=True
        feat=tester.currentFeature
        tester.infoMessage('Starting Series Sample Generation for Feature: ' + feat.featureName)
        featureImageDirectory=tester.basePath + 'Images/' + feat.featureName
        if not os.path.isdir(featureImageDirectory):
            os.mkdir(featureImageDirectory)
        if feat is None:
            tester.carouselSeriesLock.release()
        elif feat.featureName=="ApproxCenter" or feat.featureName=="PreciseCenter":
            stepAngle=1.3
            while angle<360:
                if tester.jiggleRepetitionPhotos>0:
                    jigglePhotoCount=0
                    tester.jigglePhoto=True
                    while jigglePhotoCount<tester.jiggleRepetitionPhotos:
                        feat.snapPhoto(tester)
                        time.sleep(1)
                        jigglePhotoCount+=1
                    tester.jigglePhoto=False
                else:
                    feat.snapPhoto(tester)
                print('Carousel at angle: ' + str(angle))
                queueCarouselMove(tester,stepAngle/360)
                time.sleep(1)
                angle+=stepAngle
            tester.carouselSeriesLock.release()
        elif feat.featureName=="LeftLetter" or feat.featureName=="RightLetter" or feat.featureName=="ReagentLevel":
            stepAngle=30
            centerReagent(tester)
            while angle<360:
                if tester.jiggleRepetitionPhotos>0:
                    jigglePhotoCount=0
                    tester.jigglePhoto=True
                    while jigglePhotoCount<tester.jiggleRepetitionPhotos:
                        feat.snapPhoto(tester)
                        time.sleep(1)
                        jigglePhotoCount+=1
                    tester.jigglePhoto=False
                else:
                    feat.snapPhoto(tester)
                queueCarouselMove(tester,stepAngle/360)
                print('Carousel at angle: ' + str(angle))
                time.sleep(2)
                centerReagent(tester)
                time.sleep(1)
                angle+=stepAngle
            tester.carouselSeriesLock.release()
        elif feat.featureName=="DripTop":
            dripStrokeLength=25
            plungerIncrement=.1
            currentStrokePosition=0
            while currentStrokePosition<dripStrokeLength:
                if tester.jiggleRepetitionPhotos>0:
                    jigglePhotoCount=0
                    tester.jigglePhoto=True
                    while jigglePhotoCount<tester.jiggleRepetitionPhotos:
                        feat.snapPhoto(tester)
                        time.sleep(1)
                        jigglePhotoCount+=1 
                    tester.jigglePhoto=False
                else:
                    feat.snapPhoto(tester)
                print('Plunger at increment: ' + str(-currentStrokePosition))
                queuePlungerMove(tester,-plungerIncrement)
                time.sleep(1)
                currentStrokePosition+=plungerIncrement
            tester.carouselSeriesLock.release()
        elif feat.featureName=="LeftStopper" or feat.featureName=="RightStopper":
            upDownCycleCount=10
            minDepth=2
            maxDepth=-10
            cycleCount=0
            increment=.2
            while cycleCount<upDownCycleCount:
                print('Iteration: ' + str(cycleCount+1))
                currentPlungerLevel=0 
                while currentPlungerLevel> maxDepth:              
                    print('Descending - Depth: ' + str(currentPlungerLevel))
                    queuePlungerMove(tester,-increment)
                    time.sleep(1)
                    currentPlungerLevel+=-increment
                    feat.snapPhoto(tester)
                seatedGap=getPlungerCarouselGap(tester)
                currentGap=seatedGap
                while currentPlungerLevel<minDepth and currentGap<seatedGap+1:
                    print('Ascending - Depth: ' + str(currentPlungerLevel) + ', Gap: ' + str(currentGap))
                    queuePlungerMove(tester,increment)
                    time.sleep(1)
                    currentPlungerLevel+=increment
                    feat.snapPhoto(tester)
                    currentGap=getPlungerCarouselGap(tester)
                if currentPlungerLevel<minDepth:
                    print('Cycle complete - stopped due to gap increase')
                else:
                    print('Cycle complete - stopped due to max height')
                cycleCount+=1
        elif feat.featureName=="MixerOverflow" or feat.featureName=="MixerLevel":             
            numCycles=5
            fillingCycles=20
            attemptCount=0
            while attemptCount<numCycles:
                setMixerReference(tester)
                tester.openMixerValve()
                time.sleep(5)
                tester.closeMixerValve()
                time.sleep(.5)
                fillCount=0
                while fillCount<fillingCycles:
                    time.sleep(.2)
                    tester.turnPumpOn()
                    if feat.featureName=="MixerOverflow":
                        pumpOnTime=2.0
                    else:
                        pumpOnTime=.4
                    time.sleep(pumpOnTime)
                    tester.turnPumpOff()
                    print('Adding for ' + str(pumpOnTime) + ' secs')
                    tester.videoLowResCaptureLock.acquire()
                    tester.videoLowResCaptureLock.wait()
                    currentMixOverflow=feat.clipImage(tester,tester.latestLowResImage)
                    tester.videoLowResCaptureLock.release()
                    diff=cv2.absdiff(currentMixOverflow,feat.referenceClip)
                    fn=tester.basePath + 'Images/' + feat.featureName + '/Image-' + datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S.%f") + '.jpg'
                    cv2.imwrite(fn,diff)
                    fillCount+=1
                attemptCount+=1
            tester.openMixerValve()
        tester.infoMessage('Finished Series Sample Generation for Feature: ' + feat.featureName)
            
def findReferenceDots():   
    orientationDotSamples=0
    totalCircleXLeft=0
    totalCircleYLeft=0
    totalSquareSamples=0
    totalCircleXRight=0
    totalCircleYRight=0
    totalCircleSamples=0
    samplesNeeded=10
    maxDotHeightDiscrepancy=4
    tester.referenceMarkFound=False
    try:
        while totalSquareSamples<samplesNeeded and totalCircleSamples<samplesNeeded:
            tester.videoLowResCaptureLock.acquire()
            tester.videoLowResCaptureLock.wait()
            imageCopy=tester.latestLowResImage.copy()
            tester.videoLowResCaptureLock.release()
            circleXLeft,circleYLeft,circleXRight,circleYRight=matchMarkers(imageCopy,tester)
            if not circleXLeft is None:
                totalCircleXLeft+=circleXLeft
                totalCircleYLeft+=circleYLeft
                totalSquareSamples+=1
            if not circleXRight is None:
                totalCircleXRight+=circleXRight
                totalCircleYRight+=circleYRight
                totalCircleSamples+=1
        tester.avgCircleLeftMarkerRow=totalCircleYLeft/totalSquareSamples
        tester.avgCircleLeftMarkerCol=totalCircleXLeft/totalSquareSamples
        tester.avgCircleRightMarkerRow=totalCircleYRight/totalCircleSamples
        tester.avgCircleRightMarkerCol=totalCircleXRight/totalCircleSamples
        tester.avgDotDistance=tester.avgCircleRightMarkerCol-tester.avgCircleLeftMarkerCol
        heightDist=tester.avgCircleRightMarkerRow-tester.avgCircleLeftMarkerRow
        tester.infoMessage('Dot height difference: ' + str(heightDist))
        tester.infoMessage('Dot Separation:' + str(tester.avgDotDistance))
        if abs(heightDist)>maxDotHeightDiscrepancy:
            tester.infoMessage('Orientation aborted because of dot height mismatch: Left Circle: (' + str(round(tester.avgCircleLeftMarkerCol,2)) + 
                        ',' + str(round(tester.avgCircleLeftMarkerRow,2)) + '), Right Circle: (' + str(round(tester.avgCircleRightMarkerCol,2)) + 
                        ',' + str(round(tester.avgCircleRightMarkerRow,2)) + ')')
            return False
        else:
            tester.referenceCenterRow=(tester.avgCircleLeftMarkerRow+tester.avgCircleRightMarkerRow)/2
            tester.referenceCenterCol=(tester.avgCircleLeftMarkerCol+tester.avgCircleRightMarkerCol)/2
            tester.referenceMarkFound=True
            tester.infoMessage('Reference Dots Found - Row Center: ' + str(tester.referenceCenterRow) + ', Col Center: ' + str(tester.referenceCenterCol) + ', distance: ' + str(tester.avgDotDistance))
            degreesToCompensate=math.degrees(math.atan(heightDist/tester.avgDotDistance))
            tester.infoMessage('Image compensation angle: ' + str(degreesToCompensate))
            imageScalingFactor=tester.defaultDotDistance/tester.avgDotDistance
            tester.infoMessage('Image Scaling Factor: ' + str(imageScalingFactor))
            if imageScalingFactor>tester.maxImageScalingWithoutAdjustment or imageScalingFactor<tester.maxImageScalingWithoutAdjustment or degreesToCompensate>tester.maxImageRotationWithoutAdjustment or degreesToCompensate<tester.minImageRotationWithoutAdjustment:
                tester.infoMessage('Images will be adjusted using compensation factors')
                tester.setCameraRotationMatrix(degreesToCompensate,imageScalingFactor,int(tester.referenceCenterRow),int(tester.referenceCenterCol))
            else:
                tester.infoMessage('Images within tolerance, so no image rotation or scaling applied')
            return True

    except:
        tester.debugLog.exception("Unable to Find Reference Dots")
        tester.systemStatus='Error - Cannot find Reference Dots'
        return False  
    
def parkTester(tester):
    nozzlePos=testPlungerPosition(tester,useVisualOnly=True)
    if nozzlePos=="Closed":
        centeredStatus=testReagentPosition(tester,precise=False)
        if centeredStatus=="Centered":
            leftLetterPos=testLeftLetter(tester)
            if leftLetterPos=='A':
                rightLetterPos=testRightLetter(tester)
                if rightLetterPos=='B':
                    markPlungerAsClosed(tester)
                    markCarouselAsAtOrigin(tester)
                    tester.parked=True
                    print('Orientation Complete - already in parked position')
                    return True
    result=setPlungerPosition(tester,desiredPosition=tester.PLUNGER_OPEN)
    if result:
        result=rotateToPosition(tester,'A',precise=True)
        if result:
            result=setPlungerPosition(tester,desiredPosition=tester.PLUNGER_FULLY_CLOSED)
            if result:
                while tester.plungerSteps is None:
                    print('Plunger steps still none')
                    markPlungerAsClosed(tester)
                tester.parked=True
                print('Parking Complete - now in parked position')
                return True
            else:
                print('Unable to close stoppers during parking')
                sendCannotParkAlarm(tester,'Unable to close stoppers during parking')        
                return False
        else:
            print('Unable to rotate to origin position during parking')
            sendCannotParkAlarm(tester,'Unable to rotate to origin position during parking')        
            return False
    else:
        print('Unable to open stoppers during parking')
        sendCannotParkAlarm(tester,'Unable to open stoppers during parking')        
        return False
    
def orientTester():
    try:
        tester.turnLedOn()
        if tester.skipOrientation or tester.simulation:
            tester.referenceMarkFound=True
            tester.infoMessage('Orientation Skipped')
            return True
        time.sleep(4)  #Give camera time to stabilize
        findLightingEnvironment(tester)
        while not tester.referenceMarkFound:
            findReferenceDots()
        setPlungerToClosed(tester,runAsDiagnostic=False,ignorePlungerStatus=True)
        tester.valueForStopperWhenClosed=determineStopperClosureValue(tester)
        centeredStatus=testReagentPosition(tester)
        if centeredStatus=="Centered":
            leftLetterPos=testLeftLetter(tester)
            if leftLetterPos=='A':
                rightLetterPos=testRightLetter(tester)
                if rightLetterPos=='B':
                    markPlungerAsClosed(tester)
                    markCarouselAsAtOrigin(tester)
                    tester.parked=True
                    tester.systemStatus="Idle"
                    tester.infoMessage('Orientation Complete - already in parked position')
                    return True
        waitUntilPlungerStopsMoving(tester)
        result=setPlungerToOpen(tester)
        if result:
#            print('9-Plunger Opened 2')
            waitUntilPlungerStopsMoving(tester)
#            print('10-Plunger Opened 3')
            result=rotateToPosition(tester,'A',precise=True)
#            print('11-Coming back from the Rotate')            
            if result:
#                print('12-Plunger to be closed')
                result=setPlungerToClosed(tester)
#                print('13-Plunger closed')
                if result:
#                    while tester.plungerSteps is None:
#                        print('Plunger steps still none')
#                        markPlungerAsClosed(tester)
                    tester.parked=True
                    tester.systemStatus="Idle"
                    tester.infoMessage('Orientation Complete - now in parked position')
                    return True
                else:
                    tester.debugMessage('Unable to close stopper during initialization')
                    tester.systemStatus="Fault"
                    return False
            else:
                tester.debugMessage('Unable to rotate to origin position during initialization')
                tester.systemStatus="Fault"
                return False
        else:
            tester.debugMessage('Unable to open stoppers during initialization')
            tester.systemStatus="Fault"
            return False
    except:
        tester.debugLog.exception("Orientation Failure")
    
def purgeLine(tester):
    tester.openMixerValve()
    tester.turnPumpOn()
    time.sleep(tester.pumpPurgeTimeSeconds)
    tester.turnPumpOff()

def agitatorStart(tester):
    tester.agitatorOn=True
    
def agitatorStop(tester):
    tester.agitatorOn=False
    
def agitatorRun():  
    agitatorRunning=False
    while True:
        if tester.agitatorOn:
            agitatorRunning=True
            tester.agitate(1)
        else:
            if agitatorRunning:
                tester.agitatorDisable()
                agitatorRunning=False
            time.sleep(.5)
      
def cleanMixer(tester):
    try:
        agitatorStart(tester)
        cleanCycle=0
        while cleanCycle<tester.mixerCleanCycles:
            tester.closeMixerValve()
            time.sleep(.5)
            tester.turnPumpOn()
            time.sleep(tester.mixerCleanTimeSeconds)
            tester.turnPumpOff()
            tester.openMixerValve()
            time.sleep(5)
            cleanCycle+=1
        agitatorStop(tester)
    except:
        tester.debugLog.exception("Failure cleaning Mixer")
    
def setMixerReference(tester):
    mixerFeature=tester.featureList["MixerLevel"]
    mixerOverflowFeature=tester.featureList["MixerOverflow"]
    tester.videoLowResCaptureLock.acquire()
    tester.videoLowResCaptureLock.wait()
    mixerFeature.referenceClip=mixerFeature.clipImage(tester,tester.latestLowResImage)
    mixerOverflowFeature.referenceClip=mixerOverflowFeature.clipImage(tester,tester.latestLowResImage)
    tester.videoLowResCaptureLock.release()
    
def findMixerFillHeight(tester):
    try:
        maxMixerHeight=13
        mixerFeature=tester.featureList["MixerLevel"]
        tester.videoLowResCaptureLock.acquire()
        tester.videoLowResCaptureLock.wait()
        currentMixLevel=mixerFeature.clipImage(tester,tester.latestLowResImage)
        tester.videoLowResCaptureLock.release()
        mixerLevelInMM=mixerFeature.getMixerLevelBasedOnDifference(currentMixLevel)
        if mixerLevelInMM==0:  #May be empty, may be full
            mixerOverflowFeature=tester.featureList["MixerOverflow"]
            tester.videoLowResCaptureLock.acquire()
            tester.videoLowResCaptureLock.wait()
            currentMixLevel=mixerFeature.clipImage(tester,tester.latestLowResImage)
            currentOverflowLevel=mixerOverflowFeature.clipImage(tester,tester.latestLowResImage)
            tester.videoLowResCaptureLock.release()
            mixerLevelInMM=mixerFeature.getMixerLevelBasedOnDifference(currentMixLevel)
            if mixerLevelInMM==0:
                mixerOverFlow=mixerOverflowFeature.isMixerOverflowing(currentOverflowLevel)
                if mixerOverFlow:
                    return maxMixerHeight
                else:
                    return 0
            else:
                return mixerLevelInMM
        else:
            return mixerLevelInMM
    except:
        tester.debugLog.exception("Failed finding mixture level")                    
        return 0

def fillMixingCylinder(tester,vol=5,runAsDiagnostic=False):
    trueVol=vol+tester.mlDisplacedByMagnet+tester.mixerWaterLevelAdjustment    
    try:
        maxFillingAttempts=5
        maxFillingSteps=50
        attemptCount=0
        while attemptCount<maxFillingAttempts:
            if runAsDiagnostic:
                tester.debugLog.info('Starting fill attempt: ' + str(attemptCount))                        
            tester.openMixerValve()
            time.sleep(5)
            if runAsDiagnostic:
                tester.debugLog.info('Filling the Mixer')                        
            tester.closeMixerValve()
            time.sleep(.5)
            setMixerReference(tester)
            time.sleep(.5)
            tester.turnPumpOn()
            time.sleep(tester.fillTimePerML*trueVol)
            attemptStep=0
            tester.turnPumpOff()
            while attemptStep<maxFillingSteps:
                time.sleep(.2)
                mixerWaterLevel=findMixerFillHeight(tester)
                if abs(mixerWaterLevel-trueVol)<.2:
                    if runAsDiagnostic:
                        tester.debugLog.info('Mixer Filled')                        
                    return True
                elif mixerWaterLevel>=trueVol:
                    time.sleep(.2)
                    tester.openMixerValve()
                    time.sleep(.2)
                    tester.closeMixerValve()
                    if runAsDiagnostic:
                        tester.debugLog.info('Water Level: ' + str(mixerWaterLevel) + ', Releasing for ' + str(.2) + ' secs')                        
                elif mixerWaterLevel<=trueVol:
                    time.sleep(.2)
                    tester.turnPumpOn()
                    time.sleep(.2)
                    tester.turnPumpOff()
                    if runAsDiagnostic:
                        tester.debugLog.info('Water Level: ' + str(mixerWaterLevel) + ', Adding for ' + str(.2) + ' secs')                        
                attemptStep+=1
            attemptCount+=1        
        if runAsDiagnostic:
            tester.debugLog.info('Refill retries exceeded')                        
        tester.debugMessage('Refill retries exceeded')
        return False
    except:
        tester.debugLog.exception("Unable to Detect Water Level")
        return False  
    
def evaluateResults(tester,colorChartToUse):
    tester.videoLowResCaptureLock.acquire()
    tester.videoLowResCaptureLock.wait()
    imageCopy=tester.latestLowResImage.copy()
    tester.videoLowResCaptureLock.release()
    rs=evaluateColor(tester,imageCopy,colorChartToUse)
    if rs.valueAtSwatch<0:
        rs.valueAtSwatch=0
    tester.infoMessage('Result was: ' + str(rs.valueAtSwatch)) 
    return rs

def evaluateResultsBinary(tester,colorChartToUse):
    tester.videoLowResCaptureLock.acquire()
    tester.videoLowResCaptureLock.wait()
    imageCopy=tester.latestLowResImage.copy()
    tester.videoLowResCaptureLock.release()
    rs=evaluateColorBinary(tester,imageCopy,colorChartToUse)
    if rs.valueAtSwatch<0:
        rs.valueAtSwatch=0
    tester.infoMessage('Result was: ' + str(rs.valueAtSwatch)) 
    return rs

def checkTestRange(tester,ts,results):
    alarmSent=False
    if not ts.tooLowAlarmThreshold is None:
        if results<=ts.tooLowAlarmThreshold:
            sendOutOfLimitsAlarm(tester,ts.testName,results)
            alarmSent=True
    if not ts.tooLowWarningThreshold is None and not alarmSent:
        if results<=ts.tooLowWarningThreshold:
            sendOutOfLimitsWarning(tester,ts.testName,results)
            alarmSent=True
    if not ts.tooHighAlarmThreshold is None and not alarmSent:
        if results>=ts.tooHighAlarmThreshold:
            sendOutOfLimitsAlarm(tester,ts.testName,results)
            alarmSent=True
    if not ts.tooHighWarningThreshold is None and not alarmSent:
        if results>=ts.tooHighWarningThreshold:
            sendOutOfLimitsWarning(tester,ts.testName,results)
            alarmSent=True        

def convertMLtoDrops(mlToDispense):
    return round(20*mlToDispense)
    
def runTestStep(tester,testStepNumber,testName,waterVolInML,reagentSlot,agitateSecs,reagentDispenseType,amountToDispense,lastStep=False):
    try:
        tester.infoMessage('Rotating to Reagent ' + str(testStepNumber)) 
        tester.testStatus='Rotating to Reagent ' + str(testStepNumber)
        success=rotateToPosition(tester,reagentSlot)
        if not success:
            tester.debugMessage('Unable to Rotate to Reagent ' + str(testStepNumber))
            sendUnableToRotateAlarm(tester,reagentSlot,testName)
            return False
        if waterVolInML>0:
            tester.infoMessage('Cleaning the Mixer') 
            tester.testStatus='Cleaning the Mixer'
            cleanMixer(tester)
            tester.infoMessage('Filling the Mixing Cylinder') 
            tester.testStatus='Filling the Mixing Cylinder'
            fillResult=fillMixingCylinder(tester,waterVolInML)
            if not fillResult:
                tester.debugLog.info("Failure filling cylinder")
                sendFillAlarm(tester,testName)
                return False
        if agitateSecs>0:
            tester.infoMessage('Agitating the Reagent for ' + str(agitateSecs) + ' secs.') 
            tester.testStatus='Agitating the Reagent for ' + str(agitateSecs) + ' secs.'
            agitatorStart(tester)
            time.sleep(agitateSecs)
            agitatorStop(tester)
        tester.infoMessage('Dispensing ' + str(amountToDispense) + ' ' + reagentDispenseType + '. (Video Disabled)') 
        tester.testStatus='Dispensing ' + str(amountToDispense) + ' ' + reagentDispenseType + '. (Video Disabled)'
    #    print('Video disabled while dispensing drops')
        time.sleep(1)
        if reagentDispenseType=='ml':
            dropsToDispense=convertMLtoDrops(amountToDispense)
        else:
            dropsToDispense=amountToDispense
        success=dispenseDrops(tester,dropsToDispense,waitUntilPlungerRaised=False,reagent=reagentSlot)
        if not success:
            sendDispenseAlarm(tester,reagentSlot,tester.lastReagentRemainingML)
            return False
    #    print('Video re-enabled after drops')
        if tester.lastReagentRemainingML<tester.reagentRemainingMLAlarmThreshold and tester.reagentAlmostEmptyAlarmEnable:
            sendReagentAlarm(tester,reagentSlot,tester.lastReagentRemainingML)
        tester.infoMessage('Retracting plunger') 
        tester.testStatus='Retracting plunger'
        while not lastStep:
            if tester.plungerState==tester.PLUNGER_OPEN or tester.plungerState==tester.PLUNGER_MOSTLY_CLOSED or tester.plungerState==tester.PLUNGER_FULLY_CLOSED:
                break
            else:
                print('Lifting Plunger')
                time.sleep(1)
        return True
    except:
        tester.debugLog.exception('Failure when running Test Step ' + str(testStepNumber))
        return False
    
def getDirectReadResults(tester,ts,sequenceName):
    testSucceeded=True
    results=None
    tester.colorTable=tester.colorSheetList[ts.colorChartToUse].generateColorTableDisplay(tester)        
    if ts.agitateMixtureSecs>0:
        tester.testStatus='Agitating the Mixture for ' + str(ts.agitateMixtureSecs) + ' secs.'
        agitatorStart(tester)
        time.sleep(ts.agitateMixtureSecs)
        agitatorStop(tester)
    timeRemaining=ts.delayBeforeReadingSecs-ts.agitateMixtureSecs
    while timeRemaining>0:
        tester.testStatus='Waiting ' + str(timeRemaining) + ' secs before reading mixture.'
        time.sleep(1)
        timeRemaining-=1
    try:
        rs=evaluateResults(tester,ts.colorChartToUse)
        results=rs.valueAtSwatch
        tester.testStatus='Test results are: %.2f' % results
        tester.saveTestResults(results,swatchResultList=[rs])
        tester.infoMessage('Completed Test ' + sequenceName + ', Results were: %.2f' % results)
        if tester.sendMeasurementReports and not tester.iftttSecretKey is None:
            sendMeasurementReport(tester,sequenceName,results)
    except:
        testSucceeded=False
        sendEvaluateAlarm(tester,sequenceName,tester.currentLightingConditions)
        tester.debugLog.exception("Failure evaluating")
    checkTestRange(tester,ts,results)
    time.sleep(tester.pauseInSecsBeforeEmptyingMixingChamber)
    if testSucceeded:
        tester.testStatus='Result was: %.2f' % results + ' - Emptying chamber'
    else:
        tester.testStatus='Test Failed'
    tester.openMixerValve()
    time.sleep(4)
    return results

def runTitration(tester,ts,sequenceName):
    originalDistortion=tester.undistortImage
    try:
        tester.infoMessage('Rotating to Titration Reagent') 
        tester.testStatus='Rotating to Titration Reagent'
        success=rotateToPosition(tester,ts.titrationSlot)
        if not success:
            tester.debugMessage('Unable to Rotate to Titration Reagent')
            sendUnableToRotateAlarm(tester,ts.titrationSlot,testName)
            return False
        if ts.agitateMixtureSecs>0:
            tester.testStatus='Agitating the Mixture for ' + str(ts.agitateMixtureSecs) + ' secs.'
            agitatorStart(tester)
            time.sleep(ts.agitateMixtureSecs)
            agitatorStop(tester)
        remainingWaitTime=ts.delayBeforeReadingSecs-ts.agitateMixtureSecs
        if remainingWaitTime>0:
            tester.testStatus='Waiting for ' + str(remainingWaitTime) + ' secs before beginning titration.'
            time.sleep(remainingWaitTime)
        dispenseCount=0
        colorResultsList=[]
        gotInitialDrop=False
        testSucceeded=False
        tester.undistortImage=False
        while dispenseCount<=ts.titrationMaxDispenses:
            tester.testStatus='Processing with dispense = ' + str(dispenseCount)
            if ts.titrationAgitateSecs>0:
                agitatorStart(tester)
                time.sleep(ts.titrationAgitateSecs)
                agitatorStop(tester)
            rs=evaluateResultsBinary(tester,ts.colorChartToUse)
            rs.swatchDropCount=dispenseCount
            colorResultsList.append(rs)
            print('Observed Value = ' + str(rs.valueAtSwatch))
            if rs.valueAtSwatch>=ts.titrationTransition:
                testSucceeded=True
                break
            if dispenseCount==0:
                result=dispenseFirstDrop(tester,reagent=ts.titrationSlot,runAsDiagnostic=False)
                if not result:
                    break 
            else:
                result=dispenseAnotherDrop(tester,reagent=ts.titrationSlot,runAsDiagnostic=False)
                if not result:
                    break
                gotInitialDrop=True
            dispenseCount+=1 
        print('Exited')          
        tester.plungerSlow=False
        tester.suppressProcessing=False
        tester.undistortImage=originalDistortion
        tester.plungerAbort=True
        tester.plungerPause=False
        time.sleep(1)
        tester.plungerAbort=False
        try:
            if testSucceeded:
                results=dispenseCount
                tester.testStatus='Test results are: ' + str(dispenseCount)
                tester.saveTestResults(results,swatchResultList=colorResultsList)
                tester.infoMessage('Completed Test ' + sequenceName + ', Results were: ' + str(dispenseCount))
                if tester.sendMeasurementReports and not tester.iftttSecretKey is None:
                    sendMeasurementReport(tester,sequenceName,dispenseCount)
                checkTestRange(tester,ts,dispenseCount)
            elif dispenseCount>ts.titrationMaxDispenses:
                results=None
                tester.saveTestResults(results,swatchResultList=colorResultsList)
                sendEvaluateAlarm(tester,sequenceName,tester.currentLightingConditions)
                tester.debugLog.exception("Max drops dispensed before hitting transition")
            else:
                sendEvaluateAlarm(tester,sequenceName,tester.currentLightingConditions)
                tester.debugLog.exception("Failure evaluating")                
        except:
            testSucceeded=False
            sendEvaluateAlarm(tester,sequenceName,tester.currentLightingConditions)
            tester.debugLog.exception("Failure evaluating")
        time.sleep(tester.pauseInSecsBeforeEmptyingMixingChamber)
        tester.openMixerValve()
        if tester.lastReagentRemainingML<tester.reagentRemainingMLAlarmThreshold and tester.reagentAlmostEmptyAlarmEnable:
            sendReagentAlarm(tester,ts.titrationSlot,tester.lastReagentRemainingML)
        tester.infoMessage('Retracting plunger') 
        tester.testStatus='Retracting plunger'
        liftPlungerUntilExactlyOpen(tester,blockUntilDone=False)
        return results
    except:
        tester.plungerSlow=False
        tester.suppressProcessing=False
        tester.undistortImage=originalDistortion
        tester.plungerAbort=True
        tester.plungerPause=False
        time.sleep(1)
        tester.plungerAbort=False
        tester.openMixerValve()
        tester.debugLog.exception('Failure when running Titration Step')
        liftPlungerUntilExactlyOpen(tester,blockUntilDone=False)
        return None
    

def runTestSequence(tester,sequenceName):
    tester.systemStatus="Running Test"
    tester.infoMessage('Running Test ' + sequenceName)
    tester.abortJob=False
    results=None
    tester.infoMessage('Running Test ' + sequenceName) 
    tester.currentTest=sequenceName
    try:
        ts=tester.testSequenceList[sequenceName]
        numSteps=0
        if not ts.reagent1Slot is None:
            numSteps+=1
        if not ts.reagent2Slot is None:
            numSteps+=1
        if not ts.reagent3Slot is None:
            numSteps+=1
        if not ts.titrationSlot is None:
            numSteps+=1
        tester.testStatus='Making Sure Stoppers are Open'
        success=setPlungerToOpen(tester)
        if not success:
            sendCannotOpenStoppersAlarm(tester,sequenceName)
            tester.systemStatus="Fault"
            return False
        waitUntilPlungerStopsMoving(tester)
        testSucceeded=True
        if not ts.reagent1Slot is None and ts.reagent1DispenseCount>0:
            success=runTestStep(tester,1,sequenceName,ts.waterVolInML,ts.reagent1Slot,ts.reagent1AgitateSecs,ts.reagent1DispenseType,ts.reagent1DispenseCount,lastStep=numSteps==1)
            testSucceeded=success
            if success and not ts.reagent2Slot is None and ts.reagent2DispenseCount>0 and not tester.abortJob:
                success=runTestStep(tester,2,sequenceName,0,ts.reagent2Slot,ts.reagent2AgitateSecs,ts.reagent2DispenseType,ts.reagent2DispenseCount,lastStep=numSteps==2)
                testSucceeded=success
                if success and not ts.reagent3Slot is None and ts.reagent3DispenseCount>0  and not tester.abortJob:
                    success=runTestStep(tester,3,sequenceName,0,ts.reagent3Slot,ts.reagent3AgitateSecs,ts.reagent3DispenseType,ts.reagent3DispenseCount,lastStep=numSteps==3)
                    testSucceeded=success
        if testSucceeded and not tester.abortJob:
            findLightingEnvironment(tester)
            tester.testStatus='Lighting Environment is ' + tester.currentLightingConditions
            if ts.titrationSlot is None:
                results=getDirectReadResults(tester,ts,sequenceName)
                if results is None:
                    testSucceeded=False
            else:
                results=runTitration(tester,ts,sequenceName)
                if results is None:
                    testSucceeded=False
        else:
             tester.saveTestSaveBadResults()
        if not tester.anyMoreJobs():
            if testSucceeded:
                tester.testStatus='Result was: %.2f' % results + ' - Cleaning the Mixer'
            else:
                tester.testStatus='Test Failed'
            cleanMixer(tester)
            while True:
                if tester.plungerState==tester.PLUNGER_OPEN or tester.plungerState==tester.PLUNGER_MOSTLY_CLOSED or tester.plungerState==tester.PLUNGER_FULLY_CLOSED:
                    break
                else:
                    if testSucceeded:
                        print('Result was: %.2f' % results + ' - Waiting for plunger to Close')
                    else:
                        print('Test Failed')
                    time.sleep(1)
            rotateToPosition(tester,'A',precise=False)            
            parkTester(tester)
            tester.infoMessage('System Parked') 
        else:
            while True:
                if tester.plungerState==tester.PLUNGER_OPEN or tester.plungerState==tester.MOSTLY_CLOSED or tester.plungerState==tester.FULLY_CLOSED:
                    break
                else:
                    print('Waiting for plunger to Close')
                    time.sleep(1)
        if testSucceeded:
            tester.testStatus='Done: Last Results: %.2f' % results
        else:
            tester.testStatus='Test Failed'
        tester.colorTable=None
    except:
        tester.debugLog.exception('Failure when running Test')
    tester.systemStatus="Idle"
    return testSucceeded

def dailyMaintenance():
    tester.removeOldRecords()
                
def alertUser(alertCode,alertText,variable):
    tester.testerLog.info(alertText + str(variable))
    if tester.iftttSecretKey in None:
        return
    payload = "{ 'value1' : '" + tester.testerName + "', 'value2' : '" + alertText + "', 'value3' : '" + str(variable) + "'}"
    requests.post("https://maker.ifttt.com/trigger/TesterAlert/with/key/" + tester.iftttSecretKey, data=payload)    

def alarmMonitor():
    alarmCheckIntervalInSeconds=60
    lastWakeupTime=datetime.datetime.now()
    alarmCheckInterval=datetime.timedelta(seconds=alarmCheckIntervalInSeconds)
    nextalarmCheck=lastWakeupTime+alarmCheckInterval
    while True:
        lastWakeupTime=sleepUntilNextInterval(lastWakeupTime,alarmCheckIntervalInSeconds)
        if datetime.datetime.now()>nextalarmCheck:
            nextalarmCheck=nextalarmCheck+alarmCheckInterval
            try:
                time.sleep(100)
            except:
                tester.debugLog.exception("Continuing...")
                time.sleep(1)
                
def queueTestJob(tester,jobToQueue):
    print('Running job: ' + jobToQueue)
    tester.runTestLock.acquire()
    tester.addJobToQueue(jobToQueue)
    tester.runTestLock.release()
    
def runTestFromQueue():    
    while True:
        try:
            moreToDo=tester.anyMoreJobs()
            if moreToDo and tester.systemStatus=='Idle':
                tester.runTestLock.acquire()
                nextJobToRun=tester.getNextJob()
                tester.runTestLock.release()
                if nextJobToRun is None:
                    time.sleep(10)
                else:
                    if tester.simulation:
                        print('Would have runTestSequence for ' + nextJobToRun)
                    else:
                        runTestSequence(tester,nextJobToRun)
                    tester.abortJob=False
                    tester.clearRunningJobs() 
            else:
                time.sleep(10)
        except:
            tester.debugLog.exception("Error in Test Runner...")
            time.sleep(10)
            
def clearJobSchedules():
    schedule.clear()
    
def setJobSchedules(testName):
    daysToRun=tester.getJobDaysText(testName)
    tester.infoMessage('Days to run for ' + testName + ' was ' + daysToRun)
    if daysToRun=='Never':
        return
    for hour in tester.getHoursToRunList(testName):
        print('Adding schedule for ' + testName + ' on ' + daysToRun + ' at ' + hour)
        if daysToRun=='Everyday':
            schedule.every().day.at(hour).do(queueTestJob,tester,testName).tag(testName)
        elif daysToRun=='2day':
            schedule.every(2).days.at(hour).do(queueTestJob,tester,testName).tag(testName)
        elif daysToRun=='3day':
            schedule.every(3).days.at(hour).do(queueTestJob,tester,testName).tag(testName)
        elif daysToRun=='4day':
            schedule.every(4).days.at(hour).do(queueTestJob,tester,testName).tag(testName)
        elif daysToRun=='5day':
            schedule.every(5).days.at(hour).do(queueTestJob,tester,testName).tag(testName)
        elif daysToRun=='10day':
            schedule.every(10).days.at(hour).do(queueTestJob,tester,testName).tag(testName)
        elif daysToRun=='14day':
            schedule.every(14).days.at(hour).do(queueTestJob,tester,testName).tag(testName)
        elif daysToRun=='21day':
            schedule.every(21).days.at(hour).do(queueTestJob,tester,testName).tag(testName)
        elif daysToRun=='28day':
            schedule.every(28).days.at(hour).do(queueTestJob,tester,testName).tag(testName)
        elif daysToRun=='Sunday':
            schedule.every().sunday.at(hour).do(queueTestJob,tester,testName).tag(testName)
        elif daysToRun=='Monday':
            schedule.every().sunday.at(hour).do(queueTestJob,tester,testName).tag(testName)
        elif daysToRun=='Tuesday':
            schedule.every().sunday.at(hour).do(queueTestJob,tester,testName).tag(testName)
        elif daysToRun=='Wednesday':
            schedule.every().sunday.at(hour).do(queueTestJob,tester,testName).tag(testName)
        elif daysToRun=='Thursday':
            schedule.every().sunday.at(hour).do(queueTestJob,tester,testName).tag(testName)
        elif daysToRun=='Friday':
            schedule.every().sunday.at(hour).do(queueTestJob,tester,testName).tag(testName)
        elif daysToRun=='Saturday':
            schedule.every().sunday.at(hour).do(queueTestJob,tester,testName).tag(testName)

def resetJobSchedules():
    clearJobSchedules()
    for ts in tester.testSequenceList:
        try:
            setJobSchedules(ts) 
        except:
            pass 
    schedule.every().day.at('02:00').do(dailyMaintenance).tag('Maintenance')

def testerJobScheduler():
    resetJobSchedules()
    while True:
        if tester.resetJobSchedule:
            tester.resetJobSchedule=False
            resetJobSchedules()
        schedule.run_pending()
        time.sleep(10) 
        
def runDiagnosticTest(diagnosticTest):
    tester.systemStatus="Running Diagnostic"
    if diagnosticTest[0]=='Carousel Diagnostic':
        stepsToRun=diagnosticTest[1]
        tester.debugLog.info("Starting Carousel Diagnostic for " + str(stepsToRun) + ' movements')
        testRotation(tester,int(stepsToRun))
        tester.debugLog.info("Carousel Diagnostic test completed - see Debug log for results")
    elif diagnosticTest[0]=='Plunger Diagnostic':
        stepsToRun=diagnosticTest[1]
        tester.debugLog.info("Starting Plunger Diagnostic for " + str(stepsToRun) + ' open/close cycles')
        testPlunger(tester,int(stepsToRun))
        tester.debugLog.info("Plunger Diagnostic test completed - see Debug log for results")
    elif diagnosticTest[0]=='Dispense Diagnostic':
        stepsToRun=diagnosticTest[1]
        tester.debugLog.info("Starting Drop Dispensing Diagnostic for " + str(stepsToRun) + ' cycles')
        testDispensing(tester,int(stepsToRun))
        tester.debugLog.info("Drop Dispense Diagnostic test completed - see Debug log for results")
    elif diagnosticTest[0]=='Fill Mixer Diagnostic':
        stepsToRun=diagnosticTest[1]
        tester.debugLog.info("Starting Mixer Fill Diagnostic for " + str(stepsToRun) + ' cycles')
        testMixerFill(tester,int(stepsToRun))
        tester.debugLog.info("Mixer Fill Diagnostic test completed - see Debug log for results")
    else:
        try:
            print('Unknown diagnostic test ' + diagnosticTest[0])
        except:
            traceback.print_exc()   
    tester.systemStatus="Idle"
             
def testerDiagnostics(): 
    while True:
        tester.diagnosticLock.acquire()
        diagnosticQueueItemCount=len(tester.diagnosticQueue)
        if diagnosticQueueItemCount >0 and tester.systemStatus=="Idle":
            nextDiagnostic=tester.diagnosticQueue[0]
            tester.diagnosticQueue=tester.diagnosticQueue[1:]
            tester.diagnosticLock.release()
            runDiagnosticTest(nextDiagnostic)
        else:
            tester.diagnosticLock.release()
        time.sleep(10)
                  
                 
def exit_handler():
    global remoteControlThreadRPYC
    tester.debugMessage('Done')
    remoteControlThreadRPYC.close()
    tester.webcamRelease()
    
if __name__ == '__main__':
    from WebCmdHandler import processWebCommand
    basePath=getBasePath()
    sys.path.append(os.path.abspath(basePath))
    os.environ['DJANGO_SETTINGS_MODULE'] = 'AutoTesterv2.settings'
    django.setup()
    tester=Tester(1)
    if tester.manageDatabases:
        adminToUse=tester.basePath + 'tester/databaseAdminFull.py'
    else:
        adminToUse=tester.basePath + 'tester/databaseAdminEmpty.py'
    adminToReplace=tester.basePath + 'tester/databaseAdmin.py'
    try:
        fin=open(adminToUse,'r')
        text=fin.read()
        fin.close()
        fout=open(adminToReplace,'w+')
        fout.write(text)
        fout.close()
    except:
        tester.infoMessage('Admin update failed')
    testerWebName='TesterWeb'
    if platform.system()!='Windows':
        if screenPresent(testerWebName):
            tester.infoMessage('Web port already active, so not relaunched')
        else:
            tester.infoMessage('Web port not active, so launching webserver on port: ' + str(tester.webPort))
            runWebServer(tester,testerWebName)
    tester.videoLowResCaptureLock=threading.Condition()
    tester.captureImageLock=threading.Condition()
    tester.movePlungerLock=threading.Condition()
    tester.moveCarouselLock=threading.Condition()
    tester.carouselSeriesLock=threading.Condition()
    tester.runTestLock=threading.Lock()
    tester.diagnosticLock=threading.Lock()
    tester.testerLog.info('Feeded Server Threaded Started')
    remoteControlThreadRPYC = ThreadedServer(TesterRemoteControl, port = 18861)
    atexit.register(exit_handler)
    remoteControlThread=threading.Thread(target=startHandler,args=('Remote Control',remoteControlThreadRPYC))
    remoteControlThread.start()
    videoGrabberThread=threading.Thread(target=videoGrabber,name='Video Grabber',args=())
    videoGrabberThread.start()
    tester.infoMessage('Thread: ' + videoGrabberThread.getName() + ' started')
    videoStreamerThread=threading.Thread(target=videoStreamer,name='Video Streamer',args=())
    videoStreamerThread.start()
    tester.infoMessage('Thread: ' + videoStreamerThread.getName() + ' started')
    captureImagesThread=threading.Thread(target=captureImages,name='Capture Images',args=())
    captureImagesThread.start()
    tester.infoMessage('Thread: ' + captureImagesThread.getName() + ' started')
    movePlungerThread=threading.Thread(target=movePlungerProcess,name='Move Plunger',args=())
    movePlungerThread.start()
    tester.infoMessage('Thread: ' + movePlungerThread.getName() + ' started')
    moveCarouselThread=threading.Thread(target=moveCarouselProcess,name='Move Carousel',args=())
    moveCarouselThread.start()
    tester.infoMessage('Thread: ' + moveCarouselThread.getName() + ' started')
    seriesCaptureThread=threading.Thread(target=seriesCapture,name='Series Capture',args=())
    seriesCaptureThread.start()
    tester.infoMessage('Thread: ' + seriesCaptureThread.getName() + ' started')
    orientTesterThread=threading.Thread(target=orientTester,name='Orient Tester',args=())
    orientTesterThread.start()
    tester.infoMessage('Thread: ' + orientTesterThread.getName() + ' started')
    agitatorRunThread=threading.Thread(target=agitatorRun,name='Agitator Run',args=())
    agitatorRunThread.start()
    tester.infoMessage('Thread: ' + agitatorRunThread.getName() + ' started')
    runTestFromQueueThread=threading.Thread(target=runTestFromQueue,name='Run Test',args=())
    runTestFromQueueThread.start()
    tester.infoMessage('Thread: ' + runTestFromQueueThread.getName() + ' started')
    testerJobSchedulerThread=threading.Thread(target=testerJobScheduler,name='Job Scheduler',args=())
    testerJobSchedulerThread.start()
    tester.infoMessage('Thread: ' + testerJobSchedulerThread.getName() + ' started')
    testerDiagnosticsThread=threading.Thread(target=testerDiagnostics,name='Diagnostics',args=())
    testerDiagnosticsThread.start()
    tester.infoMessage('Thread: ' + testerDiagnosticsThread.getName() + ' started')

    tester.infoMessage('Tester Server version ' + currentVersion + ' loaded') 
