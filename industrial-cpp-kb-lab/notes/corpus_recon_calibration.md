# Corpus Recon Calibration (fallback vs cloc)

- Corpus: `repos/Smoothieware`
- cloc install method: `winget install --id AlDanial.Cloc --source winget`
- cloc executable path: `C:/Users/14390/AppData/Local/Microsoft/WinGet/Packages/AlDanial.Cloc_Microsoft.Winget.Source_8wekyb3d8bbwe/cloc.exe`
- Scope: common target-extension files only

## Total Comparison

| Metric | cloc | fallback | delta | deviation |
|------|-----:|---------:|-------:|-----:|
| code | 70,704 | 70,939 | +235 | 0.33% |
| comment | 30,496 | 30,270 | -226 | 0.74% |
| blank | 17,329 | 17,320 | -9 | 0.05% |
| total | 118,529 | 118,529 | +0 | 0.00% |

- file matching: common=618, fallback_only=20, cloc_only=51

## By-file Delta Top 10 (|dCode|+|dComment|+|dBlank|)

| File | dCode | dComment | dBlank | cloc(total) | fallback(total) |
|------|------:|---------:|-------:|------------:|---------------:|
| `mbed/src/vendor/NXP/cmsis/LPC2368/uARM/vector_functions.s` | +71 | -71 | +0 | 248 | 248 |
| `mbed/src/vendor/NXP/cmsis/LPC2368/GCC_CS/vector_functions.s` | +68 | -68 | +0 | 180 | 180 |
| `mbed/src/vendor/NXP/cmsis/LPC1768/IAR/startup_LPC17xx.s` | +24 | -24 | +0 | 375 | 375 |
| `mbed/src/vendor/NXP/cmsis/LPC11U24/uARM/startup_LPC11xx.s` | +14 | -14 | +0 | 325 | 325 |
| `mbed/src/vendor/NXP/cmsis/LPC11U24/ARM/startup_LPC11xx.s` | +14 | -14 | +0 | 308 | 308 |
| `mbed/src/vendor/NXP/cmsis/LPC2368/uARM/vector_table.s` | +13 | -13 | +0 | 99 | 99 |
| `mbed/src/vendor/NXP/cmsis/LPC2368/GCC_CS/vector_table.s` | +9 | -9 | +0 | 45 | 45 |
| `mbed/src/vendor/NXP/cmsis/LPC1768/GCC_ARM/startup_LPC17xx.s` | +6 | -3 | -3 | 219 | 219 |
| `mbed/src/vendor/NXP/cmsis/LPC11U24/GCC_ARM/startup_LPC11xx.s` | +6 | -3 | -3 | 213 | 213 |
| `mbed/src/vendor/NXP/cmsis/LPC1768/uARM/startup_LPC17xx.s` | +5 | -5 | +0 | 243 | 243 |

## Verdict

- max(code/comment/blank) deviation 0.74% < 2%, **fallback is acceptable**.