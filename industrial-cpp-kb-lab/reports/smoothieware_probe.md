# Repo Probe Report

- Created: `2026-06-30T01:34:16.810788+00:00`
- Files: **617**
- Lines: **116,897**
- Risk level: **中**

## File Statistics

| Extension | Files |
| --- | --- |
| .c | 74 |
| .cpp | 193 |
| .h | 349 |
| .hpp | 1 |

### Largest Files

| File | Lines | Size bytes |
| --- | --- | --- |
| src/libs/ChaNFS/CHAN_FS/ff.cpp | 3,983 | 162400 |
| src/libs/Network/uip/webserver/httpd-fsdata2.h | 2,096 | 131080 |
| src/libs/LPC17xx/LPC17xxLib/src/lpc17xx_can.c | 1,937 | 57545 |
| src/libs/Network/uip/uip/uip.c | 1,923 | 69064 |
| src/modules/robot/Robot.cpp | 1,804 | 86163 |
| src/libs/Network/uip/uip/uip.h | 1,638 | 46435 |
| mbed/src/vendor/NXP/cmsis/LPC1768/core_cm3.h | 1,612 | 98846 |
| src/modules/utils/simpleshell/SimpleShell.cpp | 1,481 | 54362 |
| src/libs/LPC17xx/LPC17xxLib/src/lpc17xx_i2c.c | 1,383 | 45260 |
| src/libs/LPC17xx/LPC17xxLib/src/lpc17xx_uart.c | 1,379 | 42834 |
| src/modules/tools/endstops/Endstops.cpp | 1,274 | 54143 |
| src/modules/utils/motordrivercontrol/drivers/TMC26X/TMC26X.cpp | 1,137 | 42743 |
| mbed/src/vendor/NXP/cmsis/LPC1768/LPC17xx.h | 1,035 | 36106 |
| src/libs/USBDevice/USBDevice/USBDevice.cpp | 974 | 28077 |
| src/libs/USBDevice/USBDevice/USBHAL_LPC17.cpp | 970 | 27670 |
| src/libs/LPC17xx/sLPC17xx.h | 968 | 33806 |
| src/libs/LPC17xx/LPC17xxLib/src/lpc17xx_emac.c | 960 | 32513 |
| src/libs/LPC17xx/score_cm3.h | 908 | 37294 |
| mbed/src/vendor/NXP/capi/ethernet_api.c | 895 | 36370 |
| src/libs/LPC17xx/LPC17xxLib/inc/lpc17xx_can.h | 866 | 33417 |

## Encoding

| Encoding | Files |
| --- | --- |
| latin-1 | 2 |
| utf-8 | 615 |

### Encoding Anomalies

| File | Encoding |
| --- | --- |
| mbed/src/vendor/NXP/cmsis/LPC11U24/system_LPC11Uxx.c | latin-1 |
| src/libs/LPC17xx/LPC17xxLib/inc/lpc17xx_dac.h | latin-1 |

## Ctags Structure

- Available: `True`
- Exit code: `0`
- Empty or failed files: **7**

| Kind | Count |
| --- | --- |
| class | 209 |
| enum | 131 |
| function | 3128 |
| macro | 3929 |
| namespace | 49 |
| struct | 379 |

## Risk Files

### Large Files

| File | Lines |
| --- | --- |
| src/libs/ChaNFS/CHAN_FS/ff.cpp | 3,983 |

### Generated-Like Files

| File | Lines |
| --- | --- |
| mbed/src/cpp/CAN.h | 196 |
| mbed/src/cpp/Serial.h | 138 |
| mbed/src/vendor/NXP/cmsis/LPC11U24/LPC11Uxx.h | 670 |
| src/libs/LPC17xx/LPC17xxLib/inc/lpc17xx_pwm.h | 342 |
| src/libs/LPC17xx/LPC17xxLib/src/lpc17xx_gpio.c | 759 |
| src/libs/LPC17xx/LPC17xxLib/src/lpc17xx_timer.c | 606 |
| src/libs/Network/uip/uip/psock.h | 409 |
| src/libs/Network/uip/uip/uipopt.h | 546 |
| src/main.cpp | 277 |
| src/modules/communication/GcodeDispatch.cpp | 490 |
| src/modules/tools/spindle/SoftSerial/SoftSerial.h | 127 |
| src/modules/utils/motordrivercontrol/drivers/TMC26X/TMC26X.h | 451 |
| src/testframework/easyunit/test.h | 433 |

### Binary Or Garbled Files

No binary or garbled source files detected.

## Directory Code Map

| Directory | Files | Lines | Symbols |
| --- | --- | --- | --- |
| src | 452 | 93,513 | function:2453, class:174, macro:2814, namespace:16, enum:84, struct:237 |
| mbed | 164 | 23,276 | macro:1101, enum:47, struct:142, function:675, class:35, namespace:33 |
| mri | 1 | 108 | macro:14 |

## Index Feasibility

- Estimated scan time: **0.15 s**
- Estimated ctags time: **3.54 s**
- Estimated chunks size: **2.0 MB**
- Ctags fail rate: **1.1%**
- Risk level: **中**

### Recommendations

- 先确认超长文件是否为第三方或生成代码，必要时通过 --exclude 排除目录。
- 迁移前确认 GBK/GB18030 文件读取策略，避免 line number 与源码显示不一致。
- generated-like 文件建议默认不作为业务问答重点。
