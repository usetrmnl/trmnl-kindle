# Turn Your Amazon Kindle into a TRMNL

This guide explains how to jailbreak your Kindle using WinterBreak, then connect it to  a TRMNL device.

## Prerequisites
- A PC/Mac
- TRMNL API key (physical device or [BYOD license](https://shop.usetrmnl.com/products/byod))
- Registered Kindle
- Kindle connected to WiFi (Steps 8–10 require active internet)

## Introduction
**WinterBreak** is a jailbreak released by **HackerDude** on **New Year’s Day 2025**. It's based on **Mesquito** and allows Kindle users to run custom applications like TRMNL.

**Note**: Mesquito does **NOT** work on Kindle firmware 5.18.1 and later. Open your Kindle's settings tray > All Settings > Device options > Device info to determine which version you're using. If newer than 5.18, roll back.

<kdb><img src="https://github.com/usetrmnl/trmnl-kindle/blob/main/images/kindle-firmware-check.jpeg" width="500px"/></kdb>

### Special Thanks
- Marek
- NiLuJe
- Katadelos
- All beta-testers

---

## Jailbreaking Steps

### 1. Download WinterBreak
Download the latest WinterBreak:
- [WinterBreak.tar.gz](https://github.com/KindleModding/WinterBreak/releases/latest/download/WinterBreak.tar.gz)

### 2. Airplane Mode
Turn on **Airplane Mode** on your Kindle. Swipe down or tap the battery icon in the top right corner to access the tray.

<kdb><img src="https://github.com/usetrmnl/trmnl-kindle/blob/main/images/kindle-airplane-mode-enabled.jpeg" width="500px"/></kdb>

### 3. Restart Kindle
From the same settings tray as Airplane Mode, click All Settings > Device options >  Restart. Pending your Kindle device and firmware, you may see either modal option below.

<div align="center">
  <kbd><img src="https://kindlemodding.org/jailbreaking/WinterBreak/reboot.png" width="350px"/></kbd>
  <kbd><img src="https://github.com/usetrmnl/trmnl-kindle/blob/main/images/kindle-paperwhite-restart-modal.jpeg" width="350px"/></kbd>
</div>

### 4. Extract WinterBreak
- After reboot, connect Kindle to PC.
- Extract `WinterBreak.tar.gz` on your PC first, then copy files to Kindle.
- For Linux/Mac users, ensure `.active_content_sandbox` folder is also copied.

Replace files if prompted.

<kbd><img src="https://kindlemodding.org/jailbreaking/WinterBreak/file_list.png" width="650px"/></kbd>

### 5. Enter Mesquito
- Eject Kindle.
- Open Kindle Store and confirm to turn off Airplane mode when prompted.

<kbd><img src="https://kindlemodding.org/jailbreaking/WinterBreak/store_aeroplane.png" width="650px"/></kbd>

### 6. Run WinterBreak
Click the **WinterBreak icon** after store loads.

![WinterBreak Launcher](https://kindlemodding.org/jailbreaking/WinterBreak/winterbreak_launcher.png)

### 7. Complete Jailbreak
Wait ~30 seconds for confirmation message, then turn Airplane mode back on.

![WinterBreak Run](https://kindlemodding.org/jailbreaking/WinterBreak/winterbreak_run.png)

## Post-Jailbreak Hotfix

### 8. Setup Hotfix
Download universal hotfix:
- [Update_hotfix_universal.bin](https://github.com/KindleModding/Hotfix/releases/latest/download/Update_hotfix_universal.bin)

**Important:** Uninstall OTARenamer if previously installed.

### 9. Copy Hotfix
Connect Kindle to PC and copy `Update_hotfix_universal.bin`. Delete any other `.bin` files present.

![Copy Hotfix](https://kindlemodding.org/jailbreaking/post-jailbreak/setting-up-a-hotfix/copy_hotfix.png)

### 10. Install Hotfix
- Eject Kindle.
- Go to **Settings → Three dots → Update Your Kindle**.

![Update Settings](https://kindlemodding.org/jailbreaking/post-jailbreak/setting-up-a-hotfix/update_settings.png)

### 11. Confirm Hotfix Install
Confirm when asked to update.

![Update Dialog](https://kindlemodding.org/jailbreaking/post-jailbreak/setting-up-a-hotfix/update_dialog.png)

### 12. Run Hotfix
After installation, run the Hotfix by opening **Run Hotfix** or **Run Bridge** from your library.

Run the Hotfix after every OTA update.

![Run Hotfix](https://kindlemodding.org/jailbreaking/post-jailbreak/setting-up-a-hotfix/run_hotfix.png)

## Install KUAL and MRPI

### 13. Download KUAL and MRPI
- Download MRPI and KUAL: [KUAL-MRPI](https://fw.notmarek.com/khf/kual-mrinstaller-khf.tar.xz)
- Provided by Marek: [More info](https://fw.notmarek.com/khf/)

### 14. Choose Correct KUAL Version
- **Newer Kindles (post-2012):** [KUAL Coplate](https://kindlemodding.org/jailbreaking/post-jailbreak/installing-kual-mrpi/Update_KUALBooklet_ALLDEVICES_KS2_install.bin)
- **Legacy Kindles:** [KUAL Legacy](https://storage.gra.cloud.ovh.net/v1/AUTH_2ac4bfee353948ec8ea7fd1710574097/mr-public/KUAL/KUAL-v2.7.35-g2d06358-20250103.tar.xz)

### 15. Extract and Copy MRPI and KUAL
- Extract MRPI, copying the `extensions` and `mrpackages` folders to Kindle.
- Extract KUAL and copy the `.bin` file into Kindle's `mrpackages` folder.

![Extracting MRPI](https://kindlemodding.org/jailbreaking/post-jailbreak/installing-kual-mrpi/mrpackages_extensions_folders.png)
![Extracting KUAL](https://kindlemodding.org/jailbreaking/post-jailbreak/installing-kual-mrpi/kual_install_bin.png)

### 16. Eject and Disconnect Kindle
Safely eject and unplug your Kindle.

![Eject](https://kindlemodding.org/jailbreaking/post-jailbreak/installing-kual-mrpi/eject.png)

### 17. Run MRPI
Run MRPI by typing `;log mrpi` into the search bar and press enter.

![Run Dispatch](https://kindlemodding.org/jailbreaking/post-jailbreak/installing-kual-mrpi/run_dispatch.png)

### 18. Complete KUAL Installation
Wait until installation completes and **KUAL book** appears in your library.

*Note:* "Application Error" dialog may appear on some modern Kindles; this is normal.

## Install TRMNL

### 19. Download TRMNL KUAL Package
FIXME: Download: [TRMNL_KINDLE.zip - https://usetrmnl.com/devices/5831/kindle/TRMNL_KINDLE.zip](https://usetrmnl.com/devices/5831/kindle/TRMNL_KINDLE.zip)

### 20. Unzip TRMNL Package

### 21. Connect Kindle to PC

### 22. Copy TRMNL to Kindle
Copy the `TRMNL_KINDLE` folder to Kindle’s `extensions` folder.

### 23. Disconnect Kindle
Safely eject and disconnect your Kindle.

### 24. Open KUAL
Launch KUAL from your library.
![Launch KUAL from your library](https://files.littlebird.com.au/IMG_2455_e.jpeg)


### 25. Start TRMNL
- Press the **TRMNL** button.
![Launch KUAL from your library](https://files.littlebird.com.au/IMG_2456_e.jpeg)
- Select **Start TRMNL**.
![Launch KUAL from your library](https://files.littlebird.com.au/IMG_2457_e.jpeg)
Your Kindle is now successfully running TRMNL!
![successfully running TRMNL!](https://files.littlebird.com.au/IMG_2458.jpg)
