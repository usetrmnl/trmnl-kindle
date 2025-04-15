# Turn Your Amazon Kindle into a TRMNL

This guide explains how to jailbreak your Kindle using WinterBreak, then convert it into a personal dashboard with TRMNL.

## Prerequisites
- A PC/Mac
- TRMNL API key (physical device **or** [BYOD license](https://shop.usetrmnl.com/products/byod) **or** [BYOS client](https://docs.usetrmnl.com/go/diy/byos). No* purchase necessary.
- Registered Kindle
- Kindle connected to WiFi

`*` - for a 100% free, DIY approach you need to modify our `TRMNL_KINDLE` Zip (Step 19 below) to point to your own server, which is currently beyond the scope of this guide. this code will also be made available.

## Introduction
**[WinterBreak](https://kindlemodding.org/jailbreaking/WinterBreak/)** is a jailbreak released by **HackerDude** on **New Year’s Day 2025**. It's based on **Mesquito** and allows Kindle users to run custom applications like TRMNL. Special thanks to their many contributors and beta testers.

**Note**: Mesquito does **NOT** work on Kindle firmware 5.18.1 and later. Open your Kindle's settings tray > All Settings > Device options > Device info to determine which version you're using. If newer than 5.18, roll back.

<kdb><img src="https://github.com/usetrmnl/trmnl-kindle/blob/main/images/kindle-firmware-check.jpeg" width="500px"/></kdb>

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
 (incl Finder screenshot here, from Ryan's macbook. also include "Send to kindle" success modal after native app installation). If you do have to install the app, make sure to open it up after installation. It will look like this (incl 2x more mac screenshots) 

- After reboot, connect Kindle to PC.
- Extract `WinterBreak.tar.gz` on your computer, then copy all enclosed files to Kindle.
- For Linux/Mac users, ensure `.active_content_sandbox` folder is also copied. See troubleshooting below for help accomplishing this.

Replace files if prompted.

<kbd><img src="https://kindlemodding.org/jailbreaking/WinterBreak/file_list.png" width="650px"/></kbd>

**Troubleshooting (Mac) - Kindle doesn't appear connected**

If you connected the Kindle via USB but don't see it, install the [ConnectMyKindle](https://www.amazon.com/ConnectMyKindle) app.

<kdb><img src="https://github.com/usetrmnl/trmnl-kindle/blob/main/images/kindle-finder-doesnt-appear.png" width="400px"></kdb>

Open the app, then click "Open USB File Manager" in the top right. The default app will not work.

<kdb><img src="https://github.com/usetrmnl/trmnl-kindle/blob/main/images/send-to-kindle-app.png" width="400px"></kdb>

Drag all files from the extracted WinterBreak folder:

<kdb><img src="https://github.com/usetrmnl/trmnl-kindle/blob/main/images/winterbreak-drag-drop-usb-window.jpeg" width="400px"></kdb>

To ensure the hidden `.active_content_sandbox` content is also copied, open the hidden folder from your terminal and then drag/drop the `store` directory into the Kindle's existing `.active_content_sandbox` directory.

<kdb><img src="https://github.com/usetrmnl/trmnl-kindle/blob/main/images/winterbreak-copy-store-directory.jpeg"></kdb>

### 5. Enter Mesquito
- Eject your Kindle by clicking "Disconnect" on the device screen.
- Open the Kindle Store by clicking the cart icon and turn Airplane Mode back "off" when prompted.

<kdb><img src="https://github.com/usetrmnl/trmnl-kindle/blob/main/images/kindle-store-airplane-mode-prompt.jpeg" width="400px"></kdb>

### 6. Run WinterBreak
Click the **WinterBreak icon** after the Kindle store reloads.

<kdb><img src="https://github.com/usetrmnl/trmnl-kindle/blob/main/images/kindle-mesquito.jpeg" width="400px"></kdb>

If you don't see this, follow [these steps](https://kindlemodding.org/jailbreaking/WinterBreak/#kindle-store-encountered-an-unexpected-error) to factory reset, drag/drop Winterbreak files before* signing into Amazon, delete the LocalStorage folder if exists, etc. While building this TRMNL jailbreak guide we experienced both scenarios with different Kindle devices. Also delete `ku` and `mfa` folders if exist.

**deleting KU, MFA folders**

<kdb><img src="https://github.com/usetrmnl/trmnl-kindle/blob/main/images/kindle-ku-mfa-folders.png" width="400px"></kdb>

**deleting LocalStorage folder**

<kdb><img src="https://github.com/usetrmnl/trmnl-kindle/blob/main/images/kindle-active-content-sandbox-delete-localstorage.png" width="400px"></kdb>

### 7. Complete Jailbreak
Wait ~30 seconds for the confirmation message ("Finished installing jailbreak"), then turn Airplane mode back on.

<kdb><img src="https://github.com/usetrmnl/trmnl-kindle/blob/main/images/kindle-jailbreak-conirmation-message.jpeg" width="400px"></kdb>

## Post-Jailbreak Hotfix

### 8. Setup Hotfix
Download universal hotfix:
- [Update_hotfix_universal.bin](https://github.com/KindleModding/Hotfix/releases/latest/download/Update_hotfix_universal.bin)

**Important:** Uninstall OTARenamer if previously installed.

### 9. Copy Hotfix
Connect Kindle to your computer and copy `Update_hotfix_universal.bin`. Delete any other `.bin` files present.

<kdb><img src="https://github.com/usetrmnl/trmnl-kindle/blob/main/images/kindle-update-hotfix-universal-bin.png" width="400px"></kdb>

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
