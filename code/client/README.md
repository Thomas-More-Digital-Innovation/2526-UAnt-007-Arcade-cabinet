

### 🛠️ Getting Started

#### 1. Install Nix
To build these images, you need the Nix package manager (which can be installed on other operating systems than NixOS itself, such as standard Linux distributions, macOS, or WSL2):
```bash
sh <(curl -L https://nixos.org/nix/install) --daemon
```

#### 2. Configure Nix
Enable Flakes and Cross-Compilation by adding the following to `/etc/nix/nix.conf`:
```text
experimental-features = nix-command flakes
extra-platforms = aarch64-linux arm-linux i686-linux
```

### 🏗️ Building the Image
You can build different variants of the SD card image using the Nix flake.
*NOTE: Building can take a while. Some packages are downloaded from Cachix and others are built from source.*
For development use the "Mutable" version, this version allows you to update the configuration on the RPI without reflashing the SD card.
For production use the "Immutable" version, this version makes the SD card read-only. (Except for certain directories)

| Variant | Command |
| :--- | :--- |
| **Mutable Compressed** | `nix build .#sdImages.rpi5 --print-build-logs` |
| **Mutable Uncompressed** | `nix build .#sdImages.rpi5-uncompressed --print-build-logs` |
| **Immutable Compressed** | `nix build .#sdImages.rpi5-immutable --print-build-logs` |
| **Immutable Uncompressed** | `nix build .#sdImages.rpi5-immutable-uncompressed --print-build-logs` |

### 💾 Flashing to SD Card
Once built, the image will be in `result/sd-image/`. Replace `/dev/sdX` with your SD card device path.

#### Using `dd` (Standard)
```bash
# For compressed images (.img.zst)
zstdcat result/sd-image/*.img.zst | sudo dd of=/dev/sdX bs=4M status=progress conv=fsync

# For uncompressed images (.img)
sudo dd if=result/sd-image/*.img of=/dev/sdX bs=4M status=progress conv=fsync
```

#### Other Methods
- **Manual Decompression**: `zstd -d result/sd-image/nixos* -o rpi4-nixos.img`
- **Using Caligula**: `sudo caligula burn result/sd-image/nixos*`
- **Using Balena Etcher**


### 🔄 Updating
For testing purposes, you can update the RPI over the network without reflashing the SD card.
*NOTE: This is only possible for mutable images.*

#### Update (via ssh)
```bash
nixos-rebuild switch --flake .#rpi5 --target-host root@<IP_OR_HOSTNAME> --option filter-syscalls false
```

#### Update (via sshpass)
```bash
sshpass -p "nixos" nixos-rebuild switch --flake .#rpi5 --target-host root@<IP_OR_HOSTNAME> --option filter-syscalls false
```

#### Update for next boot (via sshpass)
```bash
sshpass -p "nixos" nixos-rebuild boot --flake .#rpi5 --target-host root@<IP_OR_HOSTNAME> --option filter-syscalls false
```


### 🔐 Configuration

#### Password Generation
If you need to update the `hashedPassword` in `flake.nix`, generate a new hash using:
```bash
mkpasswd -m sha-512
```

#### Credentials
- **User**: `root` | **Password**: `nixos`
- **User**: `pi` | **Password**: `pi`


#### Debugging Input
To watch live key presses from the arcade buttons (Ultimarc I-PAC 2):
```bash
sudo evtest
```
Select the device number for "Ultimarc I-PAC 2" to see real-time button events. This is useful for verifying hardware connections and remapping keys.

#### Keymapping
Keymapping is configured in `code/client/flake.nix` at the hardware level using systemd-hwdb (via NixOS's `services.udev.extraHwdb`). This maps low-level hardware scancodes to Linux input keycodes, affecting how inputs are registered across the entire system. Note that the Ultimarc I-PAC 2 exposes itself to the operating system as a standard USB keyboard, meaning its button presses are handled like standard keyboard keypress events.

##### How the Existing Keymap Works
In `flake.nix`, you will find this configuration:
```nix
        services.udev.extraHwdb = ''
          # Match by name
          evdev:name:Ultimarc I-PAC 2:*
            KEYBOARD_KEY_700e0=enter
        '';
```

- **`evdev:name:Ultimarc I-PAC 2:*`**: Matches any input device whose name is exactly `"Ultimarc I-PAC 2"`.
- **`KEYBOARD_KEY_700e0=enter`**: Remaps the button with hex scancode `700e0` (which is the USB HID usage ID `0xe0`, corresponding to **Left Control**) to the Linux keycode **`enter`**.
- *Note:* systemd-hwdb requires that the property assignment lines (starting with `KEYBOARD_KEY_...`) are indented with at least one space.

##### How to Add or Change Keymappings
1. **Find the Scancode**:
   Run `evtest` on the target device:
   ```bash
   sudo evtest
   ```
   Select the device number for `"Ultimarc I-PAC 2"`. Press the button you wish to remap. Look for the `MSC_SCAN` event in the output. For example:
   ```text
   Event: time ..., type 4 (EV_MSC), code 4 (MSC_SCAN), value 700e0
   ```
   The hexadecimal value (`700e0` in this case) is the button's scancode.

2. **Update the Configuration**:
   Open `code/client/flake.nix` and locate `services.udev.extraHwdb`. Add a new entry under the matching rule. For example, to map the Player 1 Button 2 (default USB scancode `700e1` / Left Shift) to `space`:
   ```nix
   services.udev.extraHwdb = ''
     evdev:name:Ultimarc I-PAC 2:*
       KEYBOARD_KEY_700e0=enter
       KEYBOARD_KEY_700e1=space
   '';
   ```
   *Note: Scancodes in `KEYBOARD_KEY_<scancode>` must be lowercase hexadecimal.*

3. **Apply the Changes**:
   If the target system is running NixOS (mutable), you can switch to the new configuration immediately:
   ```bash
   nixos-rebuild switch --flake .#rpi5 --target-host root@<IP_OR_HOSTNAME> --option filter-syscalls false
   ```
