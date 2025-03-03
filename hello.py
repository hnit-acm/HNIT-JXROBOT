# coding=utf-8
from __future__ import print_function

import logging
import threading
import time
from math import *
from ConfigureNao import *
from confirm import isConfirm
import vision_definitions as vd

IP = "192.168.1.106"  # 机器人的IP地址
PORT = 9559  # 机器人的端口号，默认9559
LOG_LEVEL = logging.DEBUG


class GolfGame(ConfigureNao):
    def __init__(self, robotIP, port):
        super(GolfGame, self).__init__(robotIP, port)
        self.memoryProxy = ALProxy("ALMemory", "192.168.1.106", 9559)

    def prepare(self):
        logging.debug("preparing")
        if not self.motionProxy.robotIsWakeUp():
            print("机器人未唤醒，是否唤醒")
            if isConfirm():
                self.motionProxy.wakeUp()
            else:
                self.endRun()
        self.postureProxy.goToPosture("Standing", 0.5)
        self.motionProxy.setStiffnesses("Body", 1.0)

    def rest(self):
        logging.debug("rest")
        self.motionProxy.rest()

    def endRun(self, code=0):
        self.rest()
        exit(code)

    def goStraight(self, origin):
        self.motionProxy.move(0.1, 0, 0)
        position = self.motionProxy.getRobotPosition(1)
        while True:
            new_pos = self.motionProxy.getRobotPosition(1)
            tmp=math.sqrt((new_pos[0] - position[0])** 2 + (new_pos[1]-position[1])**2)
            print(tmp)
            if  tmp> 1.5:
                break
            else:
                now = self.get_theta()
                compen = compensate(origin, now)
                compen = judge(compen)
                self.motionProxy.move(1.0, 0, compen)
        self.motionProxy.stopMove()

    def gameStart(self):
        self.tts.say("已连接")
        logging.info("已连接机器人 {}".format(IP))
        isRunning = True
        try:
            while isRunning:
                FrontFlag = self.memoryProxy.getData("Device/SubDeviceList/Head/Touch/Front/Sensor/Value")
                MiddleFlag = self.memoryProxy.getData("Device/SubDeviceList/Head/Touch/Middle/Sensor/Value")
                RearFlag = self.memoryProxy.getData("Device/SubDeviceList/Head/Touch/Rear/Sensor/Value")
                if isRunning and FrontFlag == 1:
                    self.tts.say("结束")
                    logging.info("结束")
                    isRunning = False

                elif FrontFlag == 1:
                    self.tts.say("第一关")
                    logging.info("开始第一关")
                    isRunning = True
                    self.gameTask_1()
                elif MiddleFlag == 1:
                    self.tts.say("第二关")
                    logging.info("开始第二关")
                    isRunning = True
                elif RearFlag == 1:
                    self.tts.say("第三关")
                    logging.info("开始第三关")
                    isRunning = True

                time.sleep(.5)

        except KeyboardInterrupt:
            print("退出")

    def gameTask_1(self):
        # todo...
        # self.sonarProxy.subscribe("Test_InertialSensor", 200, 0.0)
        origin = self.get_theta()
        self.motionProxy.moveTo(0,0,1.4)
        time.sleep(2)
        self.goStraight(origin)  # 1.6m
        # self.sonarProxy.unsubscribe("Test_InertialSensor")
        # ballTracking = RedBallTracking(self.memoryProxy, self.motionProxy)
        # ballTracking.start()
    def get_theta(self):
        return self.memoryProxy.getData("Device/SubDeviceList/InertialSensor/AngleZ/Sensor/Value")



class RedBallTracking:
    def __init__(self, memoryProxy, motionProxy, redBallProxy):
        self.redBallProxy = redBallProxy
        self.memoryProxy = memoryProxy
        self.motionProxy = motionProxy
        self.period = 100
        self.running = False
        self.thr = threading.Thread(target=self.track)
        self.memValue = "redBallDetected"
        self.val = []

    def start(self):
        self.running = True
        self.thr.start()

    def stop(self):
        self.running = False
        # self.thr.join()

    def getAngles(self):
        if not self.val:
            return ()
        ballInfo = self.val[1]
        cX, cY = ballInfo[0], ballInfo[1]
        x, y, z, wX, wY, wZ = self.val[3]
        AnglesX = cX / cos(wX) + wZ
        AnglesY = cY * cos(wX) + wY
        return AnglesX, AnglesY

    def getDistance(self):
        if not self.val:
            return 0
        ballInfo = self.val[1]
        cX, cY = ballInfo[0], ballInfo[1]
        x, y, z, wX, wY, wZ = self.val[3]
        distance = (tan(pi / 2 - wY + cY * cos(wX)) * z) / (cos(cX / cos(wX)) + wZ) - sqrt(pow(x, 2) + pow(y, 2))
        # distance = (tan(pi / 2 - wY + cY * cos(wX)) * z) - sqrt(pow(x, 2) + pow(y, 2))
        # distance = (tan(pi / 2 - wY) * z)
        return distance

    def getCameraAngle(self):
        if not self.val:
            return 0
        x, y, z, wX, wY, wZ = self.val[3]
        return wX, wY, wZ

    def track(self):
        self.redBallProxy.subscribe("Test_RedBall", self.period, 0.0)
        while self.running:
            time.sleep(self.period / 1000.0)
            val = self.memoryProxy.getData(self.memValue)
            self.val = val
            if val and isinstance(val, list) and len(val) >= 2:
                ballInfo = val[1]
                try:
                    logging.debug("centerX= {} centerY= {}".format(ballInfo[0], ballInfo[1]))
                    logging.debug("sizeX= {} sizeY= {}".format(ballInfo[2], ballInfo[3]))
                    anglesX = ballInfo[0]
                    anglesY = ballInfo[1]

                    previous_errorX = 0
                    setPointX = anglesX  # 设定值
                    measuredValueX = self.motionProxy.getAngles("HeadYaw", True)[0]  # 反馈值
                    errorX = abs(setPointX - measuredValueX)
                    derivativeX = errorX - previous_errorX
                    fractionMaxSpeedX = derivativeX / 2

                    previous_errorY = 0
                    setPointY = anglesY  # 设定值
                    measuredValueY = self.motionProxy.getAngles("HeadPitch", True)[0]  # 反馈值
                    errorY = abs(setPointY - measuredValueY)
                    derivativeY = errorY - previous_errorY
                    fractionMaxSpeedY = derivativeY / 2

                    self.motionProxy.setAngles("HeadYaw", anglesX, fractionMaxSpeedX)
                    self.motionProxy.setAngles("HeadPitch", anglesY, fractionMaxSpeedY)

                except IndexError, err:
                    logging.error("RedBall detected, but it seems getData is invalid. ALvalue = ")
                    logging.error(val)
                    logging.error("Error msg %s" % (str(err)))
            else:
                logging.error("Error with getData. ALValue = %s" % (str(val)))
        self.redBallProxy.unsubscribe("Test_RedBall")


if __name__ == '__main__':
    logging.basicConfig(level=LOG_LEVEL)
    action = GolfGame(IP, PORT)
    # action.gameStart()
    action.gameTask_1()
