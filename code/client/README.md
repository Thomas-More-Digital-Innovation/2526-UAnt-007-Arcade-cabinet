BUILD (Regular SD):  `nix build .#sdImages.rpi5 --print-build-logs`
BUILD (Uncompressed): `nix build .#sdImages.rpi5-uncompressed --print-build-logs`
BUILD (Immutable): `nix build .#sdImages.rpi5-immutable --print-build-logs`
BUILD (Immutable-Uncompressed): `nix build .#sdImages.rpi5-immutable-uncompressed --print-build-logs`

FLASH (Compressed): `zstdcat result/sd-image/*.img.zst | sudo dd of=/dev/sdX bs=4M status=progress conv=fsync`
FLASH (Uncompressed): `sudo dd if=result/sd-image/*.img of=/dev/sdX bs=4M status=progress conv=fsync`
DECOMPRESS: `zstd -d result/sd-image/nixos* -o rpi5-nixos.img`
CALIGULA: `sudo caligula burn result/sd-image/nixos*`

UPDATE:
`nixos-rebuild switch --flake .#rpi5 --target-host root@<IP_OR_HOSTNAME> --option filter-syscalls false`
UPDATE with sshpass:
`sshpass -p "nixos" nixos-rebuild switch --flake .#rpi5 --target-host root@<IP_OR_HOSTNAME> --option filter-syscalls false`

UPDATE (boot):
`sshpass -p "nixos" nixos-rebuild boot --flake .#rpi5 --target-host root@<IP_OR_HOSTNAME> --option filter-syscalls false`

GENERATE Password for hashedPassword:
`mkpasswd -m sha-512`

## Credentials
- **User**: `pi` | **Password**: `pi`
- **User**: `root` | **Password**: `nixos`

## Debugging Input
To watch live key presses from the arcade buttons (Ultimarc I-PAC 2):
```bash
sudo evtest
```
Select the device number for "Ultimarc I-PAC 2" to see real-time button events. This is useful for verifying hardware connections and remapping keys.

