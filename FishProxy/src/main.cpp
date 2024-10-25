#include <main.h>

uint8_t mouthState = MOTOR_IDLE;
uint8_t tailState = MOTOR_IDLE;
uint8_t headState = MOTOR_IDLE;
uint8_t controlledExternally = CONTROL_IDLE;
MotorState headMotorState = IDLE;
MotorState tailMotorState = IDLE;
MotorState mouthMotorState = IDLE;

unsigned long actionStartTimeHead = 0;
unsigned long actionStartTimeMouth = 0;
unsigned long actionStartTimeTail = 0;

void handleInterruptTail()
{
  digitalWrite(tailPinOut, digitalRead(interruptPinTailIn));
}

void handleInterruptMouth()
{
  digitalWrite(mouthPinOut, digitalRead(interruptPinMouthIn));
}

void handleInterruptHead()
{
  digitalWrite(headPinOut, digitalRead(interruptPinHeadIn));
}

void DetachInterrupts()
{
  detachInterrupt(digitalPinToInterrupt(interruptPinTailIn));
  detachInterrupt(digitalPinToInterrupt(interruptPinMouthIn));
  detachInterrupt(digitalPinToInterrupt(interruptPinHeadIn));
}

void AssumeControl()
{
  DetachInterrupts();

  ledcAttachPin(tailPinOut, tailPwmChannel);
  ledcAttachPin(headPinOut, headPwmChannel);
  ledcAttachPin(mouthPinOut, mouthPwmChannel);

  switchAudio(true);
}

void AttachInterrupts()
{
  pinMode(tailPinOut, OUTPUT);
  pinMode(headPinOut, OUTPUT);
  pinMode(mouthPinOut, OUTPUT);

  pinMode(interruptPinTailIn, INPUT);
  pinMode(interruptPinMouthIn, INPUT);
  pinMode(interruptPinHeadIn, INPUT);

  attachInterrupt(digitalPinToInterrupt(interruptPinTailIn), handleInterruptTail, CHANGE);
  attachInterrupt(digitalPinToInterrupt(interruptPinMouthIn), handleInterruptMouth, CHANGE);
  attachInterrupt(digitalPinToInterrupt(interruptPinHeadIn), handleInterruptHead, CHANGE);
}

void EndExternalControl()
{
  switchAudio(false);

  ledcDetachPin(tailPinOut);
  ledcDetachPin(headPinOut);
  ledcDetachPin(mouthPinOut);

  AttachInterrupts();
}

void switchAudio(bool externalControl)
{
  digitalWrite(relay1Out, externalControl ? LOW : HIGH);
  digitalWrite(relay2Out, externalControl ? LOW : HIGH);
}

void handleMotorStates(
    MotorState &motorState,
    uint8_t &state,
    const unsigned long startupTime,
    const unsigned long springTime,
    unsigned long actionStartTime)
{
  switch (motorState)
  {
  case IDLE:
    break;
  case UP_REQUESTED:
    if (millis() - actionStartTime >= startupTime)
    {
      motorState = UP;
      state = MOTOR_UP;
    }
    break;
  case UP:
    break;
  case DOWN_REQUESTED:
    if (millis() - actionStartTime >= springTime)
    {
      motorState = DOWN;
      state = MOTOR_DOWN;
    }
    break;
  case DOWN:
    motorState = IDLE;
    state = MOTOR_IDLE;
    break;
  default:
    Serial.println("Unknown head motor state");
    break;
  }
}

void loop()
{
  handleMotorStates(headMotorState, headState, HEAD_STARTUP_TIME, HEAD_SPRING_TIME, actionStartTimeHead);
  handleMotorStates(tailMotorState, tailState, TAIL_STARTUP_TIME, TAIL_SPRING_TIME, actionStartTimeTail);
  handleMotorStates(mouthMotorState, mouthState, MOUTH_STARTUP_TIME, MOUTH_SPRING_TIME, actionStartTimeMouth);
}

void setup()
{
  pinMode(relay1Out, OUTPUT);
  pinMode(relay2Out, OUTPUT);

  switchAudio(false);

  ledcSetup(tailPwmChannel, pwmFrequency, pwmResolution);
  ledcSetup(headPwmChannel, pwmFrequency, pwmResolution);
  ledcSetup(mouthPwmChannel, pwmFrequency, pwmResolution);

  AttachInterrupts();

  Wire.begin(0x08);
  Wire.onReceive(receiveEvent);
  Wire.onRequest(requestEvent);

  Serial.begin(115200);
  Serial.println("READY_FOR_COMMANDS");
}

void initiateMotorChange(
    uint8_t registerValue,
    MotorState &motorState,
    unsigned long &actionStart,
    const int pwmChannel)
{
  if (registerValue == MOTOR_UP_REQUESTED && motorState == IDLE)
  {
    motorState = UP_REQUESTED;
    actionStart = millis();
    headState = MOTOR_UP_REQUESTED;
    ledcWrite(pwmChannel, 255);
  }
  else if (registerValue == MOTOR_DOWN_REQUESTED && motorState == UP)
  {
    motorState = DOWN_REQUESTED;
    actionStart = millis();
    headState = MOTOR_DOWN_REQUESTED;
    ledcWrite(pwmChannel, 0);
  }
}

void receiveEvent(int numBytes)
{
  if (numBytes < 2)
    return;

  uint8_t registerAddress = Wire.read();
  uint8_t registerValue = Wire.read();

  Serial.print("registerAddress: 0x");
  Serial.println(registerAddress, HEX);
  Serial.print("registerValue: 0x");
  Serial.println(registerValue, HEX);

  switch (registerAddress)
  {
  case CONTROL_REG:
    if (registerValue == CONTROL_REQUESTED && controlledExternally != CONTROL_UNDER_CONTROL)
    {
      AssumeControl();
      controlledExternally = CONTROL_UNDER_CONTROL;
    }
    else if (registerValue == CONTROL_LEAVE && controlledExternally == CONTROL_UNDER_CONTROL)
    {
      EndExternalControl();
      controlledExternally = CONTROL_IDLE;
    }
    break;
  case HEAD_REG:
    initiateMotorChange(registerValue, headMotorState, actionStartTimeHead, headPwmChannel);
    break;
  case TAIL_REG:
    initiateMotorChange(registerValue, tailMotorState, actionStartTimeTail, tailPwmChannel);
    break;
  case MOUTH_REG:
    initiateMotorChange(registerValue, mouthMotorState, actionStartTimeMouth, mouthPwmChannel);
    break;
  default:
    break;
  }
}

void requestEvent()
{
  uint8_t registerAddress = Wire.read();
  Serial.print("Requesting register: 0x");
  Serial.print(registerAddress, HEX);
  Serial.print(", value: 0x");

  switch (registerAddress)
  {
  case CONTROL_STATUS:
    Serial.println(controlledExternally, HEX);
    Wire.write(controlledExternally);
    break;
  case MOUTH_STATUS:
    Serial.println(mouthState, HEX);
    Wire.write(mouthState);
    break;
  case TAIL_STATUS:
    Serial.println(tailState, HEX);
    Wire.write(tailState);
    break;
  case HEAD_STATUS:
    Serial.println(headState, HEX);
    Wire.write(headState);
    break;

  default:
    break;
  }
  return;
}
