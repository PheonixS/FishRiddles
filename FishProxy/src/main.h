#ifndef MAIN_H
#include <Arduino.h>
#include <Wire.h>

#define MOUTH_REG 0x01
#define CONTROL_REG 0x02
#define TAIL_REG 0x03
#define HEAD_REG 0x04

#define MOUTH_STATUS 0x50
#define CONTROL_STATUS 0x51
#define TAIL_STATUS 0x52
#define HEAD_STATUS 0x53

// register values
#define MOTOR_IDLE 0x00
#define MOTOR_UP_REQUESTED 0x01
#define MOTOR_UP 0x02
#define MOTOR_DOWN_REQUESTED 0x03
#define MOTOR_DOWN 0x04

#define CONTROL_IDLE 0x10
#define CONTROL_REQUESTED 0x11
#define CONTROL_UNDER_CONTROL 0x12
#define CONTROL_LEAVE 0x13

#define ERROR_PLEASE_WAIT 0x20

const int pwmFrequency = 5000;
const int pwmResolution = 8;

const int interruptPinTailIn = GPIO_NUM_34;
const int tailPinOut = GPIO_NUM_13;
const int tailPwmChannel = 0;

const int interruptPinMouthIn = GPIO_NUM_35;
const int mouthPinOut = GPIO_NUM_25;
const int mouthPwmChannel = 1;

const int interruptPinHeadIn = GPIO_NUM_32;
const int headPinOut = GPIO_NUM_26;
const int headPwmChannel = 2;

const int relay1Out = GPIO_NUM_18;
const int relay2Out = GPIO_NUM_4;

// Movement timing constants (in milliseconds)
const unsigned long MOUTH_STARTUP_TIME = 250;
const unsigned long MOUTH_SPRING_TIME = 200;
const unsigned long HEAD_STARTUP_TIME = 600;
const unsigned long HEAD_SPRING_TIME = 1500;
const unsigned long TAIL_STARTUP_TIME = 250;
const unsigned long TAIL_SPRING_TIME = 125;

void requestEvent();
void receiveEvent(int numBytes);
void switchAudio(bool externalControl = false);

enum MotorState
{
    UNKNOWN_STATE, // pin unknown to zero so it's not overlap
    IDLE,
    UP,
    UP_REQUESTED,
    DOWN,
    DOWN_REQUESTED,
};

void handleMotorStates(
    MotorState &motorState,
    uint8_t &state,
    const unsigned long startupTime,
    const unsigned long springTime,
    unsigned long actionStartTime);

void initiateMotorChange(
    uint8_t registerValue,
    MotorState &motorState,
    unsigned long &actionStart,
    const int pwmChannel);
#endif
